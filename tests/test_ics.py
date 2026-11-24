from datetime import date, datetime, timezone

import pytest

from lib.ics import AU_STATES, Feed, advertised_feeds, build_feeds, render_feed, render_ics
from lib.models import Event, Status

NOW = datetime(2026, 8, 3, 4, 30, 0, tzinfo=timezone.utc)


def mk(track="Broadford", state="VIC", d=date(2026, 9, 7), status=Status.OPEN, **kw):
    kw.setdefault("provider", "champions")
    kw.setdefault("provider_name", "Champions Ride Days")
    kw.setdefault("price_display", "$220.00")
    kw.setdefault("url", f"https://championsridedays.com.au/product/{track.lower()}-{d}/")
    return Event(title=track, track=track, state=state, date_start=d, status=status, **kw)


def lines(text):
    return text.split("\r\n")


def unfold(text):
    """Undo RFC 5545 line folding so tests can assert on whole property values."""
    return text.replace("\r\n ", "")


# --- calendar envelope --------------------------------------------------------

def test_envelope_is_a_valid_vcalendar_with_crlf_endings():
    out = render_ics([mk()], name="赛道日 · VIC", now=NOW)
    assert out.startswith("BEGIN:VCALENDAR\r\n")
    assert out.endswith("END:VCALENDAR\r\n")
    assert "\n" not in out.replace("\r\n", "")  # every line ends CRLF, no bare LF
    ls = lines(out)
    assert "VERSION:2.0" in ls
    assert "CALSCALE:GREGORIAN" in ls
    assert "METHOD:PUBLISH" in ls
    assert any(line.startswith("PRODID:") for line in ls)


def test_calendar_name_is_published_for_apple_calendar():
    out = unfold(render_ics([mk()], name="赛道日 · VIC", now=NOW))
    assert "X-WR-CALNAME:赛道日 · VIC" in lines(out)
    # Apple/most clients honour these to re-poll a subscription
    assert "REFRESH-INTERVAL;VALUE=DURATION:PT6H" in lines(out)
    assert "X-PUBLISHED-TTL:PT6H" in lines(out)


def test_empty_feed_still_renders_a_valid_calendar():
    out = render_ics([], name="赛道日 · TAS", now=NOW)
    assert "BEGIN:VEVENT" not in out
    assert out.startswith("BEGIN:VCALENDAR\r\n") and out.endswith("END:VCALENDAR\r\n")


# --- events -------------------------------------------------------------------

def test_one_vevent_per_event_keyed_by_stable_uid():
    a, b = mk(d=date(2026, 9, 7)), mk(d=date(2026, 9, 21))
    out = unfold(render_ics([a, b], name="x", now=NOW))
    assert out.count("BEGIN:VEVENT") == 2
    assert f"UID:{a.event_uid}@rideday-radar" in lines(out)
    assert f"UID:{b.event_uid}@rideday-radar" in lines(out)


def test_all_day_event_uses_date_values_with_exclusive_dtend():
    out = unfold(render_ics([mk(d=date(2026, 9, 7))], name="x", now=NOW))
    assert "DTSTART;VALUE=DATE:20260907" in lines(out)
    assert "DTEND;VALUE=DATE:20260908" in lines(out)  # DTEND is exclusive
    assert "DTSTART:" not in out  # never a timed event


def test_multi_day_event_ends_the_day_after_date_end():
    e = mk(d=date(2026, 12, 22), date_end=date(2026, 12, 23))
    out = unfold(render_ics([e], name="x", now=NOW))
    assert "DTSTART;VALUE=DATE:20261222" in lines(out)
    assert "DTEND;VALUE=DATE:20261224" in lines(out)


def test_dtstamp_comes_from_the_passed_clock():
    out = unfold(render_ics([mk()], name="x", now=NOW))
    assert "DTSTAMP:20260803T043000Z" in lines(out)


def test_summary_carries_track_and_price():
    out = unfold(render_ics([mk()], name="x", now=NOW))
    assert "SUMMARY:🏁 Broadford · $220.00" in lines(out)


def test_sold_out_and_filling_fast_are_flagged_in_the_summary():
    sold = unfold(render_ics([mk(status=Status.SOLD_OUT)], name="x", now=NOW))
    fast = unfold(render_ics([mk(status=Status.FILLING_FAST)], name="x", now=NOW))
    assert "SUMMARY:🏁 [售罄] Broadford · $220.00" in lines(sold)
    assert "SUMMARY:🏁 [快满] Broadford · $220.00" in lines(fast)


def test_sold_out_events_stay_confirmed_so_clients_do_not_hide_them():
    out = unfold(render_ics([mk(status=Status.SOLD_OUT)], name="x", now=NOW))
    assert "STATUS:CONFIRMED" in lines(out)
    assert "STATUS:CANCELLED" not in out  # clients hide cancelled events


def test_all_day_events_do_not_block_busy_time():
    out = unfold(render_ics([mk()], name="x", now=NOW))
    assert "TRANSP:TRANSPARENT" in lines(out)


def test_location_url_and_description_are_populated():
    e = mk(start_time="7:00am", status_raw="Available!")
    out = unfold(render_ics([e], name="x", now=NOW))
    assert f"LOCATION:Broadford\\, VIC" in lines(out)
    assert f"URL:{e.url}" in lines(out)
    desc = next(line for line in lines(out) if line.startswith("DESCRIPTION:"))
    assert "Champions Ride Days" in desc
    assert "7:00am" in desc and "Available!" in desc and e.url in desc
    assert "\\n" in desc  # newlines escaped, never literal


def test_events_are_ordered_by_date():
    late, early = mk(d=date(2026, 11, 1)), mk(d=date(2026, 9, 7))
    out = unfold(render_ics([late, early], name="x", now=NOW))
    assert out.index("20260907") < out.index("20261101")


# --- RFC 5545 escaping / folding ---------------------------------------------

def test_text_fields_escape_commas_semicolons_and_backslashes():
    e = mk(track="Wakefield; Goulburn, NSW\\x", state="NSW")
    out = unfold(render_ics([e], name="x", now=NOW))
    summary = next(line for line in lines(out) if line.startswith("SUMMARY:"))
    assert "Wakefield\\; Goulburn\\, NSW\\\\x" in summary


def test_long_lines_are_folded_to_75_octets_without_splitting_utf8():
    e = mk(track="桂林" * 40, url="https://example.com/" + "a" * 200)
    out = render_ics([e], name="x", now=NOW)
    for line in lines(out):
        assert len(line.encode("utf-8")) <= 75, line
        if line.startswith(" "):
            continue
    assert "桂林" * 40 in unfold(out)  # unfolds back to the original text


def test_output_is_byte_stable_for_the_same_input():
    evs = [mk(d=date(2026, 9, 7)), mk(d=date(2026, 9, 21))]
    assert render_ics(evs, name="x", now=NOW) == render_ics(evs, name="x", now=NOW)


# --- feed grouping ------------------------------------------------------------

def test_build_feeds_makes_one_feed_per_state_plus_all():
    evs = [mk(state="VIC"), mk(state="VIC", d=date(2026, 9, 21)),
           mk(state="NSW", track="Sydney Motorsport Park")]
    feeds = {f.slug: f for f in build_feeds(evs)}
    assert set(feeds) == {"all"} | {s.lower() for s in AU_STATES}
    assert len(feeds["all"].events) == 3
    assert len(feeds["vic"].events) == 2
    assert len(feeds["nsw"].events) == 1
    assert feeds["vic"].filename == "vic.ics" and "VIC" in feeds["vic"].name


def test_events_without_a_state_only_land_in_the_all_feed():
    mystery = mk(state=None, track="Mystery Track")
    evs = [mystery, mk(state="VIC")]
    feeds = {f.slug: f for f in build_feeds(evs)}
    assert len(feeds["all"].events) == 2
    assert len(feeds["vic"].events) == 1
    # 没有州的那场不该落进任何一个州 feed
    assert all(mystery.event_uid not in {e.event_uid for e in f.events}
               for slug, f in feeds.items() if slug != "all")


def test_all_feed_comes_first_then_states_alphabetically():
    # 带一个不在 AU_STATES 里的州,顺带证明排序是在并集上做的
    evs = [mk(state="WA"), mk(state="NSW"), mk(state="NZ")]
    expected = ["all"] + sorted({s.lower() for s in AU_STATES} | {"nz"})
    assert [f.slug for f in build_feeds(evs)] == expected


@pytest.mark.parametrize("state", ["vic", "Vic", "VIC"])
def test_state_slug_is_case_insensitive(state):
    feeds = {f.slug: f for f in build_feeds([mk(state=state)])}
    assert "vic" in feeds and feeds["vic"].name.endswith("VIC")


# --- 空州 feed:订阅链接要稳定 ----------------------------------------------

def test_every_au_state_gets_a_feed_even_when_it_has_no_events():
    # 某州暂时没有未来场次时,那个 .ics 以前根本不生成,已订阅的客户端拿 404。
    feeds = {f.slug: f for f in build_feeds([mk(state="VIC")])}
    assert set(feeds) == {"all"} | {s.lower() for s in AU_STATES}
    assert len(feeds["vic"].events) == 1
    assert feeds["qld"].events == []          # 没场次,但文件得在
    assert feeds["qld"].filename == "qld.ics"


def test_unknown_state_in_the_data_still_gets_its_own_feed():
    # 回归守卫:原来「按数据里出现的州动态分 feed」那条不许因为加了已知州列表而丢掉
    feeds = {f.slug: f for f in build_feeds([mk(state="NZ", track="Hampton Downs")])}
    assert "nz" in feeds and len(feeds["nz"].events) == 1


def test_empty_state_feed_renders_a_valid_calendar_with_no_events():
    feeds = {f.slug: f for f in build_feeds([mk(state="VIC")])}
    out = render_feed(feeds["qld"], now=NOW)
    assert "BEGIN:VEVENT" not in out
    assert out.startswith("BEGIN:VCALENDAR\r\n") and out.endswith("END:VCALENDAR\r\n")


def _feed(slug, events):
    return Feed(slug, slug.upper(), f"x · {slug}", events)


def test_advertised_feeds_hides_empty_states_but_keeps_all():
    # 空 feed 文件照样发布(URL 要稳定),只是不往页面上挂一排「0」
    e = mk(state="VIC")
    feeds = [_feed("all", [e]), _feed("vic", [e]), _feed("qld", []), _feed("tas", [])]
    assert [f.slug for f in advertised_feeds(feeds)] == ["all", "vic"]


def test_advertised_feeds_keeps_all_even_when_it_is_empty():
    # 回归守卫:all 不管空不空都要留着,否则页面上订阅区会整块消失
    assert [f.slug for f in advertised_feeds([_feed("all", [])])] == ["all"]
