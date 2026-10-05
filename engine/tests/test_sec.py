"""The SEC EDGAR client: contact handling, request shape, pacing, retries, parsing (no network)."""

from __future__ import annotations

from datetime import date

import pytest
import requests

from seer_engine import config, sec
from seer_engine.sec import Client, Fact, SecError, SecNotFound

CONTACT = "seer-tests@example.test"
CIK = 718877  # ATVI


class FakeClock:
    def __init__(self) -> None:
        self.t = 100.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


class _Resp:
    def __init__(self, status: int, body=None, text: str | None = None, headers: dict | None = None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else ("" if body is None else str(body))
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeTransport:
    """Pops one queued response (or raises one queued exception) per GET; ``took`` moves the clock."""

    def __init__(self, *items, clock: FakeClock | None = None, took: float = 0.0):
        self.queue = list(items)
        self.calls: list[dict] = []
        self.clock = clock
        self.took = took

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers), "timeout": timeout})
        if self.clock is not None:
            self.clock.t += self.took
        item = self.queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def make(transport: FakeTransport, clock: FakeClock | None = None, **kw) -> tuple[Client, FakeClock]:
    clock = clock or transport.clock or FakeClock()
    return Client(CONTACT, transport=transport, clock=clock.now, sleep=clock.sleep, **kw), clock


# --- fixture payloads ---------------------------------------------------------------------------

ATVI_FACTS = {
    "cik": 718877,
    "entityName": "Activision Blizzard, Inc.",
    "facts": {
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "label": "Entity Common Stock, Shares Outstanding",
                "units": {
                    "shares": [
                        {
                            "end": "2023-07-31", "val": 786585469,
                            "accn": "0000718877-23-000068", "fy": 2023, "fp": "Q2",
                            "form": "10-Q", "filed": "2023-08-03",
                        }
                    ]
                },
            }
        },
        "us-gaap": {
            "Assets": {
                "label": "Assets",
                "units": {
                    "USD": [
                        {
                            "end": "2022-12-31", "val": 27383000000,
                            "accn": "0000718877-23-000018", "fy": 2022, "fp": "FY",
                            "form": "10-K", "filed": "2023-02-23", "frame": "CY2022Q4I",
                        },
                        {
                            "end": "2022-12-31", "val": 27400000000,
                            "accn": "0000718877-23-000068", "fy": 2023, "fp": "Q2",
                            "form": "10-Q", "filed": "2023-08-03",
                        },
                        {
                            "end": "2023-06-30", "val": 28000000000,
                            "accn": "0000718877-23-000068", "fy": 2023, "fp": "Q2",
                            "form": "10-Q", "filed": "2023-08-03",
                        },
                    ]
                },
            },
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "start": "2023-01-01", "end": "2023-06-30", "val": 4576000000,
                            "accn": "0000718877-23-000068", "fy": 2023, "fp": "Q2",
                            "form": "10-Q", "filed": "2023-08-03",
                        }
                    ]
                }
            },
        },
        "srt": {
            "NoiseTag": {
                "units": {
                    "USD": [
                        {
                            "end": "2023-06-30", "val": 1, "accn": "0000718877-23-000068",
                            "form": "10-Q", "filed": "2023-08-03",
                        }
                    ]
                }
            }
        },
    },
}

ASSETS_CONCEPT = {
    "cik": 718877,
    "taxonomy": "us-gaap",
    "tag": "Assets",
    "label": "Assets",
    "entityName": "Activision Blizzard, Inc.",
    "units": {
        "USD": [
            {
                "end": "2009-06-30", "val": 13240000000, "accn": "0001193125-09-167291",
                "fy": 2009, "fp": "Q2", "form": "10-Q", "filed": "2009-08-07",
            },
            {
                "end": "2023-06-30", "val": 28000000000, "accn": "0000718877-23-000068",
                "fy": 2023, "fp": "Q2", "form": "10-Q", "filed": "2023-07-31",
            },
        ]
    },
}


# --- configuration ------------------------------------------------------------------------------


def test_require_contact_reads_the_setting(monkeypatch):
    monkeypatch.setenv(sec.CONTACT_SETTING, f"  {CONTACT} ")
    monkeypatch.setattr(sec.config, "_loaded", True)
    assert sec.require_contact() == CONTACT


@pytest.mark.parametrize("value", ["", "   ", "not-an-email", "@example.test", "nobody@"])
def test_require_contact_refuses_an_unusable_address(monkeypatch, value):
    monkeypatch.setenv(sec.CONTACT_SETTING, value)
    monkeypatch.setattr(sec.config, "_loaded", True)
    with pytest.raises(config.ConfigError):
        sec.require_contact()


def test_require_contact_unset_is_a_config_error(monkeypatch):
    monkeypatch.delenv(sec.CONTACT_SETTING, raising=False)
    monkeypatch.setattr(sec.config, "_loaded", True)
    with pytest.raises(config.ConfigError):
        sec.require_contact()


def test_empty_contact_is_refused():
    with pytest.raises(ValueError):
        Client("", transport=FakeTransport())
    with pytest.raises(ValueError):
        Client("   ", transport=FakeTransport())


def test_contact_never_in_repr():
    c, _ = make(FakeTransport())
    assert CONTACT not in repr(c)


def test_user_agent_carries_the_version_and_the_contact():
    ua = sec.user_agent(CONTACT)
    assert CONTACT in ua and ua.startswith("seer-engine/")


def test_scrub_removes_the_contact_and_any_token():
    assert sec.scrub(f"hi {CONTACT} ?token=xyz", CONTACT) == "hi REDACTED ?token=REDACTED"
    assert sec.scrub("plain", None) == "plain"


# --- cik10 --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (320193, "0000320193"),
        ("320193", "0000320193"),
        ("0000320193", "0000320193"),
        ("CIK0000320193", "0000320193"),
        ("cik320193", "0000320193"),
        (" 718877 ", "0000718877"),
        ("1234567890", "1234567890"),
    ],
)
def test_cik10_normalises(value, expected):
    assert sec.cik10(value) == expected


@pytest.mark.parametrize("value", ["", "AAPL", "12a45", "12 345", "12345678901", "../etc", "٣٢٠"])
def test_cik10_refuses_a_non_cik(value):
    with pytest.raises(ValueError):
        sec.cik10(value)


# --- request shape ------------------------------------------------------------------------------


def test_companyfacts_request_shape():
    t = FakeTransport(_Resp(200, ATVI_FACTS))
    c, _ = make(t)
    c.company_facts(CIK)
    [call] = t.calls
    assert call["url"] == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000718877.json"
    assert call["params"] == {}
    assert call["headers"]["User-Agent"] == sec.user_agent(CONTACT)
    assert CONTACT in call["headers"]["User-Agent"]
    assert call["headers"]["Accept"] == "application/json"
    assert call["timeout"] == sec.DEFAULT_TIMEOUT_S


def test_companyconcept_request_shape():
    t = FakeTransport(_Resp(200, ASSETS_CONCEPT))
    c, _ = make(t, timeout=4.0)
    c.company_concept(CIK, "us-gaap", "Assets")
    [call] = t.calls
    assert call["url"] == "https://data.sec.gov/api/xbrl/companyconcept/CIK0000718877/us-gaap/Assets.json"
    assert call["timeout"] == 4.0


@pytest.mark.parametrize("bad", ["", "us gaap", "../../secrets", "Assets/x"])
def test_companyconcept_refuses_an_unsafe_path_segment(bad):
    c, _ = make(FakeTransport())
    with pytest.raises(ValueError):
        c.company_concept(CIK, bad, "Assets")
    with pytest.raises(ValueError):
        c.company_concept(CIK, "us-gaap", bad)


def test_contact_not_in_logs(caplog):
    caplog.set_level("DEBUG", logger="seer_engine.sec")
    t = FakeTransport(_Resp(200, ATVI_FACTS), _Resp(200, ASSETS_CONCEPT))
    c, _ = make(t)
    c.company_facts(CIK)
    c.company_concept(CIK, "us-gaap", "Assets")
    assert caplog.text and CONTACT not in caplog.text


# --- pacing -------------------------------------------------------------------------------------


def test_first_call_does_not_wait_and_calls_are_spaced_by_min_interval():
    t = FakeTransport(*[_Resp(200, ATVI_FACTS) for _ in range(3)])
    c, clock = make(t)
    for _ in range(3):
        c.company_facts(CIK)
    # approx, as the sibling test below: a wait is `last + MIN_INTERVAL - now`, so the float
    # arithmetic lands at 0.10999999999999943 rather than literally 0.11.
    assert clock.sleeps == [pytest.approx(sec.MIN_INTERVAL), pytest.approx(sec.MIN_INTERVAL)]
    assert c.calls == 3


def test_spacing_counts_from_the_end_of_the_previous_call():
    clock = FakeClock()
    t = FakeTransport(_Resp(200, ATVI_FACTS), _Resp(200, ATVI_FACTS), clock=clock, took=0.03)
    c, _ = make(t, clock)
    c.company_facts(CIK)
    clock.t += 0.04  # caller work (the database write) between calls
    c.company_facts(CIK)
    # the 0.03 s the request itself took does not count; the 0.04 s after it does
    assert clock.sleeps == [pytest.approx(sec.MIN_INTERVAL - 0.04)]


def test_no_wait_when_enough_time_has_passed():
    clock = FakeClock()
    t = FakeTransport(_Resp(200, ATVI_FACTS), _Resp(200, ATVI_FACTS))
    c, _ = make(t, clock)
    c.company_facts(CIK)
    clock.t += 5.0
    c.company_facts(CIK)
    assert clock.sleeps == []


def test_sustained_rate_stays_under_ten_per_second():
    """The exit criterion: no two requests start less than MIN_INTERVAL apart, so <= 10 req/s."""
    clock = FakeClock()
    starts: list[float] = []

    class Recording(FakeTransport):
        def get(self, url, *, params, headers, timeout):
            starts.append(clock.t)
            return super().get(url, params=params, headers=headers, timeout=timeout)

    t = Recording(*[_Resp(200, ATVI_FACTS) for _ in range(12)], clock=clock, took=0.02)
    c, _ = make(t, clock)
    for _ in range(12):
        c.company_facts(CIK)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(g >= sec.MIN_INTERVAL - 1e-9 for g in gaps)
    assert len(gaps) / (starts[-1] - starts[0]) <= 10.0
    assert sec.MIN_INTERVAL >= 0.1


# --- retries and errors ---------------------------------------------------------------------------


def test_5xx_is_retried_with_exponential_backoff_then_succeeds():
    t = FakeTransport(_Resp(503, text="busy"), _Resp(503, text="busy"), _Resp(200, ATVI_FACTS))
    c, clock = make(t)
    assert len(c.company_facts(CIK)) == 5
    assert len(t.calls) == 3
    assert clock.sleeps == [sec.BACKOFF_S, sec.BACKOFF_S * 2]


def test_429_honours_a_longer_retry_after():
    t = FakeTransport(_Resp(429, text="rate", headers={"Retry-After": "7"}), _Resp(200, ATVI_FACTS))
    c, clock = make(t)
    c.company_facts(CIK)
    assert clock.sleeps == [7.0]


def test_retry_after_shorter_than_backoff_uses_backoff():
    t = FakeTransport(_Resp(429, text="rate", headers={"Retry-After": "0"}), _Resp(200, ATVI_FACTS))
    c, clock = make(t)
    c.company_facts(CIK)
    assert clock.sleeps == [sec.BACKOFF_S]


def test_retry_after_is_capped():
    t = FakeTransport(_Resp(429, text="rate", headers={"Retry-After": "86400"}), _Resp(200, ATVI_FACTS))
    c, clock = make(t)
    c.company_facts(CIK)
    assert clock.sleeps == [sec.MAX_RETRY_AFTER_S]


def test_exhausted_retries_raise_with_the_status():
    t = FakeTransport(*[_Resp(502, text="bad gateway") for _ in range(4)])
    c, _ = make(t)
    with pytest.raises(SecError) as exc:
        c.company_facts(CIK)
    assert exc.value.status == 502
    assert len(t.calls) == 4  # the first attempt plus RETRIES


def test_timeout_is_retried_then_raises():
    t = FakeTransport(*[requests.Timeout("read timed out") for _ in range(4)])
    c, clock = make(t)
    with pytest.raises(SecError, match="Timeout") as exc:
        c.company_facts(CIK)
    assert exc.value.status is None
    assert len(t.calls) == 4 and len(clock.sleeps) == 3


def test_connection_error_then_success():
    t = FakeTransport(requests.ConnectionError("refused"), _Resp(200, ATVI_FACTS))
    c, _ = make(t)
    assert len(c.company_facts(CIK)) == 5
    assert len(t.calls) == 2


def test_404_is_sec_not_found_and_is_not_retried():
    t = FakeTransport(_Resp(404, text="Not Found"))
    c, clock = make(t)
    with pytest.raises(SecNotFound) as exc:
        c.company_facts(CIK)
    assert exc.value.status == 404
    assert isinstance(exc.value, SecError)  # phase 4 catches SecError and tests for SecNotFound
    assert len(t.calls) == 1 and clock.sleeps == []


def test_403_is_not_retried_and_names_the_setting_without_echoing_the_contact():
    t = FakeTransport(_Resp(403, text=f"Undeclared automated tool. Your agent: {CONTACT}"))
    c, clock = make(t)
    with pytest.raises(SecError) as exc:
        c.company_facts(CIK)
    assert exc.value.status == 403
    assert sec.CONTACT_SETTING in str(exc.value)
    assert CONTACT not in str(exc.value) and "REDACTED" in str(exc.value)
    assert len(t.calls) == 1 and clock.sleeps == []


def test_non_json_200_raises():
    t = FakeTransport(_Resp(200, None, text="<html>"))
    c, _ = make(t)
    with pytest.raises(SecError, match="non-JSON"):
        c.company_facts(CIK)
    assert len(t.calls) == 1


def test_a_json_array_body_raises():
    c, _ = make(FakeTransport(_Resp(200, [])))
    with pytest.raises(SecError, match="unexpected list"):
        c.company_facts(CIK)


def test_a_body_for_another_cik_raises():
    c, _ = make(FakeTransport(_Resp(200, {**ATVI_FACTS, "cik": 320193})))
    with pytest.raises(SecError, match="body is for CIK0000320193"):
        c.company_facts(CIK)


# --- parsing ---------------------------------------------------------------------------------------


def test_company_facts_flattens_the_document():
    c, _ = make(FakeTransport(_Resp(200, ATVI_FACTS)))
    out = c.company_facts(CIK)
    assert out.cik == "0000718877"
    assert out.entity_name == "Activision Blizzard, Inc."
    assert len(out) == 5  # 1 dei + 3 us-gaap:Assets + 1 us-gaap:Revenues; srt dropped
    assert out.tags() == (
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "Assets"),
        ("us-gaap", "Revenues"),
    )


def test_facts_are_sorted_deterministically():
    out = sec.parse_company_facts(ATVI_FACTS, CIK)
    assert [(f.taxonomy, f.tag, f.period_end, f.filed) for f in out.facts] == [
        ("dei", "EntityCommonStockSharesOutstanding", date(2023, 7, 31), date(2023, 8, 3)),
        ("us-gaap", "Assets", date(2022, 12, 31), date(2023, 2, 23)),
        ("us-gaap", "Assets", date(2022, 12, 31), date(2023, 8, 3)),
        ("us-gaap", "Assets", date(2023, 6, 30), date(2023, 8, 3)),
        ("us-gaap", "Revenues", date(2023, 6, 30), date(2023, 8, 3)),
    ]
    assert sec.parse_company_facts(ATVI_FACTS, CIK).facts == out.facts


def test_a_restatement_is_a_second_fact_not_an_overwrite():
    out = sec.parse_company_facts(ATVI_FACTS, CIK, tags=["Assets"])
    same_period = [f for f in out.facts if f.period_end == date(2022, 12, 31)]
    assert len(same_period) == 2
    assert {f.accn for f in same_period} == {"0000718877-23-000018", "0000718877-23-000068"}
    assert {f.val for f in same_period} == {27383000000.0, 27400000000.0}
    assert {f.filed for f in same_period} == {date(2023, 2, 23), date(2023, 8, 3)}


def test_an_instantaneous_fact_has_no_period_start_and_a_duration_fact_does():
    out = sec.parse_company_facts(ATVI_FACTS, CIK)
    assets = next(f for f in out.facts if f.tag == "Assets")
    revenues = next(f for f in out.facts if f.tag == "Revenues")
    assert assets.period_start is None
    assert revenues.period_start == date(2023, 1, 1)


def test_fields_are_carried_through_verbatim():
    out = sec.parse_company_facts(ATVI_FACTS, CIK, tags=["Revenues"])
    assert out.facts == (
        Fact(
            cik="0000718877",
            taxonomy="us-gaap",
            tag="Revenues",
            unit="USD",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 6, 30),
            val=4576000000.0,
            accn="0000718877-23-000068",
            form="10-Q",
            fy=2023,
            fp="Q2",
            filed=date(2023, 8, 3),
            frame=None,
        ),
    )


def test_the_frame_label_is_kept_when_edgar_assigns_one():
    out = sec.parse_company_facts(ATVI_FACTS, CIK, tags=["Assets"])
    assert {f.frame for f in out.facts} == {"CY2022Q4I", None}


def test_default_taxonomies_drop_everything_but_us_gaap_and_dei():
    out = sec.parse_company_facts(ATVI_FACTS, CIK)
    assert "srt" not in {f.taxonomy for f in out.facts}
    assert sec.TAXONOMIES == ("us-gaap", "dei")


def test_taxonomies_none_keeps_every_branch():
    out = sec.parse_company_facts(ATVI_FACTS, CIK, taxonomies=None)
    assert ("srt", "NoiseTag") in out.tags()
    assert len(out) == 6


def test_tags_narrows_across_taxonomies():
    out = sec.parse_company_facts(
        ATVI_FACTS, CIK, tags=["Assets", "EntityCommonStockSharesOutstanding"]
    )
    assert out.tags() == (
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "Assets"),
    )
    assert len(out) == 4


def test_a_filer_with_no_xbrl_taxonomy_is_empty_not_an_error():
    for payload in ({"cik": 718877, "entityName": "Dead Co", "facts": {}},
                    {"cik": 718877, "entityName": "Dead Co"},
                    {"cik": 718877, "entityName": "Dead Co", "facts": {"ifrs-full": {}}}):
        out = sec.parse_company_facts(payload, CIK)
        assert out.facts == () and out.entity_name == "Dead Co" and out.cik == "0000718877"


def test_malformed_rows_are_dropped_and_the_rest_kept():
    payload = {
        "cik": 718877,
        "entityName": "Messy Co",
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {"end": "2022-12-31", "val": 1.0, "accn": "a", "form": "10-K", "filed": "2023-02-23"},
                            {"end": "2022-12-31", "accn": "b", "form": "10-K", "filed": "2023-02-23"},
                            {"end": "2022-12-31", "val": None, "accn": "c", "form": "10-K", "filed": "2023-02-23"},
                            {"end": "2022-12-31", "val": True, "accn": "d", "form": "10-K", "filed": "2023-02-23"},
                            {"end": "not-a-date", "val": 1.0, "accn": "e", "form": "10-K", "filed": "2023-02-23"},
                            {"end": "2022-12-31", "val": 1.0, "accn": "f", "form": "10-K"},
                            {"end": "2022-12-31", "val": 1.0, "accn": "", "form": "10-K", "filed": "2023-02-23"},
                            {"end": "2022-12-31", "val": 1.0, "accn": "h", "form": " ", "filed": "2023-02-23"},
                            "not an object",
                        ],
                        "bad-rows": {"not": "a list"},
                    }
                },
                "Liabilities": {"units": None},
                "Equity": "not an object",
            },
            "dei": "not an object",
        },
    }
    out = sec.parse_company_facts(payload, CIK)
    assert [f.accn for f in out.facts] == ["a"]


def test_fy_and_fp_are_optional():
    payload = {
        "cik": 718877,
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {"end": "2022-12-31", "val": 1.0, "accn": "a", "form": "10-K",
                             "filed": "2023-02-23", "fy": "2022", "fp": 4},
                        ]
                    }
                }
            }
        },
    }
    [fact] = sec.parse_company_facts(payload, CIK).facts
    assert fact.fy is None and fact.fp is None


def test_facts_are_frozen_and_hashable():
    [fact] = sec.parse_company_facts(ATVI_FACTS, CIK, tags=["Revenues"]).facts
    assert {fact, fact} == {fact}
    with pytest.raises(AttributeError):
        fact.val = 0.0  # type: ignore[misc]


# --- company_concept -------------------------------------------------------------------------------


def test_company_concept_parses_the_narrow_document():
    c, _ = make(FakeTransport(_Resp(200, ASSETS_CONCEPT)))
    out = c.company_concept(CIK, "us-gaap", "Assets")
    assert out.cik == "0000718877"
    assert out.entity_name == "Activision Blizzard, Inc."
    assert [f.filed for f in out.facts] == [date(2009, 8, 7), date(2023, 7, 31)]
    assert {(f.taxonomy, f.tag, f.unit) for f in out.facts} == {("us-gaap", "Assets", "USD")}


def test_company_concept_for_a_dead_filer_returns_its_whole_history():
    """EDGAR is an archive: there is no delisted error case."""
    c, _ = make(FakeTransport(_Resp(200, ASSETS_CONCEPT)))
    out = c.company_concept(CIK, "us-gaap", "Assets")
    assert min(f.filed for f in out.facts) == date(2009, 8, 7)
    assert max(f.filed for f in out.facts) == date(2023, 7, 31)


def test_company_concept_body_for_another_cik_raises():
    c, _ = make(FakeTransport(_Resp(200, {**ASSETS_CONCEPT, "cik": 1418091})))
    with pytest.raises(SecError, match="body is for CIK0001418091"):
        c.company_concept(CIK, "us-gaap", "Assets")


# --- the module-level session is left alone ----------------------------------------------------------


def test_the_shared_http_session_never_gets_the_contact():
    """Massive and Finnhub must keep the contact-free User-Agent."""
    from seer_engine import http as http_mod

    before = dict(http_mod._session.headers)
    c, _ = make(FakeTransport(_Resp(200, ATVI_FACTS)))
    c.company_facts(CIK)
    assert dict(http_mod._session.headers) == before
    assert CONTACT not in http_mod._session.headers.get("User-Agent", "")


def test_the_default_transport_is_its_own_session():
    from seer_engine import http as http_mod

    client = Client(CONTACT)
    assert client._transport is not http_mod._session
    assert client._transport.headers["User-Agent"] == sec.user_agent(CONTACT)
    assert http_mod._session.headers["User-Agent"] == http_mod.USER_AGENT
