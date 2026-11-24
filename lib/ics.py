"""iCalendar (RFC 5545) feed rendering for Apple Calendar / Google Calendar subscriptions.

`render_ics` is a pure function, like every adapter's `parse()`: same events +
same clock -> byte-identical output, so it is tested offline in tests/test_ics.py.
No network, no I/O.

Every ride day becomes an all-day VEVENT (VALUE=DATE), which sidesteps timezones
entirely — listing times are best-effort ("7:00am" or nothing), so they go in the
description instead of pretending to be a precise DTSTART.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from lib.models import Event, Status

PRODID = "-//rideday-radar//AU motorcycle ride days//EN"
REFRESH = "PT6H"  # matches the GitHub Actions rebuild cadence

_STATUS_TAG = {
    Status.SOLD_OUT: "[售罄] ",
    Status.FILLING_FAST: "[快满] ",
}
_STATUS_LABEL = {
    Status.OPEN: "有票",
    Status.FILLING_FAST: "快满",
    Status.SOLD_OUT: "已售罄",
    Status.UNKNOWN: "未知",
}


# --- RFC 5545 primitives ------------------------------------------------------

def _escape(text: str) -> str:
    """Escape a TEXT value (§3.3.11): backslash, newline, semicolon, comma."""
    return (text.replace("\\", "\\\\").replace("\r\n", "\\n").replace("\n", "\\n")
                .replace(";", "\\;").replace(",", "\\,"))


def _fold(line: str) -> str:
    """Fold a content line to <=75 octets (§3.1); continuation lines start with a space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks: list[str] = []
    start, limit = 0, 75
    while start < len(raw):
        end = min(start + limit, len(raw))
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:  # never split a UTF-8 char
            end -= 1
        chunks.append(raw[start:end].decode("utf-8"))
        start = end
        limit = 74  # continuations spend one octet on the leading space
    return "\r\n ".join(chunks)


def _stamp(now: datetime) -> str:
    utc = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return utc.strftime("%Y%m%dT%H%M%SZ")


# --- event rendering ----------------------------------------------------------

def _summary(e: Event) -> str:
    bits = [e.track or e.title]
    if e.price_display:
        bits.append(e.price_display)
    return f"🏁 {_STATUS_TAG.get(e.status, '')}{' · '.join(bits)}"


def _description(e: Event) -> str:
    lines = [e.provider_name, f"状态: {e.status_raw or _STATUS_LABEL[e.status]}"]
    if e.start_time:
        lines.append(f"开始: {e.start_time}")
    if e.price_display:
        lines.append(f"价格: {e.price_display}")
    if e.url:
        lines.append(f"订票: {e.url}")
    lines.append("以官网为准 · rideday-radar")
    return "\n".join(lines)


def _vevent(e: Event, *, stamp: str) -> list[str]:
    end = (e.date_end or e.date_start) + timedelta(days=1)  # DTEND is exclusive
    props = [
        ("UID", f"{e.event_uid}@rideday-radar"),
        ("DTSTAMP", stamp),
        ("DTSTART;VALUE=DATE", e.date_start.strftime("%Y%m%d")),
        ("DTEND;VALUE=DATE", end.strftime("%Y%m%d")),
        ("SUMMARY", _escape(_summary(e))),
        ("DESCRIPTION", _escape(_description(e))),
        ("LOCATION", _escape(", ".join(x for x in (e.track, e.state) if x))),
        ("CATEGORIES", _escape(e.provider_name)),
        # Always CONFIRMED: STATUS:CANCELLED makes several clients hide the event
        # outright, so a sold-out day would silently vanish. The [售罄] tag in the
        # summary is what marks it instead.
        ("STATUS", "CONFIRMED"),
        ("TRANSP", "TRANSPARENT"),
        ("SEQUENCE", "0"),
    ]
    if e.url:
        props.append(("URL", e.url))  # URI value: not TEXT-escaped
    return ["BEGIN:VEVENT", *(_fold(f"{k}:{v}") for k, v in props), "END:VEVENT"]


def render_ics(events: list[Event], *, name: str, now: datetime, desc: str = "") -> str:
    """Render events as one subscribable .ics calendar. Pure: no clock, no network."""
    stamp = _stamp(now)
    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold(f"X-WR-CALNAME:{name}"),
        f"REFRESH-INTERVAL;VALUE=DURATION:{REFRESH}",
        f"X-PUBLISHED-TTL:{REFRESH}",
    ]
    if desc:
        out.append(_fold(f"X-WR-CALDESC:{desc}"))
    for e in sorted(events, key=lambda x: (x.date_start, x.event_uid)):
        out += _vevent(e, stamp=stamp)
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


# --- feeds --------------------------------------------------------------------

@dataclass(frozen=True)
class Feed:
    slug: str            # "vic" / "all"
    label: str           # "VIC" / "全部"
    name: str            # calendar name shown in Apple Calendar
    events: list[Event]

    @property
    def filename(self) -> str:
        return f"{self.slug}.ics"


#: 澳洲所有州/领地。某州这一轮没有场次也照样出一份空 feed —— 否则那个 `.ics`
#: 根本不生成,已经订阅的客户端会拿到 404 而不是一个空日历(2026-11-24 的 QLD
#: 就是这样:9 月有 24 场、11 月全部跑完,qld.ics 就消失了)。
AU_STATES = ("ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA")


def advertised_feeds(feeds: list[Feed]) -> list[Feed]:
    """页面上挂出来的订阅链接:`all` 加上有场次的州。

    空的州 feed **文件照样发布**(订阅 URL 必须稳定),只是不往页面上挂一排「0」。
    """
    return [f for f in feeds if f.slug == "all" or f.events]


def build_feeds(events: list[Event]) -> list[Feed]:
    """每个州一个 feed(数据里出现的州 ∪ `AU_STATES`)加一个 `all`;`all` 在最前。

    取**并集**而不是只按 `AU_STATES`:数据里冒出没见过的州(将来真有 NZ 赛道的话)
    照样要出 feed —— 这是原来「不硬编码州列表」那条约定要保的东西。
    """
    by_state: dict[str, list[Event]] = {s: [] for s in AU_STATES}
    for e in events:
        if e.state:
            by_state.setdefault(e.state.upper(), []).append(e)
    feeds = [Feed("all", "全部", "澳洲赛道日 · 全部", list(events))]
    feeds += [Feed(state.lower(), state, f"澳洲赛道日 · {state}", evs)
              for state, evs in sorted(by_state.items())]
    return feeds


def render_feed(feed: Feed, *, now: datetime) -> str:
    return render_ics(feed.events, name=feed.name,
                      desc=f"{len(feed.events)} 场即将到来的赛道日 · 每 6 小时刷新", now=now)
