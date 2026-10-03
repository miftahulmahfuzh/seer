"""Tests for yahoo.py (frame parsing, ticker mapping, rate-limit detection) and the
backfill command (batching, resume, backoff, empty retry, date filter, idempotency,
dry run, demo purge ordering). No test touches the network: the yfinance call is an
injected fake, sleeps are recorded instead of slept, FX history is a fake."""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest

from seer_engine import bars, dates, demo, fx, universe, yahoo
from seer_engine.commands import backfill as backfill_cmd

COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

D0 = date(2023, 12, 29)  # before --start
D1 = date(2024, 1, 2)
D2 = date(2024, 1, 3)
D3 = date(2024, 1, 4)  # == --end
D4 = date(2024, 1, 5)  # after --end (a "partial current-day" bar)
START, END = D1, D3


def ticker_df(rows):
    """One ticker's yfinance-shaped frame. rows: [(date, o, h, l, c, v), ...]."""
    index = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], name="Date")
    data = [[o, h, l, c, round(c * 0.9, 6), v] for (_, o, h, l, c, v) in rows]
    return pd.DataFrame(data, index=index, columns=pd.Index(COLS, name="Price"), dtype=float)


def multi_frame(rows_by_ticker):
    """yfinance 1.x group_by='ticker' shape: MultiIndex (Ticker, Price), NaN-filled."""
    frames = {t: ticker_df(rows) for t, rows in rows_by_ticker.items()}
    return pd.concat(
        list(frames.values()), axis=1, keys=list(frames), names=["Ticker", "Price"], sort=True
    )


def rows_for(*days, base=10.0):
    return [(d, base, base + 1, base - 1, base + 0.5, 1000 + i) for i, d in enumerate(days)]


class FakeYahoo:
    """Injected downloader. data: yahoo ticker -> rows. Unknown tickers come back all-NaN."""

    def __init__(self, data, *, rate_limits=0, always_limited=(), empty_first=None):
        self.data = data
        self.rate_limits = rate_limits
        self.always_limited = set(always_limited)
        self.empty_first = dict(empty_first or {})
        self.calls: list[list[str]] = []

    def __call__(self, tickers, start, end_exclusive):
        self.calls.append(list(tickers))
        if self.rate_limits > 0:
            self.rate_limits -= 1
            raise yahoo.RateLimited("Too Many Requests. Rate limited.")
        if self.always_limited & set(tickers):
            raise yahoo.RateLimited("Too Many Requests. Rate limited.")
        out = {}
        for t in tickers:
            if self.empty_first.get(t, 0) > 0:
                self.empty_first[t] -= 1
                out[t] = []
            else:
                out[t] = self.data.get(t, [])
        return multi_frame(out)


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


def opts(**kw):
    base = dict(start=START, end=END, skip_fx=True)
    base.update(kw)
    return backfill_cmd.Options(**base)


def no_fx(start, end):
    raise AssertionError("FX must not be fetched in this test")


@pytest.fixture
def the_universe(monkeypatch):
    def set_symbols(symbols):
        monkeypatch.setattr(universe, "all_symbols", lambda conn, since: sorted(symbols))

    return set_symbols


def count(conn, table):
    n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    conn.rollback()
    return n


def log_rows(conn):
    rows = conn.execute(
        'SELECT symbol, status, first_date, last_date, "rows", error FROM backfill_log ORDER BY symbol'
    ).fetchall()
    conn.rollback()
    return {r[0]: r[1:] for r in rows}


def bar_rows(conn):
    rows = conn.execute(
        "SELECT symbol, date, open, high, low, close, volume FROM bars ORDER BY symbol, date"
    ).fetchall()
    conn.rollback()
    return rows


# ------------------------------------------------------------ yahoo.py: mapping


def test_symbol_mapping_dot_dash():
    assert yahoo.to_yahoo("BRK.B") == "BRK-B"
    assert yahoo.to_yahoo(" aapl ") == "AAPL"
    assert yahoo.from_yahoo("BRK-B") == "BRK.B"
    assert yahoo.from_yahoo(yahoo.to_yahoo("BF.B")) == "BF.B"


# ------------------------------------------------------- yahoo.py: frame parsing


def test_parse_multi_ticker_frame_uses_close_not_adj_close():
    frame = multi_frame({"AAA": rows_for(D1, D2), "BRK-B": rows_for(D1, base=400.0)})
    out = yahoo.parse_frame(frame, ["AAA", "BRK-B"])
    assert set(out) == {"AAA", "BRK.B"}
    assert [b.date for b in out["AAA"]] == [D1, D2]
    first = out["AAA"][0]
    assert isinstance(first.date, date) and not isinstance(first.date, datetime)
    assert first.close == Decimal("10.5000")  # Close, not Adj Close (9.45)
    assert first.open == Decimal("10.0000")
    assert first.volume == 1000
    assert out["BRK.B"][0].symbol == "BRK.B"
    assert out["BRK.B"][0].close == Decimal("400.5000")


def test_parse_single_ticker_multiindex_frame():
    frame = multi_frame({"SPY": rows_for(D1, D2, D3)})
    out = yahoo.parse_frame(frame, ["SPY"])
    assert [b.date for b in out["SPY"]] == [D1, D2, D3]


def test_parse_single_ticker_flat_frame():
    frame = ticker_df(rows_for(D1, D2))
    out = yahoo.parse_frame(frame, ["SPY"])
    assert [b.date for b in out["SPY"]] == [D1, D2]


def test_parse_flat_frame_is_ambiguous_for_many_tickers():
    frame = ticker_df(rows_for(D1))
    assert yahoo.parse_frame(frame, ["AAA", "BBB"]) == {"AAA": [], "BBB": []}


def test_parse_group_by_column_shape():
    frame = multi_frame({"AAA": rows_for(D1), "BBB": rows_for(D2)})
    frame.columns = frame.columns.swaplevel(0, 1)
    out = yahoo.parse_frame(frame, ["AAA", "BBB"])
    assert [b.date for b in out["AAA"]] == [D1]
    assert [b.date for b in out["BBB"]] == [D2]


def test_parse_drops_nan_and_nonpositive_rows_and_zeroes_nan_volume():
    nan = float("nan")
    frame = multi_frame(
        {
            "AAA": [
                (D1, 10.0, 11.0, 9.0, 10.5, nan),  # NaN volume -> 0
                (D2, nan, 11.0, 9.0, 10.5, 100),  # NaN open -> dropped
                (D3, 10.0, 11.0, 0.0, 10.5, 100),  # non-positive low -> skipped
                (D4, 10.123456, 11.0, 9.0, 10.5, 99.6),  # rounding
            ]
        }
    )
    out = yahoo.parse_frame(frame, ["AAA"])["AAA"]
    assert [b.date for b in out] == [D1, D4]
    assert out[0].volume == 0
    assert out[1].open == Decimal("10.1235")
    assert out[1].volume == 100


def test_parse_tz_aware_index_keeps_exchange_date():
    frame = ticker_df(rows_for(D1, D2))
    frame.index = frame.index.tz_localize("America/New_York")
    out = yahoo.parse_frame(frame, ["AAA"])["AAA"]
    assert [b.date for b in out] == [D1, D2]


def test_parse_absent_or_all_nan_ticker_is_empty():
    frame = multi_frame({"AAA": rows_for(D1), "DEAD": []})
    out = yahoo.parse_frame(frame, ["AAA", "DEAD", "GONE"])
    assert out["DEAD"] == [] and out["GONE"] == []
    assert yahoo.parse_frame(None, ["AAA"]) == {"AAA": []}
    assert yahoo.parse_frame(pd.DataFrame(), ["AAA"]) == {"AAA": []}


def test_download_maps_symbols_both_ways():
    fake = FakeYahoo({"BRK-B": rows_for(D1)})
    out = yahoo.download(["BRK.B", "brk.b"], D1, D4, downloader=fake)
    assert fake.calls == [["BRK-B"]]
    assert list(out) == ["BRK.B"]
    assert out["BRK.B"][0].symbol == "BRK.B"


# ------------------------------------------- yahoo.py: real downloader wrapper


def test_yf_download_turns_logged_rate_limit_into_exception(monkeypatch):
    import yfinance

    def fake_download(**kwargs):
        assert kwargs["auto_adjust"] is False and kwargs["group_by"] == "ticker"
        assert kwargs["threads"] is False and kwargs["actions"] is False
        logging.getLogger("yfinance").error(
            "['SPY']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"
        )
        return multi_frame({"SPY": []})

    monkeypatch.setattr(yfinance, "download", fake_download)
    with pytest.raises(yahoo.RateLimited):
        yahoo.yf_download(["SPY"], D1, D4)


def test_yf_download_turns_raised_rate_limit_into_exception(monkeypatch):
    import yfinance
    from yfinance.exceptions import YFRateLimitError

    def fake_download(**kwargs):
        raise YFRateLimitError()

    monkeypatch.setattr(yfinance, "download", fake_download)
    with pytest.raises(yahoo.RateLimited):
        yahoo.yf_download(["SPY"], D1, D4)


def test_yf_download_other_errors_are_not_rate_limits(monkeypatch):
    import yfinance

    def fake_download(**kwargs):
        logging.getLogger("yfinance").error("['DEAD']: possibly delisted; no timezone found")
        return multi_frame({"DEAD": []})

    monkeypatch.setattr(yfinance, "download", fake_download)
    frame = yahoo.yf_download(["DEAD"], D1, D4)
    assert yahoo.parse_frame(frame, ["DEAD"]) == {"DEAD": []}


# ------------------------------------------------------------- CLI arguments


def parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    backfill_cmd.add_arguments(p)
    return p.parse_args(argv)


def test_arguments_defaults_and_symbol_normalisation():
    args = parse([])
    assert args.start == date(2015, 1, 2) and args.end is None
    assert args.batch_size == 40 and args.symbols is None
    args = parse(["--symbols", "brk-b, aapl,AAPL", "--start", "2020-01-02", "--batch-size", "5"])
    assert args.symbols == ["BRK.B", "AAPL"]
    assert args.start == date(2020, 1, 2) and args.batch_size == 5


def test_arguments_reject_bad_input():
    with pytest.raises(SystemExit):
        parse(["--skip-fx", "--fx-only"])
    with pytest.raises(SystemExit):
        parse(["--batch-size", "0"])
    with pytest.raises(SystemExit):
        parse(["--start", "01/02/2015"])


def test_options_default_end_is_last_completed_session():
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    o = backfill_cmd.options_from_args(parse(["--dry-run"]), now=now)
    assert o.end == dates.last_completed_session(now)
    assert o.dry_run is True and o.symbols is None
    with pytest.raises(backfill_cmd.BackfillError):
        backfill_cmd.options_from_args(parse(["--start", "2030-01-02"]), now=now)


# ----------------------------------------------------------- backfill (DB)


def test_batches_and_resume_skip_ok(pg, the_universe):
    the_universe(["AAA", "BBB", "CCC", "DDD", "SPY"])
    pg.execute(
        "INSERT INTO backfill_log (symbol, status, first_date, last_date, \"rows\") "
        "VALUES ('AAA', 'ok', %s, %s, 3)",
        (D1, D3),
    )
    pg.commit()
    data = {t: rows_for(D1, D2, D3) for t in ["AAA", "BBB", "CCC", "DDD", "SPY"]}
    fake, sleeps = FakeYahoo(data), Sleeps()

    s = backfill_cmd.backfill(pg, opts(batch_size=2), downloader=fake, sleep=sleeps, fetch_fx=no_fx)

    assert fake.calls == [["BBB", "CCC"], ["DDD", "SPY"]]
    assert sleeps == [backfill_cmd.BATCH_PAUSE_S]
    assert s.ok == ["BBB", "CCC", "DDD", "SPY"] and s.skipped == 1
    assert s.rows_written == 12 and s.exit_code() == 0
    assert count(pg, "bars") == 12
    logged = log_rows(pg)
    assert logged["SPY"] == ("ok", D1, D3, 3, None)

    # Second run: everything is logged ok -> nothing fetched.
    fake2 = FakeYahoo(data)
    s2 = backfill_cmd.backfill(pg, opts(batch_size=2), downloader=fake2, sleep=Sleeps(), fetch_fx=no_fx)
    assert fake2.calls == [] and s2.skipped == 5 and s2.rows_written == 0


def test_date_filter_drops_bars_outside_start_end(pg):
    fake = FakeYahoo({"AAA": rows_for(D0, D1, D2, D3, D4)})
    s = backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert s.rows_fetched == 3
    assert [r[1] for r in bar_rows(pg)] == [D1, D2, D3]
    assert log_rows(pg)["AAA"][:4] == ("ok", D1, D3, 3)


def test_dot_symbols_fetched_as_dash_and_stored_as_dot(pg):
    fake = FakeYahoo({"BRK-B": rows_for(D1, base=400.0)})
    backfill_cmd.backfill(pg, opts(symbols=("BRK.B",)), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert fake.calls == [["BRK-B"]]
    assert {r[0] for r in bar_rows(pg)} == {"BRK.B"}
    assert "BRK.B" in log_rows(pg)


def test_rate_limit_backoff_then_success(pg):
    fake, sleeps = FakeYahoo({"AAA": rows_for(D1)}, rate_limits=2), Sleeps()
    s = backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=fake, sleep=sleeps, fetch_fx=no_fx)
    assert sleeps == [60.0, 120.0]
    assert len(fake.calls) == 3 and s.ok == ["AAA"]


def test_rate_limit_exhausted_marks_batch_failed_and_continues(pg):
    data = {t: rows_for(D1) for t in ["AAA", "BBB", "CCC"]}
    fake, sleeps = FakeYahoo(data, always_limited={"AAA"}), Sleeps()
    s = backfill_cmd.backfill(
        pg, opts(symbols=("AAA", "BBB", "CCC"), batch_size=2), downloader=fake, sleep=sleeps, fetch_fx=no_fx
    )
    assert sleeps == [60.0, 120.0, 240.0, backfill_cmd.BATCH_PAUSE_S]
    assert fake.calls == [["AAA", "BBB"]] * 4 + [["CCC"]]
    assert s.failed == ["AAA", "BBB"] and s.ok == ["CCC"] and s.exit_code() == 1
    logged = log_rows(pg)
    assert logged["AAA"][0] == "failed" and "rate limited" in logged["AAA"][4]
    assert [r[0] for r in bar_rows(pg)] == ["CCC"]


def test_failed_attempt_never_downgrades_an_ok_symbol(pg):
    fake = FakeYahoo({"AAA": rows_for(D1)})
    backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    limited = FakeYahoo({}, always_limited={"AAA"})
    backfill_cmd.backfill(pg, opts(symbols=("AAA",)), downloader=limited, sleep=Sleeps(), fetch_fx=no_fx)
    assert log_rows(pg)["AAA"][0] == "ok"
    assert count(pg, "bars") == 1


def test_empty_symbol_retried_individually_then_logged_empty(pg):
    fake, sleeps = FakeYahoo({"AAA": rows_for(D1, D2)}), Sleeps()
    s = backfill_cmd.backfill(
        pg, opts(symbols=("AAA", "DEAD")), downloader=fake, sleep=sleeps, fetch_fx=no_fx
    )
    assert fake.calls == [["AAA", "DEAD"], ["DEAD"]]
    assert sleeps == [backfill_cmd.BATCH_PAUSE_S]
    assert s.ok == ["AAA"] and s.empty == ["DEAD"] and s.exit_code() == 0
    status, first, last, n, error = log_rows(pg)["DEAD"]
    assert (status, first, last, n) == ("empty", None, None, 0)
    assert "no bars" in error


def test_empty_in_batch_recovered_by_individual_retry(pg):
    fake = FakeYahoo({"AAA": rows_for(D1), "BBB": rows_for(D1)}, empty_first={"BBB": 1})
    s = backfill_cmd.backfill(pg, opts(symbols=("AAA", "BBB")), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert s.ok == ["AAA", "BBB"] and s.empty == []


def test_retry_failed_reattempts_failed_and_empty_only(pg, the_universe):
    the_universe(["AAA", "BBB", "CCC", "SPY"])
    pg.execute(
        "INSERT INTO backfill_log (symbol, status, \"rows\") VALUES "
        "('AAA', 'ok', 1), ('BBB', 'failed', 0), ('CCC', 'empty', 0)"
    )
    pg.commit()
    data = {t: rows_for(D1) for t in ["AAA", "BBB", "CCC", "SPY"]}

    plain = FakeYahoo(data)
    backfill_cmd.backfill(pg, opts(), downloader=plain, sleep=Sleeps(), fetch_fx=no_fx)
    assert plain.calls == [["SPY"]]

    retry = FakeYahoo(data)
    s = backfill_cmd.backfill(pg, opts(retry_failed=True), downloader=retry, sleep=Sleeps(), fetch_fx=no_fx)
    assert retry.calls == [["BBB", "CCC"]]
    assert s.ok == ["BBB", "CCC"]
    assert log_rows(pg)["BBB"][0] == "ok"


def test_second_run_with_same_args_writes_zero_rows(pg):
    data = {"AAA": rows_for(D1, D2, D3), "BRK-B": rows_for(D1, D2, base=400.0)}
    o = opts(symbols=("AAA", "BRK.B"), skip_fx=False)
    fx_rows = [(D1, Decimal("15500.0000")), (D2, Decimal("15510.5000"))]

    s1 = backfill_cmd.backfill(pg, o, downloader=FakeYahoo(data), sleep=Sleeps(), fetch_fx=lambda a, b: fx_rows)
    before = bar_rows(pg)
    logged_before = log_rows(pg)
    s2 = backfill_cmd.backfill(pg, o, downloader=FakeYahoo(data), sleep=Sleeps(), fetch_fx=lambda a, b: fx_rows)

    assert s1.rows_written == 5 and s1.fx_rows_written == 2
    assert s2.rows_written == 0 and s2.fx_rows_written == 0
    assert bar_rows(pg) == before
    assert log_rows(pg) == logged_before


def test_dry_run_writes_nothing(pg, the_universe):
    the_universe(["AAA", "SPY"])
    data = {"AAA": rows_for(D1, D2), "SPY": rows_for(D1, D2)}
    fx_rows = [(D1, Decimal("15500.0000"))]
    s = backfill_cmd.backfill(
        pg,
        opts(dry_run=True, skip_fx=False),
        downloader=FakeYahoo(data),
        sleep=Sleeps(),
        fetch_fx=lambda a, b: fx_rows,
    )
    assert s.rows_written == 4 and s.fx_rows_written == 1  # computed, then rolled back
    assert count(pg, "bars") == 0
    assert count(pg, "backfill_log") == 0
    assert count(pg, "fx_rates") == 0


def test_demo_purge_runs_before_any_write(pg, monkeypatch):
    events = []
    real_upsert_bars, real_upsert_fx = bars.upsert_bars, fx.upsert_fx

    def fake_purge(conn, dry_run):
        events.append(("purge", dry_run))
        return False

    def spy_upsert_bars(conn, rows):
        events.append(("bars",))
        return real_upsert_bars(conn, rows)

    def spy_upsert_fx(conn, rows):
        events.append(("fx",))
        return real_upsert_fx(conn, rows)

    monkeypatch.setattr(demo, "purge_demo_if_needed", fake_purge)
    monkeypatch.setattr(bars, "upsert_bars", spy_upsert_bars)
    monkeypatch.setattr(fx, "upsert_fx", spy_upsert_fx)

    backfill_cmd.backfill(
        pg,
        opts(symbols=("AAA",), skip_fx=False),
        downloader=FakeYahoo({"AAA": rows_for(D1)}),
        sleep=Sleeps(),
        fetch_fx=lambda a, b: [(D1, Decimal("15500"))],
    )
    assert events == [("purge", False), ("bars",), ("fx",)]


def test_empty_universe_fails_clearly_before_any_write(pg, the_universe, monkeypatch):
    the_universe(["SPY"])
    purged = []
    monkeypatch.setattr(demo, "purge_demo_if_needed", lambda conn, dry_run: purged.append(1))
    fake = FakeYahoo({})
    with pytest.raises(backfill_cmd.BackfillError, match="universe refresh"):
        backfill_cmd.backfill(pg, opts(), downloader=fake, sleep=Sleeps(), fetch_fx=no_fx)
    assert fake.calls == [] and purged == []


def test_fx_only_loads_fx_and_skips_bars(pg, monkeypatch):
    def no_universe(conn, since):
        raise AssertionError("universe must not be read with --fx-only")

    monkeypatch.setattr(universe, "all_symbols", no_universe)
    fake = FakeYahoo({})
    s = backfill_cmd.backfill(
        pg,
        opts(fx_only=True, skip_fx=False),
        downloader=fake,
        sleep=Sleeps(),
        fetch_fx=lambda a, b: [(D1, Decimal("15500")), (D2, Decimal("15600"))],
    )
    assert fake.calls == [] and s.fx_rows_written == 2
    assert count(pg, "fx_rates") == 2 and count(pg, "bars") == 0


def test_fx_failure_is_reported_not_raised(pg):
    def broken(start, end):
        raise RuntimeError("frankfurter down")

    s = backfill_cmd.backfill(
        pg,
        opts(symbols=("AAA",), skip_fx=False),
        downloader=FakeYahoo({"AAA": rows_for(D1)}),
        sleep=Sleeps(),
        fetch_fx=broken,
    )
    assert s.ok == ["AAA"] and "frankfurter down" in s.fx_error and s.exit_code() == 1
    assert count(pg, "bars") == 1


def test_summary_reports_counts_and_table_size(pg):
    s = backfill_cmd.backfill(
        pg, opts(symbols=("AAA", "DEAD")), downloader=FakeYahoo({"AAA": rows_for(D1)}),
        sleep=Sleeps(), fetch_fx=no_fx,
    )
    assert s.bars_bytes is not None and s.bars_bytes > 0
    text = backfill_cmd.format_summary(s, opts(symbols=("AAA", "DEAD")))
    assert "1 ok, 1 empty, 0 failed" in text
    assert "empty: DEAD" in text
    assert "bars table:" in text
