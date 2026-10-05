"""One-off generator for engine/data/ticker_cik.csv. Run by hand, never imported.

    export MASSIVE_API_KEY=...  SEC_CONTACT_EMAIL=you@example.com
    python engine/scripts/build_ticker_cik.py --out engine/data/ticker_cik.csv

Every network artifact is cached under --cache (default engine/.cache/cik, gitignored), so a
re-run after editing MANUAL costs nothing. Tier order, highest first:

  0 manual   MANUAL below -- hand-audited, wins over everything
  1 current  https://www.sec.gov/files/company_tickers.json
  2 edgar    https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<ticker>&output=atom
  3 exact    Massive delisted reference -> company name -> cik-lookup-data.txt, suffixes stripped
  4 fuzzy    the same, difflib ratio >= 0.90

Measured 2026-10-05 over the 913 ever-members since cik.SINCE = 2009-01-01: MANUAL covers
152 symbols, tier 1 resolves 628 of the rest, tier 2 a further 49, leaving
84 for tiers 3-4.

A ticker alone never identifies a company: tiers 1-2 answer with whoever holds the ticker TODAY,
and tiers 1-4 take their start from spans(), which clips membership to [SINCE, ...). Two screens
guard the result, and neither is a gate:

  SCREEN  a candidate must have filed a periodic report somewhere inside the symbol's span. It
          rejected the wrong answers for MON, PLL and ALTR but NOT for LLL, DTV or HAR, so the
          six recycled tickers and the one fuzzy match stay in MANUAL permanently.
  EARLY   a candidate must also have filed one within EARLY_WINDOW_DAYS of the span's START.
          Lowering SINCE from 2015-01-02 to 2009-01-01 moved 541 starts backwards, and SCREEN
          cannot see a start that reaches back past a handover because the later filings still
          fall inside the span. EARLY can, whenever the earlier holder's successor did not exist
          yet -- Q, DELL, CEG, MRVL, SNDK among them. It still cannot see a handover between two
          filers that both reported throughout; GOLD (Randgold, now Barrick) and S (Sprint
          Nextel, now SentinelOne) are that case and are in MANUAL for it.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from seer_engine import config, http, membership  # noqa: E402
from seer_engine.cik import HEADER, NO_FILER, SINCE  # noqa: E402

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CIK_LOOKUP_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
BROWSE_EDGAR_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
MASSIVE_TICKERS_URL = "https://api.massive.com/v3/reference/tickers"

SEC_MIN_INTERVAL = 0.15  # SEC allows 10 req/s; stay under it
MASSIVE_MIN_INTERVAL = 12.5  # free tier: 5 calls/min
MASSIVE_MAX_PAGES = 50
FUZZY_CUTOFF = 0.90
PERIODIC_FORMS = frozenset({"10-K", "10-K405", "10-KSB", "10-Q", "20-F", "40-F"})

#: The second screen's window. A row's CIK must have filed a periodic report within this many
#: days of the span's start, not merely somewhere inside it. A quarterly filer files 3-5 in the
#: window and an annual-only foreign private issuer (20-F) files 1, so a zero means the filer
#: was not reporting when the span opens -- the signature of a start extended back past a
#: handover, which the first screen cannot see because the later filings still fall inside.
EARLY_WINDOW_DAYS = 450

SUFFIXES = (
    "INC", "CORP", "CORPORATION", "CO", "COMPANY", "PLC", "LTD", "LIMITED", "LP", "LLC",
    "HOLDINGS", "HOLDING", "GROUP", "THE", "CLASS A", "CLASS B", "CLASS C", "COM", "NEW",
)
_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_SPACE = re.compile(r"\s+")

# symbol -> ((cik, start, end, company_name, note), ...).
#
# ``start`` empty means "the symbol's membership start, from spans()" -- the sentinel. Use it
# whenever the filer held the ticker for the whole of the symbol's membership; write a literal
# date only when the tenure genuinely begins later than the membership does (a spinoff that
# started trading mid-membership, or the second row of a mid-membership handover). Until
# 2026-10-05 some 56 entries carried a literal "2015-01-02", which was not a tenure date at all
# but a copy of the old cik.SINCE clamp; they are sentinels now.
#
# ``end`` empty means still current, and ``end`` is ALWAYS literal. A start may be extended
# backwards; an end may never be extended forwards, because a truncated end is the entire
# defence against a recycled ticker resolving to a later holder.
#
# Hand-audited; wins over every automated tier. Every CIK below was confirmed against
# https://data.sec.gov/submissions/CIK<cik>.json.
MANUAL: dict[str, tuple[tuple[str, str, str, str, str], ...]] = {
    # --- recycled tickers: EDGAR's ticker lookup answers with today's holder -------------
    "CA": (
        ("0000356028", "", "2018-11-06", "CA, INC.",
         "recycled: CA is now an Xtrackers ETF share class; CA Inc (ex-Computer Associates) "
         "was acquired by Broadcom 2018-11-05"),
    ),
    "MON": (
        ("0001110783", "", "2018-06-07", "MONSANTO CO /NEW/",
         "recycled: browse-edgar answers 0001828325 Monument Circle Acquisition Corp; "
         "Monsanto was acquired by Bayer 2018-06-07"),
    ),
    "PLL": (
        ("0000075829", "", "2015-08-31", "PALL CORP",
         "recycled: browse-edgar answers 0001728205 Piedmont Lithium; Pall Corp was acquired "
         "by Danaher 2015-08-31"),
    ),
    "ALTR": (
        ("0000768251", "", "2015-12-28", "ALTERA CORP",
         "recycled: browse-edgar answers 0001701732 Altair Engineering; Altera was acquired "
         "by Intel 2015-12-28"),
    ),
    "LLL": (
        ("0001039101", "", "2019-07-01", "L3 TECHNOLOGIES, INC.",
         "recycled: browse-edgar answers 0001546383 JX Luxventure, which also filed 5 periodic "
         "reports inside the span, so the filing screen does NOT catch it; L3 merged with "
         "Harris 2019-06-29"),
    ),
    "DTV": (
        ("0001465112", "", "2015-07-27", "DIRECTV",
         "recycled: the ticker now carries DTE Energy corporate units (0000936340), which filed "
         "3 periodic reports inside the span, so the filing screen does NOT catch it; DIRECTV "
         "was acquired by AT&T 2015-07-24"),
    ),
    # --- filer changes inside the window, same ticker -------------------------------------
    "WRK": (
        ("0001636023", "2015-07-02", "2018-11-02", "WRKCo Inc.",
         "WestRock Co until the KapStone close on 2018-11-02, then renamed WRKCo Inc."),
        ("0001732845", "2018-11-02", "2024-07-08", "WestRock Co",
         "Whiskey Holdco became the WestRock registrant at the 2018-11-02 KapStone close; "
         "acquired by Smurfit Kappa 2024-07-05"),
    ),
    "GOOGL": (
        ("0001288776", "", "2015-10-02", "GOOGLE INC.",
         "Google Inc was the registrant until the Alphabet holdco reorg closed 2015-10-02"),
        ("0001652044", "2015-10-02", "", "ALPHABET INC.", "Alphabet holdco reorg 2015-10-02"),
    ),
    "GOOG": (
        ("0001288776", "", "2015-10-02", "GOOGLE INC.",
         "class C of the same filer as GOOGL; Google Inc until 2015-10-02"),
        ("0001652044", "2015-10-02", "", "ALPHABET INC.", "Alphabet holdco reorg 2015-10-02"),
    ),
    # --- hand-audited 2026-10-05: the 33 the automated tiers left unresolved -------------
    "AABA": (
        ("0001011006", "", "2017-06-19", "ALTABA INC.",
         "EDGAR former name YAHOO INC (1996-08-14..2017-06-15); the operating business went to "
         "Verizon 2017-06-13 and the rump became Altaba; 10 periodic filings inside the span"),
    ),
    "ADS": (
        ("0001101215", "", "2020-06-22", "BREAD FINANCIAL HOLDINGS, INC.",
         "EDGAR former name ALLIANCE DATA SYSTEMS CORP (2000-06-09..2022-03-23); a pure rename on "
         "the same CIK; 18 periodic filings inside the span"),
    ),
    "BCR": (
        ("0000009892", "", "2017-12-29", "BARD C R INC /NJ/",
         "C.R. Bard, acquired by Becton Dickinson 2017-12-29; 12 periodic filings inside the "
         "span; the predecessor CIK 0000275110 filed none inside it"),
    ),
    "BRCM": (
        ("0001054374", "", "2016-02-01", "BROADCOM CORP",
         "the original Broadcom Corp, acquired by Avago 2016-02-01; Avago then took the Broadcom "
         "name and the AVGO ticker under a different CIK; 4 periodic filings inside the span"),
    ),
    "BXLT": (
        ("0001620546", "2015-07-01", "2016-06-03", "Baxalta Inc",
         "Baxter spinoff 2015-07-01, acquired by Shire 2016-06-03; 4 periodic filings inside the "
         "span"),
    ),
    "CAM": (
        ("0000941548", "", "2016-04-04", "CAMERON INTERNATIONAL CORP",
         "EDGAR former name COOPER CAMERON CORP; acquired by Schlumberger 2016-04-01; 5 periodic "
         "filings inside the span"),
    ),
    "CELG": (
        ("0000816284", "", "2019-11-21", "CELGENE CORP /DE/",
         "acquired by Bristol-Myers Squibb 2019-11-20; 20 periodic filings inside the span"),
    ),
    "CMCSK": (
        ("0001166691", "2015-09-21", "2015-12-14", "COMCAST CORP",
         "Comcast class K special stock: the same filer as CMCSA, which is why no uniqueness "
         "check applies to cik; 1 periodic filing inside the short span (10-Q 2015-10-27), "
         "visible only in the submissions overflow files"),
    ),
    "COV": (
        ("0001385187", "", "2015-01-27", "Covidien plc",
         "EDGAR former names Covidien Ltd. and Tyco Healthcare Ltd.; acquired by Medtronic "
         "2015-01-26; 1 periodic filing inside the span (10-Q 2015-01-23)"),
    ),
    "CPGX": (
        ("0001629995", "2015-07-02", "2016-07-01", "Columbia Pipeline Group, Inc.",
         "NiSource spinoff 2015-07-01, acquired by TransCanada 2016-07-01; 4 periodic filings "
         "inside the span"),
    ),
    "CSRA": (
        ("0001646383", "2015-11-30", "2018-04-04", "CSRA Inc.",
         "EDGAR former name Computer Sciences Government Services Inc.; CSC spinoff 2015-11-27, "
         "acquired by General Dynamics 2018-04-03; 10 periodic filings inside the span"),
    ),
    "CTRX": (
        ("0001363851", "", "2015-07-24", "Catamaran Corp",
         "EDGAR former name SXC Health Solutions Corp; acquired by UnitedHealth OptumRx "
         "2015-07-23; 2 periodic filings inside the span"),
    ),
    "CVC": (
        ("0001053112", "", "2016-06-21", "CABLEVISION SYSTEMS CORP /NY",
         "the registrant behind the listed equity, acquired by Altice 2016-06-21; 6 periodic "
         "filings inside the span; NOT 0000784681 CSC Holdings LLC, the debt-issuing subsidiary "
         "that co-files on the very same dates"),
    ),
    "DISCK": (
        ("0001437107", "", "2022-04-11", "Warner Bros. Discovery, Inc.",
         "Discovery series C; EDGAR former names Discovery Communications, Inc. "
         "(2008-06-11..2018-03-05) and Discovery, Inc. (2018-03-06..2022-04-08); the WarnerMedia "
         "merger closed 2022-04-08 on the same CIK; 8 periodic filings inside the span"),
    ),
    "EMC": (
        ("0000790070", "", "2016-09-07", "EMC CORP",
         "acquired by Dell 2016-09-07; 7 periodic filings inside the span"),
    ),
    "FLIR": (
        ("0000354908", "", "2021-05-14", "Teledyne FLIR, LLC",
         "EDGAR former name FLIR SYSTEMS INC (1996-08-14..2021-05-14); acquired by Teledyne "
         "2021-05-14 on the same CIK; 26 periodic filings inside the span"),
    ),
    "GMCR": (
        ("0000909954", "", "2016-03-03", "KEURIG GREEN MOUNTAIN, INC.",
         "EDGAR former names GREEN MOUNTAIN COFFEE ROASTERS INC (2003-03-04..2014-03-06) and "
         "GREEN MOUNTAIN COFFEE INC; taken private by JAB 2016-03-03; 5 periodic filings inside "
         "the span"),
    ),
    "INFO": (
        ("0001598014", "2017-06-02", "2022-03-02", "IHS Markit Ltd.",
         "EDGAR former name Markit Ltd. (2014-01-27..2016-07-11); merged into S&P Global "
         "2022-02-28; 19 periodic filings inside the span"),
    ),
    "KORS": (
        ("0001530721", "", "2018-09-19", "Capri Holdings Ltd",
         "EDGAR former name Michael Kors Holdings Ltd (2011-12-02..2018-12-21); renamed Capri on "
         "the Versace deal, same CIK; 15 periodic filings inside the span"),
    ),
    "KRFT": (
        ("0001545158", "", "2015-07-06", "Kraft Foods Group, Inc.",
         "merged with H.J. Heinz into Kraft Heinz (KHC, its own ever-member) 2015-07-02; 2 "
         "periodic filings inside the span"),
    ),
    "LMCA": (
        ("0001560385", "", "2016-06-20", "Liberty Media Corp",
         "Liberty Media series A; EDGAR former name Liberty Spinco, Inc.; replaced by the Liberty "
         "SiriusXM/Braves/Media tracking stocks in 2016; 6 periodic filings inside the span, "
         "visible only in the submissions overflow files; NOT 0001507934 (Starz, traded STRZA) "
         "nor 0001355096 (Liberty Interactive, traded LVNTA/QVCA)"),
    ),
    "LMCK": (
        ("0001560385", "", "2016-06-20", "Liberty Media Corp",
         "Liberty Media series C, the same filer as LMCA; 6 periodic filings inside the span, "
         "visible only in the submissions overflow files"),
    ),
    "LO": (
        ("0001424847", "", "2015-06-12", "LORILLARD, LLC",
         "EDGAR former name LORILLARD, INC. (2008-02-05..2015-06-12); acquired by Reynolds "
         "American 2015-06-12; 2 periodic filings inside the span"),
    ),
    "NDOI": (
        ("NONE", "", "2016-07-18", "",
         "phantom ticker in the Wikipedia-derived ndx_history.csv: present in every snapshot "
         "2007-02-01..2016-07-18, always between MSFT and NIHD. No EDGAR filer exists - absent "
         "from company_tickers.json, from browse-edgar's ticker lookup, from cik-lookup-data.txt "
         "and from all 21250 of Massive's delisted US tickers. The same file carries NLTI, a "
         "transposition of NTLI (NTL Inc), so mangled tickers are a known defect of this source. "
         "A membership_overrides.csv correction belongs to the membership owner, not to this "
         "phase"),
    ),
    "NFX": (
        ("0000912750", "", "2019-02-15", "NEWFIELD EXPLORATION CO /DE/",
         "acquired by Encana 2019-02-13; 16 periodic filings inside the span"),
    ),
    "PCL": (
        ("0000849213", "", "2016-02-22", "PLUM CREEK TIMBER CO INC",
         "merged into Weyerhaeuser 2016-02-19; 5 periodic filings inside the span"),
    ),
    "SHPG": (
        ("0000936402", "2016-10-19", "2018-12-24", "Shire plc",
         "EDGAR former names Shire Ltd. and SHIRE PHARMACEUTICALS GROUP PLC; acquired by Takeda, "
         "ADSs delisted 2018-12-24; 9 periodic filings inside the span; Massive's name for this "
         "ticker is the OCR artifact 'Shire pic', which is why the automated name match failed"),
    ),
    "SNI": (
        ("0001430602", "", "2018-03-07", "Scripps Networks Interactive, Inc.",
         "acquired by Discovery 2018-03-06; 13 periodic filings inside the span"),
    ),
    "SPLS": (
        ("0000791519", "", "2017-09-13", "STAPLES INC",
         "taken private by Sycamore Partners 2017-09-12; 11 periodic filings inside the span"),
    ),
    "TEG": (
        ("0000916863", "", "2015-06-30", "INTEGRYS HOLDING, INC.",
         "EDGAR former names INTEGRYS ENERGY GROUP, INC. (2007-02-23..2015-06-29) and WPS "
         "RESOURCES CORP; acquired by Wisconsin Energy 2015-06-29; 2 periodic filings inside the "
         "span"),
    ),
    "TWC": (
        ("0001377013", "", "2016-05-18", "SPECTRUM MANAGEMENT HOLDING COMPANY, LLC",
         "EDGAR former name TIME WARNER CABLE INC. (2006-10-18..2016-06-01); acquired by Charter "
         "2016-05-18 on the same CIK; 6 periodic filings inside the span"),
    ),
    "WYND": (
        ("0001361658", "", "2018-05-31", "Travel & Leisure Co.",
         "EDGAR former names WYNDHAM WORLDWIDE CORP (2006-05-11..2018-05-23) and Wyndham "
         "Destinations, Inc. (2018-05-31..2021-02-16); the hotel business spun off as WH "
         "2018-05-31 and the rump kept this CIK; 14 periodic filings inside the span, visible "
         "only in the submissions overflow files"),
    ),
    # --- hand-audited 2026-10-05: the one fuzzy match the 2009 floor produced, which was right
    "BNI": (
        ("0000934612", "", "2010-02-16", "BURLINGTON NORTHERN SANTA FE, LLC",
         "difflib matched Massive's 'BURLINGTON NRTHRN SANTA FE(COM' to cik-lookup 'BURLINGTON "
         "NORTHERN SANTA FE' at ratio >= 0.90. Read by hand because SOURCES.md forbids shipping "
         "a fuzzy row: EDGAR records 0000934612 under the name BURLINGTON NORTHERN SANTA FE CORP "
         "from 1995-12-08 to 2010-02-11, when Berkshire Hathaway completed the acquisition and "
         "it became an LLC -- which is the span's end; 124 periodic filings 1995-11-13 .. "
         "2026-08-10. Promoted to manual so the file ships zero fuzzy rows"),
    ),

    # --- hand-audited 2026-10-05: the one fuzzy match, which was wrong -------------------
    "HAR": (
        ("0000800459", "", "2017-03-13", "HARMAN INTERNATIONAL INDUSTRIES INC /DE/",
         "the only fuzzy-tier row, and it was wrong: difflib matched Massive's 'Harman "
         "International Industries' to cik-lookup 'AMERICAN INTERNATIONAL INDUSTRIES' "
         "(0001073146), an unrelated company that filed 4 periodic reports inside the span and so "
         "passed the screen -- the same net-not-a-gate failure as LLL and DTV. Harman was "
         "acquired by Samsung 2017-03-10; 9 periodic filings inside the span"),
    ),
    # --- hand-audited 2026-10-05: rows the periodic-filing screen caught -----------------
    "ADT": (
        ("0001546640", "", "2016-05-02", "ADT Corp",
         "recycled: browse-edgar answers 0001703056 ADT Inc., the 2017 Apollo/Prime Security "
         "entity whose filings start 2017-04-11; The ADT Corporation was the 2012 Tyco spinoff, "
         "taken private by Apollo 2016-05-02; 5 periodic filings inside the span"),
    ),
    "APC": (
        ("0000773910", "", "2019-08-09", "ANADARKO PETROLEUM CORP",
         "recycled: the ticker now carries ARKO Petroleum Corp (0002080921, filings start "
         "2025-09-15); Anadarko was acquired by Occidental 2019-08-08; 19 periodic filings inside "
         "the span"),
    ),
    "BATRA": (
        ("0001560385", "2016-04-18", "2016-06-20", "Liberty Media Corp",
         "Liberty Braves series A was a Liberty Media tracking stock in this window; the ticker "
         "now carries Atlanta Braves Holdings (0001958140), which did not exist until the 2023 "
         "split-off; 1 periodic filing inside the span"),
    ),
    "BATRK": (
        ("0001560385", "2016-04-18", "2016-06-20", "Liberty Media Corp",
         "Liberty Braves series C, the same filer as BATRA; the ticker now carries Atlanta Braves "
         "Holdings (0001958140), incorporated 2022; 1 periodic filing inside the span"),
    ),
    "DINO": (
        ("0000048039", "2018-06-18", "2021-06-04", "HollyFrontier Corp",
         "recycled: the ticker now carries HF Sinclair (0001915657, filings start 2022-03-14), "
         "the 2022 holding company; HollyFrontier Corp (EDGAR former name HOLLY CORP) is the "
         "filer for this window; 12 periodic filings inside the span"),
    ),
    "LILA": (
        ("0001570585", "2015-07-02", "2015-12-21", "Liberty Global Ltd.",
         "LiLAC series A was a Liberty Global tracking stock in this window; the ticker now "
         "carries Liberty Latin America (0001712184), which was not split off until 2018; 2 "
         "periodic filings inside the span"),
    ),
    "LILAK": (
        ("0001570585", "2015-07-02", "2015-12-21", "Liberty Global Ltd.",
         "LiLAC series C, the same filer as LILA; Liberty Latin America (0001712184) did not "
         "exist until the 2018 split-off; 2 periodic filings inside the span"),
    ),
    "NE": (
        ("0001458891", "", "2015-07-20", "Noble Corp",
         "recycled across a reorganisation: the ticker now carries Noble Corp plc 0001895262 "
         "(filings start 2021-12-20, former Noble Finco Ltd); the filer in this window is CIK "
         "0001458891, EDGAR former names Noble Corp / Switzerland and Noble Corp plc; 2 periodic "
         "filings inside the span"),
    ),
    "POM": (
        ("0001135971", "", "2016-03-24", "PEPCO HOLDINGS LLC",
         "recycled: the ticker now carries POMDOCTOR Ltd (0001877971, filings start 2021-09-30); "
         "Pepco Holdings (EDGAR former name PEPCO HOLDINGS INC) was acquired by Exelon "
         "2016-03-23; 5 periodic filings inside the span"),
    ),
    "SE": (
        ("0001373835", "", "2017-02-27", "Spectra Energy Corp.",
         "recycled: the ticker now carries Sea Ltd (0001703399, filings start 2017-04-24); "
         "Spectra Energy merged into Enbridge 2017-02-27; 9 periodic filings inside the span"),
    ),
    "STI": (
        ("0000750556", "", "2019-12-09", "SUNTRUST BANKS INC",
         "recycled: the ticker now carries Solidion Technology (0001881551, former Nubia Brand "
         "International Corp); SunTrust merged with BB&T into Truist 2019-12-06; 20 periodic "
         "filings inside the span"),
    ),
    "TE": (
        ("0000350563", "", "2016-07-01", "TECO ENERGY INC",
         "recycled: the ticker now carries T1 Energy (0001992243, former FREYR Battery); TECO "
         "Energy was acquired by Emera 2016-07-01; 6 periodic filings inside the span"),
    ),
    "VIP": (
        ("0001468091", "", "2015-12-21", "VEON Ltd.",
         "recycled: the ticker now carries Vulcan Infrastructure & Power (0001844971, former "
         "Greenidge Generation); VimpelCom Ltd (EDGAR former name of this CIK until 2017-03-28) "
         "is the filer for this window; 1 periodic filing inside the span (20-F, a foreign "
         "private issuer)"),
    ),
    "PX": (
        ("0000884905", "", "2018-10-31", "LINDE INC",
         "recycled: the ticker now carries Ridgepost Capital (0001841968, former P10 Inc); EDGAR "
         "former name PRAXAIR INC (1995-02-14..2022-02-03) on the same CIK, merged into Linde "
         "2018-10-31; 15 periodic filings inside the span"),
    ),
    "XL": (
        ("0000875159", "", "2018-09-12", "XL GROUP LTD",
         "recycled: the ticker now carries Spruce Power Holding (0001772720, former XL Fleet Corp "
         "/ Pivotal Investment Corp II); XL Group (EDGAR former names XL GROUP PLC, XL CAPITAL "
         "LTD, EXEL LTD) was acquired by AXA 2018-09-12; 15 periodic filings inside the span"),
    ),
    "DNB": (
        ("0001115222", "", "2017-04-05", "DUN & BRADSTREET CORP/NW",
         "the ticker was reissued to Dun & Bradstreet Holdings (0001799208) at its 2020 re-IPO; "
         "the filer for this window is the old Dun & Bradstreet Corp, taken private 2019-02-08; 9 "
         "periodic filings inside the span"),
    ),
    "AET": (
        ("0001122304", "", "2018-11-29", "AETNA INC /PA/",
         "name match picked 0001022658 AETNA HOLDINGS INC, which filed only 3 documents, all in "
         "1996; the Aetna in the S&P 500 is CIK 0001122304, acquired by CVS 2018-11-28; 16 "
         "periodic filings inside the span"),
    ),
    "DAY": (
        ("0001725057", "2021-09-20", "2026-02-09", "Dayforce, Inc.",
         "name match picked 0001496678 Dayforce Corp, a namesake with a single 2010 filing; the "
         "index member is CIK 0001725057, EDGAR former name Ceridian HCM Holding Inc. "
         "(2018-01-12..2024-01-26); 17 periodic filings inside the span"),
    ),
    "EVHC": (
        ("0001678531", "2016-12-02", "2018-10-11", "Envision Healthcare Corp",
         "two CIKs share the name: 0001344154 (former Emergency Medical Services Corp) stopped "
         "filing 2014-06-20; the post-merger AmSurg/Envision entity is 0001678531, EDGAR former "
         "name New Amethyst Corp., taken private by KKR 2018-10-11; 7 periodic filings inside the "
         "span"),
    ),
    "LLTC": (
        ("0000791907", "", "2017-03-13", "LINEAR TECHNOLOGY CORP /CA/",
         "name match picked 0001160656 CLEAR TECHNOLOGY INC, an unrelated company with 6 filings "
         "ending 2007; Linear Technology is CIK 0000791907, acquired by Analog Devices "
         "2017-03-10; 9 periodic filings inside the span"),
    ),
    "MJN": (
        ("0001452575", "", "2017-06-15", "Mead Johnson Nutrition Co",
         "two CIKs carry the name: 0001444904 filed only 4 documents in 2008; the listed issuer "
         "is 0001452575, acquired by Reckitt Benckiser 2017-06-15; 10 periodic filings inside the "
         "span"),
    ),
    "MNK": (
        ("0001567892", "", "2017-07-26", "Keenova Therapeutics plc",
         "name match picked 0000051396 MALLINCKRODT INC /MO (former IMCERA GROUP), whose filings "
         "end 2001; the index member is CIK 0001567892, EDGAR former name Mallinckrodt plc "
         "(2013-02-01..2025-11-10); 9 periodic filings inside the span"),
    ),
    "PETM": (
        ("0000863157", "", "2015-03-12", "PETSMART INC",
         "name match picked 0001088628 PETSMART COM INC, the dot-com subsidiary with 2 filings in "
         "2000; the index member is CIK 0000863157, taken private by BC Partners 2015-03-11. No "
         "periodic filing falls inside the 10-week span because the FY2014 10-K was due after the "
         "buyout, so this symbol is also in SCREEN_EXEMPT"),
    ),
    "RTN": (
        ("0001047122", "", "2020-04-06", "RAYTHEON CO/",
         "name match picked 0000082267 RAYTHEON CO, the pre-1997 entity whose filings end "
         "2013-03-25; the index member is CIK 0001047122 (EDGAR former name HE HOLDINGS INC), "
         "merged with United Technologies into Raytheon Technologies 2020-04-03; 21 periodic "
         "filings inside the span"),
    ),

    # --- hand-audited 2026-10-05: the 28 the 2009 floor newly admitted and no tier resolved --
    # Every CIK below was read off https://data.sec.gov/submissions/CIK<cik>.json: the note
    # records the EDGAR name, any formerNames, and the periodic-filing range that was checked.
    # The seven -Q suffixes are post-bankruptcy pink-sheet tickers; the filer is the company,
    # under the CIK it filed with before the Q was appended.
    "ACS": (
        ("0000002135", "", "2010-02-08", "AFFILIATED COMPUTER SERVICES INC",
         "55 periodic filings 1996-05-13 .. 2009-10-22; acquired by Xerox 2010-02-05, which is "
         "why the filings stop inside the span"),
    ),
    "ANRZQ": (
        ("0001301063", "", "2012-10-02", "Alpha Natural Resources, Inc.",
         "43 periodic filings 2005-03-31 .. 2015-08-03; EDGAR former name Foundation Coal "
         "Holdings, Inc., renamed at the 2009 Alpha merger. Not 0001310243 Alpha Natural "
         "Resources, Inc./Old, whose filings end 2009-08-07, before this span opens. ANRZQ is "
         "the pink-sheet ticker after the 2015 Chapter 11"),
    ),
    "BTUUQ": (
        ("0001064728", "", "2014-09-22", "PEABODY ENERGY CORP",
         "111 periodic filings 1998-11-13 .. 2026-08-06, ticker BTU on NYSE today; EDGAR former "
         "name P&L COAL HOLDINGS CORP. BTUUQ is the pink-sheet ticker during the 2016 Chapter 11"),
    ),
    "CBE": (
        ("0001141982", "", "2012-12-03", "Cooper Industries plc",
         "42 periodic filings 2002-08-14 .. 2012-11-05; EDGAR former name COOPER INDUSTRIES LTD. "
         "Not 0000024454 COOPER INDUSTRIES INC, whose filings end 2002-05-13; acquired by Eaton "
         "2012-11-30"),
    ),
    "CITGQ": (
        ("0001171825", "", "2009-07-27", "CIT GROUP INC",
         "78 periodic filings 2002-08-14 .. 2021-11-05; EDGAR former name CIT GROUP INC DEL. Not "
         "0000020388 CIT GROUP INC (ex-Tyco Capital), whose filings end 2002-05-15. CITGQ is the "
         "pink-sheet ticker around the 2009 prepackaged Chapter 11"),
    ),
    "EKDKQ": (
        ("0000031235", "", "2010-12-20", "EASTMAN KODAK CO",
         "131 periodic filings 1994-03-11 .. 2026-08-04, ticker KODK on NYSE today; EKDKQ is the "
         "pink-sheet ticker during the 2012 Chapter 11"),
    ),
    "FII": (
        ("0001056288", "", "2013-01-02", "FEDERATED HERMES, INC.",
         "114 periodic filings 1998-06-16 .. 2026-07-31, ticker FHI on NYSE today; EDGAR former "
         "name FEDERATED INVESTORS INC /PA/, renamed 2020"),
    ),
    "FMCN": (
        ("0001330017", "", "2009-01-20", "Focus Media Holding LTD",
         "8 periodic filings 2006-06-28 .. 2013-04-29, all 20-F: a foreign private issuer filing "
         "annually, so a 20-day span holds none; taken private 2013"),
    ),
    "FWLT": (
        ("0001130385", "", "2010-12-20", "FOSTER WHEELER AG",
         "54 periodic filings 2001-08-13 .. 2014-11-03; EDGAR former name FOSTER WHEELER LTD, "
         "redomesticated to Switzerland 2009. Not 0000038321 FOSTER WHEELER CORP, the pre-2001 "
         "entity"),
    ),
    "GENZ": (
        ("0000732485", "", "2011-04-04", "GENZYME CORP",
         "64 periodic filings 1995-05-12 .. 2011-03-01; acquired by Sanofi 2011-04-08, which is "
         "why the filings stop at the end of the span"),
    ),
    "JAVA": (
        ("0000709519", "", "2010-01-27", "SUN MICROSYSTEMS, INC.",
         "64 periodic filings 1994-02-08 .. 2009-11-06; the ticker was SUNW until 2007, when Sun "
         "moved to JAVA; acquired by Oracle 2010-01-27"),
    ),
    "JNY": (
        ("0000874016", "", "2009-03-04", "JONES GROUP INC",
         "72 periodic filings 1996-05-14 .. 2014-02-18; EDGAR former name JONES APPAREL GROUP "
         "INC, renamed 2010 -- the same CIK throughout, so the 2009 span is this filer"),
    ),
    "KFT": (
        ("0001103982", "", "2012-10-02", "Mondelez International, Inc.",
         "101 periodic filings 2001-08-13 .. 2026-07-28, ticker MDLZ on Nasdaq today; EDGAR "
         "former name KRAFT FOODS INC, renamed 2012-10-01 when it spun off the grocery business "
         "as Kraft Foods Group (0001545158, ticker KRFT). KFT is the pre-rename ticker"),
    ),
    "LXK": (
        ("0001001288", "", "2012-10-01", "LEXMARK INTERNATIONAL INC /KY/",
         "82 periodic filings 1996-08-08 .. 2016-11-04; EDGAR former name LEXMARK INTERNATIONAL "
         "GROUP INC. Not 0001060259 LEXMARK INTERNATIONAL INC, which has no periodic filings at "
         "all"),
    ),
    "MIL": (
        ("0000066479", "", "2010-07-15", "MILLIPORE CORP /MA",
         "66 periodic filings 1994-03-28 .. 2010-05-12; acquired by Merck KGaA 2010-07-14"),
    ),
    "MTLQQ": (
        ("0000040730", "", "2009-06-03", "Motors Liquidation Co",
         "97 periodic filings 1994-03-29 .. 2021-02-12; EDGAR former name GENERAL MOTORS CORP. "
         "MTLQQ is the pink-sheet ticker the old GM took after the 2009-06-01 Chapter 11; the "
         "new General Motors Company is 0001467858 and is a different filer"),
    ),
    "NIHD": (
        ("0001037016", "", "2011-12-19", "NII HOLDINGS INC",
         "90 periodic filings 1997-09-22 .. 2019-11-05; EDGAR former names NEXTEL INTERNATIONAL "
         "INC and MCCAW INTERNATIONAL LTD"),
    ),
    "NVLS": (
        ("0000836106", "", "2012-06-05", "NOVELLUS SYSTEMS INC",
         "69 periodic filings 1995-05-15 .. 2012-05-07; acquired by Lam Research 2012-06-04"),
    ),
    "PGN": (
        ("0001094093", "", "2012-07-02", "PROGRESS ENERGY INC",
         "108 periodic filings 2000-03-29 .. 2026-08-04; EDGAR former names CP&L ENERGY INC and "
         "CP&L HOLDINGS INC. It still files as a Duke Energy subsidiary registrant after the "
         "2012-07-02 merger, which is why the range runs past the span"),
    ),
    "PPDI": (
        ("0001003124", "", "2009-12-21", "PHARMACEUTICAL PRODUCT DEVELOPMENT, LLC",
         "63 periodic filings 1996-05-15 .. 2011-11-02; EDGAR former name PHARMACEUTICAL PRODUCT "
         "DEVELOPMENT INC, taken private 2011-12"),
    ),
    "ROH": (
        ("0000084792", "", "2009-04-02", "ROHM & HAAS CO",
         "60 periodic filings 1994-03-25 .. 2009-02-27; acquired by Dow Chemical 2009-04-01, so "
         "the last 10-K falls inside the span"),
    ),
    "RSHCQ": (
        ("0000096289", "", "2011-07-01", "RS Legacy Corp",
         "84 periodic filings 1994-03-30 .. 2014-12-11; EDGAR former names RADIOSHACK CORP and "
         "TANDY CORP /DE/. RSHCQ is the pink-sheet ticker after the 2015 Chapter 11; the filer "
         "held RSH on NYSE throughout this span"),
    ),
    "SHLD": (
        ("0001310067", "", "2013-12-23", "SEARS HOLDINGS CORP",
         "55 periodic filings 2005-06-07 .. 2018-12-13, formed by the 2005 Kmart/Sears merger"),
    ),
    "STRZA": (
        ("0001507934", "", "2013-03-18", "Starz Acquisition LLC",
         "23 periodic filings 2011-06-02 .. 2016-11-08; EDGAR former names Starz, Liberty Media "
         "Corp, Liberty CapStarz, Inc. and Liberty Splitco, Inc. STRZA is the Series A tracking "
         "stock of the 2013-01-11 Liberty Media split-off"),
    ),
    "SUNEQ": (
        ("0000945436", "", "2011-12-19", "SUNEDISON, INC.",
         "78 periodic filings 1996-08-12 .. 2015-11-09; EDGAR former name MEMC ELECTRONIC "
         "MATERIALS INC, which held the ticker WFR through this span and renamed to SunEdison in "
         "2013. SUNEQ is the pink-sheet ticker after the 2016 Chapter 11"),
    ),
    "UST": (
        ("0000811669", "", "2009-01-06", "UST INC",
         "60 periodic filings 1994-03-16 .. 2008-11-03; the smokeless-tobacco UST, acquired by "
         "Altria 2009-01-06. The 5-day span holds no filing, so this symbol is also in "
         "SCREEN_EXEMPT"),
    ),
    "VMED": (
        ("0001270400", "", "2013-06-05", "VIRGIN MEDIA INC.",
         "38 periodic filings 2004-06-14 .. 2013-08-08; EDGAR former names NTL INC and TELEWEST "
         "GLOBAL INC; acquired by Liberty Global 2013-06-07"),
    ),
    "WCRX": (
        ("0001323854", "", "2012-12-24", "Warner Chilcott plc",
         "28 periodic filings 2006-11-14 .. 2013-07-24; EDGAR former names Warner Chilcott Ltd "
         "and Warner Chilcott Holdings Co Ltd. Not 0001042459 (9 filings ending 2000-08-14) nor "
         "0001113445 (ex-GALEN HOLDINGS PLC, 4 filings ending 2003-12-31)"),
    ),

    # --- hand-audited 2026-10-05: flagged by the SCREEN and EARLY screens at the 2009 floor --
    # Each CIK was read off https://data.sec.gov/submissions/CIK<cik>.json. Where two filers
    # held the ticker, the tenure is split: for a symbol whose membership has a multi-year
    # hole the rows take the real membership boundaries and the hole stays uncovered (as for
    # Q); otherwise they meet at the successor's FIRST periodic filing, which is measured and
    # is the first date any fact of the successor's exists. No end is ever pushed forward.
    "ACAS": (
        ("0000817473", "", "2009-03-04", "AMERICAN CAPITAL, LTD",
         "tier answered 0000004707 AMERICA CAPITAL CORP, a namesake with no periodic filings at "
         "all; the index member is the BDC American Capital, Ltd (EDGAR former name AMERICAN "
         "CAPITAL STRATEGIES LTD), 77 periodic filings 1997-11-14 .. 2016-11-03"),
    ),
    "AKS": (
        ("0000918160", "", "2011-12-19", "Cleveland-Cliffs Steel Holding Corp",
         "tier answered 0000918192 AK STEEL CORP, the operating subsidiary, which files no periodic "
         "report of its own; the index member is AK Steel Holding Corp, 95 periodic filings "
         "1996-07-29 .. 2020-02-20, renamed Cleveland-Cliffs Steel Holding after the 2020 "
         "acquisition"),
    ),
    "APA": (
        ("0000006769", "", "2021-05-07", "APACHE CORP",
         "held APA until the 2021 holding-company reorganisation; 124 periodic filings 1994-03-21 "
         ".. 2024-11-07. The two rows meet at the successor's first periodic filing (2021-05-07), "
         "which is the first date any fact of the successor's exists"),
        ("0001841666", "2021-05-07", "", "APA Corp",
         "the 2021 holding-company reorganisation; first periodic filing 2021-05-07, measured from "
         "its submissions JSON"),
    ),
    "AVGO": (
        ("0001441634", "", "2018-06-14", "Avago Technologies LTD",
         "held AVGO until the 2018 Singapore-to-Delaware redomiciliation; 26 periodic filings "
         "2009-09-03 .. 2015-12-17. The two rows meet at the successor's first periodic filing "
         "(2018-06-14), which is the first date any fact of the successor's exists"),
        ("0001730168", "2018-06-14", "", "Broadcom Inc.",
         "the 2018 Singapore-to-Delaware redomiciliation; first periodic filing 2018-06-14, "
         "measured from its submissions JSON"),
    ),
    "BEAM": (
        ("0000789073", "", "2014-05-01", "Beam Suntory Inc.",
         "tier answered 0001745999 Beam Therapeutics Inc., a 2020 biotech holding the ticker today; "
         "the index member is Beam Inc, 81 periodic filings 1994-03-28 .. 2014-02-18, EDGAR former "
         "names BEAM INC, FORTUNE BRANDS INC and AMERICAN BRANDS INC /DE/; acquired by Suntory "
         "2014-04"),
    ),
    "BKR": (
        ("0000808362", "", "2017-07-28", "Baker Hughes Holdings LLC",
         "held BKR until the 2017 Baker Hughes/GE Oil & Gas combination; 120 periodic filings "
         "1994-02-14 .. 2023-10-26, EDGAR former name BAKER HUGHES A GE CO LLC. The two rows meet "
         "at the successor's first periodic filing (2017-07-28), which is the first date any fact "
         "of the successor's exists"),
        ("0001701605", "2017-07-28", "", "Baker Hughes Co",
         "the 2017 Baker Hughes/GE Oil & Gas combination; first periodic filing 2017-07-28, "
         "measured from its submissions JSON"),
    ),
    "BLK": (
        ("0001364742", "", "2024-11-06", "BlackRock Finance, Inc.",
         "held BLK until the 2024 holding-company reorganisation; 72 periodic filings 2006-11-14 .. "
         "2024-08-06. The two rows meet at the successor's first periodic filing (2024-11-06), "
         "which is the first date any fact of the successor's exists"),
        ("0002012383", "2024-11-06", "", "BlackRock, Inc.",
         "the 2024 holding-company reorganisation; first periodic filing 2024-11-06, measured from "
         "its submissions JSON"),
    ),
    "CCE": (
        ("0000804055", "", "2010-10-28", "COCA-COLA REFRESHMENTS USA, INC.",
         "held CCE until the 2010 North America/Europe split; 67 periodic filings 1994-03-14 .. "
         "2010-07-28, the old Coca-Cola Enterprises Inc. The two rows meet at the successor's first "
         "periodic filing (2010-10-28), which is the first date any fact of the successor's exists"),
        ("0001491675", "2010-10-28", "2016-05-31", "COCA-COLA ENTERPRISES, INC.",
         "the 2010 North America/Europe split; first periodic filing 2010-10-28, measured from its "
         "submissions JSON. Supersedes the single-row entry this file carried until 2026-10-05, "
         "which said NOT 0000804055 because that filer filed nothing inside the span -- true "
         "while the span opened 2015-01-02, false once the floor moved to 2009-01-01"),
    ),
    "CEG": (
        ("0001004440", "", "2012-03-13", "CONSTELLATION ENERGY GROUP INC",
         "Constellation Energy Group held CEG until the Exelon merger closed 2012-03-12; 56 "
         "periodic filings 1997-05-14 .. 2012-02-29"),
        ("0001868275", "2022-02-02", "", "Constellation Energy Corp",
         "the 2022 Exelon generation spinoff, first periodic filing 2022-02-25"),
    ),
    "CI": (
        ("0000701221", "", "2019-02-28", "Cigna Holding Co",
         "held CI until the 2018 Express Scripts acquisition holdco; 100 periodic filings "
         "1994-03-25 .. 2018-11-01. The two rows meet at the successor's first periodic filing "
         "(2019-02-28), which is the first date any fact of the successor's exists"),
        ("0001739940", "2019-02-28", "", "Cigna Group",
         "the 2018 Express Scripts acquisition holdco; first periodic filing 2019-02-28, measured "
         "from its submissions JSON"),
    ),
    "DD": (
        ("0000030554", "", "2017-09-01", "EIDP, Inc.",
         "E I du Pont de Nemours held DD until the 2017-08-31 DowDuPont merger; 131 periodic "
         "filings 1994-03-21 .. 2026-07-31, EDGAR former name DUPONT E I DE NEMOURS & CO"),
        ("0001666700", "2019-06-03", "", "DuPont de Nemours, Inc.",
         "DowDuPont renamed DuPont de Nemours at the 2019 separations, first periodic filing "
         "2017-11-06; membership resumes 2019-06-03"),
    ),
    "DELL": (
        ("0000826083", "", "2013-10-29", "DELL INC",
         "Dell Inc held DELL until the 2013-10-29 Silver Lake buyout; 79 periodic filings "
         "1994-04-01 .. 2013-08-28"),
        ("0001571996", "2024-09-23", "", "Dell Technologies Inc.",
         "the post-2018 re-listing, first periodic filing 2016-06-10; membership resumes 2024-09-23"),
    ),
    "DF": (
        ("0000931336", "", "2013-05-24", "DEAN FOODS CO",
         "tier answered 0000027500 DEAN FOODS CO, the pre-2001 company acquired by Suiza, whose "
         "first periodic filing is 1994-01-11 and which did not file in this span; the index member "
         "is the Suiza entity that took the Dean Foods name, 96 periodic filings 1996-05-15 .. "
         "2020-03-20, EDGAR former name SUIZA FOODS CORP"),
    ),
    "DIS": (
        ("0001001039", "", "2019-05-08", "TWDC Enterprises 18 Corp.",
         "held DIS until the 2019 Fox-acquisition holding company; 93 periodic filings 1996-02-14 "
         ".. 2019-02-05. The two rows meet at the successor's first periodic filing (2019-05-08), "
         "which is the first date any fact of the successor's exists"),
        ("0001744489", "2019-05-08", "", "Walt Disney Co",
         "the 2019 Fox-acquisition holding company; first periodic filing 2019-05-08, measured from "
         "its submissions JSON"),
    ),
    "DOW": (
        ("0000029915", "", "2017-09-01", "DOW CHEMICAL CO /DE/",
         "The Dow Chemical Company held DOW until the 2017-08-31 DowDuPont merger; 128 periodic "
         "filings 1995-03-23 .. 2026-07-24"),
        ("0001751788", "2019-04-02", "", "DOW INC.",
         "the 2019-04-01 DowDuPont materials-science spinoff, first periodic filing 2019-05-03"),
    ),
    "DYN": (
        ("0001379895", "", "2009-12-21", "DYNEGY INC.",
         "tier answered 0001818794 Dyne Therapeutics, Inc.; the index member is Dynegy Inc, 44 "
         "periodic filings 2007-05-09 .. 2018-02-22, EDGAR former name Dynegy Acquisition, Inc. Not "
         "0000879215 DYNEGY ILLINOIS INC., whose filings end 2007-02-27"),
    ),
    "EQ": (
        ("0001350031", "", "2009-07-01", "Embarq CORP",
         "tier answered 0001746466 Equillium, Inc., a 2018 biotech; the index member is Embarq "
         "Corp, the 2006 Sprint local-telephone spinoff, 13 periodic filings 2006-06-09 .. "
         "2009-05-07, acquired by CenturyTel 2009-07-01 which is exactly where the span ends"),
    ),
    "ESRX": (
        ("0000885721", "", "2012-05-10", "EXPRESS SCRIPTS INC",
         "held ESRX until the 2012 Medco merger holdco; 64 periodic filings 1996-05-10 .. "
         "2012-02-22. The two rows meet at the successor's first periodic filing (2012-05-10), "
         "which is the first date any fact of the successor's exists"),
        ("0001532063", "2012-05-10", "2018-12-24", "Express Scripts Holding Company",
         "the 2012 Medco merger holdco; first periodic filing 2012-05-10, measured from its "
         "submissions JSON"),
    ),
    "ETN": (
        ("0000031277", "", "2012-11-14", "EATON CORP",
         "held ETN until the 2012 Cooper acquisition and Irish domicile; 76 periodic filings "
         "1994-03-28 .. 2012-10-31. The two rows meet at the successor's first periodic filing "
         "(2012-11-14), which is the first date any fact of the successor's exists"),
        ("0001551182", "2012-11-14", "", "Eaton Corp plc",
         "the 2012 Cooper acquisition and Irish domicile; first periodic filing 2012-11-14, "
         "measured from its submissions JSON"),
    ),
    "FOX": (
        ("0001308161", "", "2019-03-18", "TWENTY-FIRST CENTURY FOX, INC.",
         "held FOX until the 2019 Disney-transaction spinoff; 57 periodic filings 2005-02-04 .. "
         "2019-02-06. The two rows meet at the successor's first periodic filing (2019-03-18), "
         "which is the first date any fact of the successor's exists"),
        ("0001754301", "2019-03-18", "", "Fox Corp",
         "the 2019 Disney-transaction spinoff; first periodic filing 2019-03-18, measured from its "
         "submissions JSON"),
    ),
    "FOXA": (
        ("0001308161", "", "2019-03-18", "TWENTY-FIRST CENTURY FOX, INC.",
         "held FOXA until the 2019 Disney-transaction spinoff; 57 periodic filings 2005-02-04 .. "
         "2019-02-06. The two rows meet at the successor's first periodic filing (2019-03-18), "
         "which is the first date any fact of the successor's exists"),
        ("0001754301", "2019-03-18", "", "Fox Corp",
         "the 2019 Disney-transaction spinoff; first periodic filing 2019-03-18, measured from its "
         "submissions JSON"),
    ),
    "FRX": (
        ("0000038074", "", "2014-07-01", "Forest Laboratories, LLC",
         "tier answered 0001826889 Forest Road Acquisition Corp., a 2020 SPAC; the index member is "
         "Forest Laboratories, 82 periodic filings 1994-02-14 .. 2014-05-30; acquired by Actavis "
         "2014-07-01"),
    ),
    "FTI": (
        ("0001135152", "", "2017-01-13", "FMC TECHNOLOGIES INC",
         "held FTI until the 2017 Technip merger; 62 periodic filings 2001-08-14 .. 2016-10-27. The "
         "two rows meet at the successor's first periodic filing (2017-01-13), which is the first "
         "date any fact of the successor's exists"),
        ("0001681459", "2017-01-13", "2021-02-12", "TechnipFMC plc",
         "the 2017 Technip merger; first periodic filing 2017-01-13, measured from its submissions "
         "JSON"),
    ),
    "GOLD": (
        ("0001175580", "", "2013-11-18", "RANDGOLD RESOURCES LTD",
         "tier answered 0001591588 Gold.com, Inc.; in this span the ticker was Randgold Resources "
         "Ltd, 16 periodic filings (20-F) 2003-06-27 .. 2018-03-29. GOLD is Barrick Gold today, and "
         "neither screen can see this handover because Barrick filed throughout -- it is a recycled "
         "ticker only a human catches"),
    ),
    "IACI": (
        ("0000891103", "", "2009-12-21", "Match Group, Inc.",
         "tier answered 0001892876 Intrepid Acquisition Corp I; the index member is "
         "IAC/InterActiveCorp, 122 periodic filings 1996-05-15 .. 2026-08-05, EDGAR former names "
         "IAC/INTERACTIVECORP, INTERACTIVECORP, USA INTERACTIVE, USA NETWORKS INC, HSN INC and "
         "SILVER KING COMMUNICATIONS"),
    ),
    "ICE": (
        ("0001174746", "", "2013-08-07", "Intercontinental Exchange Holdings, Inc.",
         "held ICE until the 2013 NYSE Euronext holdco; 32 periodic filings 2006-03-10 .. "
         "2013-11-05, EDGAR former name INTERCONTINENTALEXCHANGE INC. The two rows meet at the "
         "successor's first periodic filing (2013-08-07), which is the first date any fact of the "
         "successor's exists"),
        ("0001571949", "2013-08-07", "", "Intercontinental Exchange, Inc.",
         "the 2013 NYSE Euronext holdco; first periodic filing 2013-08-07, measured from its "
         "submissions JSON"),
    ),
    "IGT": (
        ("0000353944", "", "2014-06-20", "INTERNATIONAL GAME TECHNOLOGY",
         "tier answered 0001619762 Brightstar Lottery PLC (the 2015 IGT PLC, renamed 2025); the "
         "index member is the Nevada International Game Technology, 85 periodic filings 1993-12-23 "
         ".. 2015-02-09"),
    ),
    "IR": (
        ("0001160497", "", "2009-07-01", "INGERSOLL RAND CO LTD",
         "the Bermuda Ingersoll-Rand Company Limited, 30 periodic filings 2002-03-13 .. 2009-05-08; "
         "membership ends 2009-07-01, the same date EDGAR records the Irish entity taking the name"),
        ("0001466258", "2010-11-17", "2020-02-26", "Trane Technologies plc",
         "EDGAR records this CIK as Ingersoll-Rand plc from 2009-07-01 to 2020-02-24, when it was "
         "renamed Trane Technologies and kept ticker TT; 69 periodic filings 2009-08-06 .. "
         "2026-07-30"),
        ("0001699150", "2020-02-26", "", "Ingersoll Rand Inc.",
         "EDGAR records this CIK as GARDNER DENVER HOLDINGS, INC. to 2020-02-26, when it took the "
         "Ingersoll Rand name and the IR ticker; 37 periodic filings 2017-08-04 .. 2026-07-31"),
    ),
    "JNS": (
        ("0001065865", "", "2011-11-23", "JANUS CAPITAL GROUP INC",
         "tier answered 0000812295 JANUS CAPITAL CORP, which files no periodic report at all; the "
         "index member is Janus Capital Group Inc, 68 periodic filings 2000-08-14 .. 2017-04-20, "
         "EDGAR former name STILWELL FINANCIAL INC"),
    ),
    "KG": (
        ("0001047699", "", "2010-12-20", "KING PHARMACEUTICALS INC",
         "tier answered 0002055116 Kestrel Group Ltd, whose first periodic filing is 2025-08-15; "
         "the index member is King Pharmaceuticals, 50 periodic filings 1998-08-14 .. 2010-11-05, "
         "acquired by Pfizer 2011-02"),
    ),
    "LBTYA": (
        ("0001316631", "", "2009-12-21", "Liberty Global, Inc.",
         "Liberty Global, Inc., 32 periodic filings 2005-08-11 .. 2013-05-06"),
        ("0001570585", "2012-12-24", "2020-12-21", "Liberty Global Ltd.",
         "the 2013 UK holding company, first periodic filing 2013-08-01; EDGAR name Liberty Global "
         "plc through the span"),
    ),
    "LIFE": (
        ("0001073431", "", "2014-01-24", "Life Technologies Corp",
         "tier answered 0001788451 Ethos Technologies Inc.; the index member is Life Technologies "
         "Corp, 59 periodic filings 1999-05-11 .. 2013-11-05, EDGAR former name INVITROGEN CORP; "
         "acquired by Thermo Fisher 2014-02"),
    ),
    "MDT": (
        ("0000064670", "", "2015-02-27", "MEDTRONIC INC",
         "held MDT until the 2015 Covidien acquisition and Irish domicile; 85 periodic filings "
         "1994-03-04 .. 2015-02-27. The two rows meet at the successor's first periodic filing "
         "(2015-02-27), which is the first date any fact of the successor's exists"),
        ("0001613103", "2015-02-27", "", "Medtronic plc",
         "the 2015 Covidien acquisition and Irish domicile; first periodic filing 2015-02-27, "
         "measured from its submissions JSON"),
    ),
    "MFE": (
        ("0000890801", "", "2011-03-01", "McAfee, Inc.",
         "tier answered 0001095388 MCAFEE COM CORP, a different entity whose periodic filings stop "
         "2000-03-29; the index member is McAfee, Inc., 60 periodic filings 1996-05-08 .. "
         "2011-02-28, EDGAR former names NETWORKS ASSOCIATES INC/, NETWORK ASSOCIATES INC and "
         "MCAFEE ASSOCIATES INC; acquired by Intel 2011-02-28"),
    ),
    "MI": (
        ("0001399315", "", "2011-07-06", "MARSHALL & ILSLEY CORP",
         "tier answered 0001958713 NFT Ltd; the index member is Marshall & Ilsley Corp, 15 periodic "
         "filings 2007-11-09 .. 2011-05-10, EDGAR former name NEW M&I CORP (the 2007 holding "
         "company). Not 0000062741 MARSHALL & ILSLEY CORP/WI/, whose filings end 2007-08-08"),
    ),
    "MICC": (
        ("0000912958", "", "2011-05-27", "MILLICOM INTERNATIONAL CELLULAR SA",
         "tier answered 0002071668 Magnum Ice Cream Co N.V.; the index member is Millicom "
         "International Cellular S.A., 19 periodic filings 2002-06-25 .. 2026-03-24"),
    ),
    "MMI": (
        ("0001495569", "", "2012-05-22", "Motorola Mobility Holdings, Inc",
         "tier answered 0001578732 Marcus & Millichap, Inc.; the index member is Motorola Mobility "
         "Holdings, the 2011-01-04 Motorola split, 6 periodic filings 2011-02-18 .. 2012-05-01, "
         "EDGAR former name Motorola SpinCo Holdings Corp; acquired by Google 2012-05-22"),
    ),
    "MRVL": (
        ("0001058057", "", "2012-12-24", "MARVELL TECHNOLOGY GROUP LTD",
         "the Bermuda Marvell Technology Group Ltd, 83 periodic filings 2000-09-12 .. 2021-03-16"),
        ("0001835632", "2020-12-21", "", "Marvell Technology, Inc.",
         "the 2021 Delaware redomiciliation, first periodic filing 2021-06-09"),
    ),
    "NSM": (
        ("0000070530", "", "2011-09-26", "NATIONAL SEMICONDUCTOR CORP",
         "tier answered 0001520566 Nationstar Mortgage Holdings, which IPO'd in 2012; the index "
         "member is National Semiconductor, 70 periodic filings 1994-03-18 .. 2011-07-27, acquired "
         "by Texas Instruments 2011-09-23"),
    ),
    "NYX": (
        ("0001368007", "", "2013-11-13", "NYSE Euronext",
         "tier answered 0001679379 NYIAX, INC.; the index member is NYSE Euronext, 28 periodic "
         "filings 2007-03-22 .. 2013-11-05, acquired by IntercontinentalExchange 2013-11-13"),
    ),
    "PRGO": (
        ("0000820096", "", "2013-11-04", "PERRIGO CO",
         "held PRGO until the 2013 Elan acquisition and Irish domicile; 71 periodic filings "
         "1996-05-09 .. 2013-11-04. The two rows meet at the successor's first periodic filing "
         "(2013-11-04), which is the first date any fact of the successor's exists"),
        ("0001585364", "2013-11-04", "2021-09-20", "PERRIGO Co plc",
         "the 2013 Elan acquisition and Irish domicile; first periodic filing 2013-11-04, measured "
         "from its submissions JSON"),
    ),
    "Q": (
        ("0001037949", "", "2011-04-01", "QWEST COMMUNICATIONS INTERNATIONAL INC",
         "Qwest held Q until CenturyLink closed 2011-04-01; 64 periodic filings 1997-08-14 .. "
         "2013-11-13. The ticker was reissued to the 2025 DuPont electronics spinoff, and tier 1 "
         "answers with that one -- the EARLY screen caught it because Qnity's first periodic filing "
         "is 2025-11-18"),
        ("0002058873", "2025-11-03", "", "Qnity Electronics, Inc.",
         "the 2025 DuPont electronics spinoff, first periodic filing 2025-11-18; membership resumes "
         "2025-11-03, so the two tenures cannot overlap"),
    ),
    "RX": (
        ("0001058083", "", "2010-02-26", "IMS HEALTH INC",
         "tier answered 0001595262 IMS HEALTH HOLDINGS, INC., the 2014 re-IPO entity; the index "
         "member is the original IMS Health Inc, 47 periodic filings 1998-08-14 .. 2010-02-17, "
         "taken private 2010-02-26"),
    ),
    "S": (
        ("0000101830", "", "2013-07-09", "SPRINT LLC",
         "tier answered 0001583708 SentinelOne, Inc., which holds S today; in this span the ticker "
         "was Sprint Nextel Corp, 104 periodic filings 1994-03-15 .. 2020-01-27, EDGAR former names "
         "SPRINT CORP and SPRINT NEXTEL CORP; SoftBank closed 2013-07-10. Like GOLD, a recycled "
         "ticker neither screen can catch on its own"),
    ),
    "SGP": (
        ("0000310158", "", "2009-11-04", "Merck & Co., Inc.",
         "tier answered 0001778922 SpyGlass Pharma, Inc.; the index member is Schering-Plough Corp, "
         "which was the surviving registrant of the 2009-11-03 Merck reverse merger and so is EDGAR "
         "CIK 0000310158 with former name SCHERING PLOUGH CORP; 131 periodic filings 1994-03-07 .. "
         "2026-08-07"),
    ),
    "SII": (
        ("0000721083", "", "2010-08-27", "SMITH INTERNATIONAL INC",
         "tier answered 0001512920 SPROTT INC.; the index member is Smith International, 67 "
         "periodic filings 1994-03-22 .. 2010-08-06, acquired by Schlumberger 2010-08-27"),
    ),
    "SNDK": (
        ("0001000180", "", "2016-05-12", "SANDISK CORP",
         "the SanDisk Corp that Western Digital acquired 2016-05-12; 80 periodic filings 1996-08-14 "
         ".. 2016-05-02. The shipped file gave this whole span to the 2025 spinoff, so the row was "
         "already wrong before the re-floor"),
        ("0002023554", "2025-11-28", "", "Sandisk Corp",
         "the 2025 Western Digital spinoff, first periodic filing 2025-03-07"),
    ),
    "STR": (
        ("0000751652", "", "2010-07-01", "DOMINION QUESTAR CORP",
         "tier answered 0001703785 STR Sub Inc.; the index member is Questar Corp, 92 periodic "
         "filings 1994-03-25 .. 2016-08-04, EDGAR former name QUESTAR CORP; the 2010-07-01 span end "
         "is the QEP Resources spinoff"),
    ),
    "SUN": (
        ("0000095304", "", "2012-10-05", "SUNOCO INC",
         "tier answered 0001552275 Sunoco LP, the 2012 MLP; the index member is Sunoco Inc, 75 "
         "periodic filings 1994-03-03 .. 2012-08-02, EDGAR former name SUN CO INC; acquired by "
         "Energy Transfer 2012-10-05"),
    ),
    "WB": (
        ("0000036995", "", "2009-01-02", "WACHOVIA CORP NEW",
         "tier answered 0001595761 WEIBO Corp; in this one-day span the ticker was Wachovia Corp, "
         "60 periodic filings 1994-03-08 .. 2008-10-30, EDGAR former name FIRST UNION CORP; the "
         "Wells Fargo merger closed 2008-12-31. Also in SCREEN_EXEMPT: a one-day span holds no "
         "filing"),
    ),
    "WBA": (
        ("0000104207", "", "2014-12-30", "WALGREEN CO",
         "held WBA until the 2014 Alliance Boots combination; 85 periodic filings 1994-01-13 .. "
         "2014-12-30. The two rows meet at the successor's first periodic filing (2014-12-30), "
         "which is the first date any fact of the successor's exists"),
        ("0001618921", "2014-12-30", "2025-08-28", "Walgreens Boots Alliance, Inc.",
         "the 2014 Alliance Boots combination; first periodic filing 2014-12-30, measured from its "
         "submissions JSON"),
    ),
    "WFT": (
        ("0001170565", "", "2009-02-26", "WEATHERFORD INTERNATIONAL LTD",
         "tier answered 0000029302 WEATHERFORD ENTERRA INC, whose periodic filings stop 1998-05-15; "
         "the index member is the Bermuda Weatherford International Ltd, 27 periodic filings "
         "2002-08-14 .. 2009-02-24 -- the last of them two days inside this span"),
    ),
    "XOM": (
        ("0000034088", "", "2026-08-03", "EXXON MOBIL CORP",
         "held XOM until the 2026 holding-company reorganisation; 131 periodic filings 1994-03-11 "
         ".. 2026-08-03. The two rows meet at the successor's first periodic filing (2026-08-03), "
         "which is the first date any fact of the successor's exists"),
        ("0002115436", "2026-08-03", "", "ExxonMobil Holdings Corp",
         "the 2026 holding-company reorganisation; first periodic filing 2026-08-03, measured from "
         "its submissions JSON"),
    ),
    "XRX": (
        ("0000108772", "", "2019-08-06", "XEROX CORP",
         "held XRX until the 2019 holding-company reorganisation; 127 periodic filings 1995-03-30 "
         ".. 2026-08-06. The two rows meet at the successor's first periodic filing (2019-08-06), "
         "which is the first date any fact of the successor's exists"),
        ("0001770450", "2019-08-06", "2021-03-22", "Xerox Holdings Corp",
         "the 2019 holding-company reorganisation; first periodic filing 2019-08-06, measured from "
         "its submissions JSON"),
    ),
    "TWX": (
        ("0001105705", "", "2018-06-15", "WARNER MEDIA, LLC",
         "name match picked 0000736157 TIME WARNER COMPANIES INC, whose filings end 2006; the "
         "index member is CIK 0001105705, EDGAR former names AOL TIME WARNER INC then TIME WARNER "
         "INC., acquired by AT&T 2018-06-14; 14 periodic filings inside the span"),
    ),
    "WFM": (
        ("0000865436", "", "2017-08-28", "WHOLE FOODS MARKET INC",
         "name match picked 0001681416 Whole Foods Market Group, Inc., a subsidiary with 8 "
         "registration-statement filings; the index member is CIK 0000865436, acquired by Amazon "
         "2017-08-28; 11 periodic filings inside the span"),
    ),
    "WFMI": (
        ("0000865436", "", "2016-12-19", "WHOLE FOODS MARKET INC",
         "the pre-alias spelling of WFM, the same filer; name match picked the subsidiary "
         "0001681416; 8 periodic filings inside the span"),
    ),
}



# Symbols whose absence of a periodic filing inside the span was hand-verified on 2026-10-05 and
# explained. The screen is a net for the automated tiers, not a correctness gate: a row that is
# right can still show zero filings, and without this the generator could never exit 0 on a
# correct file. Every entry records why. Checked against data.sec.gov/submissions.
SCREEN_EXEMPT: dict[str, str] = {
    "BE": "Bloom Energy; span opens 2026-09-21 and no 10-Q has fallen due since",
    "FCPT": "Four Corners Property Trust; 7-day span right after the 2015-11 Darden spinoff",
    "FRC": "First Republic Bank is a bank, not a holding company: it filed its periodic reports "
           "with the FDIC under Exchange Act s12(i), so EDGAR holds none",
    "NBIS": "Nebius Group N.V. (former Yandex N.V.); a foreign private issuer filing 20-F/6-K, "
            "and the span opens 2026-06-22",
    "P": "Everpure, Inc. (former Pure Storage, Inc.); span opens 2026-09-21",
    "PETM": "PetSmart Inc; 10-week span, taken private 2015-03-11 before the FY2014 10-K was due",
    "RDDT": "Reddit, Inc.; span opens 2026-08-18",
    "SBNY": "Signature Bank is a bank, not a holding company: periodic reports went to the FDIC "
            "under Exchange Act s12(i), not EDGAR",
    "SWY": "Safeway Inc; 25-day span, acquired by Albertsons 2015-01-30 before the FY2014 10-K",
    "VMRK": "VIVMARK RESIDENTIAL (former EQUITY RESIDENTIAL, renamed 2026-08-12); span opens "
            "2026-08-18",
    "VSNT": "Versant Media Group; 4-day span 2026-01-05 .. 2026-01-09",
    # added 2026-10-05 with the 2009 floor: spans of days around the 2008-09 crisis closings,
    # each shorter than the next periodic report's due date. The CIK is right in every case.
    "ACAS": "American Capital, Ltd; 62-day span, the FY2008 10-K fell after 2009-03-04",
    "FMCN": "Focus Media Holding; 20-day span, and a 20-F annual filer so nothing was due",
    "MER": "Merrill Lynch & Co; one-day span, the Bank of America merger closed 2009-01-01",
    "NCC": "National City Corp; one-day span, the PNC merger closed 2008-12-31",
    "SOV": "Sovereign Bancorp (EDGAR now Santander Holdings USA); 29-day span to the 2009-01-30 "
           "Santander close, inside which no periodic report fell due",
    "UST": "UST Inc; 5-day span, acquired by Altria 2009-01-06",
    "WB": "Wachovia Corp; one-day span, the Wells Fargo merger closed 2008-12-31",
}

# Symbols whose absence of a periodic filing in the FIRST EARLY_WINDOW_DAYS of the span was
# hand-verified and explained. Separate from SCREEN_EXEMPT because the questions differ: that
# table waives "filed nothing anywhere in the span", this one waives "filed nothing at the span's
# open". A symbol here is still subject to SCREEN_EXEMPT's screen and vice versa. Every entry
# records what was checked against data.sec.gov/submissions. Add; never remove, never weaken.
EARLY_EXEMPT: dict[str, str] = {
    "FRC": "First Republic Bank is a bank, not a holding company: it filed its periodic reports "
           "with the FDIC under Exchange Act s12(i), so EDGAR holds none at any date in the span",
    "SBNY": "Signature Bank is a bank, not a holding company: periodic reports went to the FDIC "
            "under Exchange Act s12(i), not EDGAR, for the whole span",
    # Current members whose span opened too recently for a periodic report to have fallen due.
    "BE": "Bloom Energy; span opens 2026-09-21 and no 10-Q has fallen due since",
    "NBIS": "Nebius Group N.V.; a foreign private issuer filing 20-F annually, and the span "
            "opens 2026-06-22",
    "P": "Everpure, Inc. (former Pure Storage, Inc.); span opens 2026-09-21",
    "RDDT": "Reddit, Inc.; span opens 2026-08-18",
    "VMRK": "VIVMARK RESIDENTIAL (former EQUITY RESIDENTIAL, renamed 2026-08-12); span opens "
            "2026-08-18",
    # Symbols whose MEMBERSHIP hull opens before the ticker itself existed, so there is no
    # earlier holder to split the tenure with. The hull is what membership_overrides.csv says
    # and correcting it belongs to that file, not here -- the same argument the NDOI note makes.
    # The filer named on the row is the right one for every date the symbol actually traded.
    "CCEP": "Coca-Cola Europacific Partners plc was incorporated 2016-05-28 and files 20-F "
            "annually (first 2017-04-12); the hull opens 2016-01-04 on the predecessor CCE slot",
    "DXC": "DXC Technology was created by the 2017-04-03 CSC/HPE Enterprise Services merger and "
           "the ticker DXC with it; the hull opens 2009-01-01 on the CSC slot",
    "LMCK": "LMCK is the Liberty Media Series C tracking stock created in 2014; the filer "
            "0001560385 first filed 2013-02-28 and the hull opens 2009-01-01 on an earlier "
            "Liberty slot",
    "PSKY": "Paramount Skydance Corp and the ticker PSKY both date from the 2025-08-07 close; "
            "the hull opens 2009-01-01 on the Viacom/CBS slot",
    "VTRS": "Viatris and the ticker VTRS date from the 2020-11-16 Mylan/Upjohn combination; the "
            "hull opens 2009-01-01 on the Mylan slot",
}

# --- plumbing -----------------------------------------------------------------------------


class BuildError(RuntimeError):
    """The generator cannot produce a trustworthy file."""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class SecFetcher:
    """GET from sec.gov with the contact-carrying User-Agent SEC's fair-access policy wants."""

    def __init__(self, contact: str, cache: Path) -> None:
        if "@" not in contact:
            raise BuildError(
                "SEC_CONTACT_EMAIL (or --contact) must be a contact email address; SEC's "
                "fair-access policy requires one in the User-Agent"
            )
        self.user_agent = f"seer-engine ticker_cik builder {contact}"
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self._last = 0.0

    def _pace(self) -> None:
        wait = self._last + SEC_MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def bytes(self, url: str, name: str) -> bytes:
        path = self.cache / name
        if path.exists():
            return path.read_bytes()
        self._pace()
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            body = urllib.request.urlopen(req, timeout=120).read()
        finally:
            self._last = time.monotonic()
        path.write_bytes(body)
        return body

    def text(self, url: str, name: str, encoding: str = "utf-8") -> str:
        return self.bytes(url, name).decode(encoding, "replace")

    def json(self, url: str, name: str) -> Any:
        return json.loads(self.text(url, name))


# --- name normalisation --------------------------------------------------------------------


def canonical_name(raw: str) -> str:
    """Upper-case, punctuation-free, corporate suffixes stripped."""
    text = _PUNCT.sub(" ", raw.upper())
    text = _SPACE.sub(" ", text).strip()
    changed = True
    while changed:
        changed = False
        for suffix in SUFFIXES:
            if text == suffix:
                continue
            if text.startswith(suffix + " "):
                text, changed = text[len(suffix) + 1:].strip(), True
            if text.endswith(" " + suffix):
                text, changed = text[: -len(suffix) - 1].strip(), True
    return text


def load_cik_lookup(fetcher: SecFetcher) -> dict[str, list[str]]:
    """``canonical_name -> [cik, ...]`` from cik-lookup-data.txt (39 MB, latin-1)."""
    text = fetcher.text(CIK_LOOKUP_URL, "cik-lookup-data.txt", encoding="latin-1")
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        parts = line.rstrip(":").rsplit(":", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            continue
        key = canonical_name(parts[0])
        if not key:
            continue
        cik = parts[1].zfill(10)
        bucket = out.setdefault(key, [])
        if cik not in bucket:
            bucket.append(cik)
    log(f"cik-lookup-data.txt: {len(out)} canonical names")
    return out


# --- tiers ----------------------------------------------------------------------------------


def tier_current(fetcher: SecFetcher) -> dict[str, tuple[str, str]]:
    """``symbol -> (cik, title)`` from company_tickers.json."""
    raw = fetcher.json(COMPANY_TICKERS_URL, "company_tickers.json")
    out: dict[str, tuple[str, str]] = {}
    for entry in raw.values():
        try:
            symbol = membership.normalize_ticker(str(entry["ticker"]))
        except membership.MembershipError:
            continue
        out.setdefault(symbol, (str(entry["cik_str"]).zfill(10), str(entry["title"])))
    log(f"company_tickers.json: {len(out)} tickers")
    return out


_ATOM_CIK = re.compile(r"<cik>(\d+)</cik>")
_ATOM_NAME = re.compile(r"<conformed-name>([^<]*)</conformed-name>")


def tier_edgar(fetcher: SecFetcher, symbol: str) -> tuple[str, str] | None:
    """``(cik, conformed name)`` from EDGAR's ticker lookup, or None."""
    query = urllib.parse.urlencode(
        {
            "action": "getcompany",
            "CIK": symbol.replace(".", "-"),
            "type": "10-K",
            "dateb": "",
            "owner": "include",
            "count": "1",
            "output": "atom",
        }
    )
    body = fetcher.text(f"{BROWSE_EDGAR_URL}?{query}", f"browse-{symbol}.atom")
    cik, name = _ATOM_CIK.search(body), _ATOM_NAME.search(body)
    if cik is None:
        return None
    return cik.group(1).zfill(10), (name.group(1) if name else "")


def massive_delisted_names(api_key: str, cache: Path) -> dict[str, str]:
    """``symbol -> company name`` for every inactive US stock ticker Massive knows.

    ~23,500 tickers over ~24 pages. The free tier allows 5 calls/min, so this takes ~5 minutes
    on a cold cache.
    """
    path = cache / "massive_delisted.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        log(f"massive delisted (cached): {len(data)} tickers")
        return data
    out: dict[str, str] = {}
    url = MASSIVE_TICKERS_URL
    params: dict[str, Any] = {"market": "stocks", "active": "false", "limit": 1000}
    last = 0.0
    for page in range(MASSIVE_MAX_PAGES):
        wait = last + MASSIVE_MIN_INTERVAL - time.monotonic()
        if wait > 0 and page:
            time.sleep(wait)
        try:
            data = http.get_json(url, {**params, "apiKey": api_key}, retries=4, backoff=15.0)
        finally:
            last = time.monotonic()
        for row in data.get("results") or []:
            raw_ticker, name = row.get("ticker"), row.get("name")
            if not raw_ticker or not name:
                continue
            try:
                symbol = membership.normalize_ticker(str(raw_ticker))
            except membership.MembershipError:
                continue
            out.setdefault(symbol, str(name))
        log(f"massive delisted page {page + 1}: {len(out)} tickers so far")
        next_url = data.get("next_url")
        if not next_url:
            break
        url, params = next_url, {}
    else:
        raise BuildError(f"massive delisted: more than {MASSIVE_MAX_PAGES} pages")
    path.write_text(json.dumps(out, indent=0, sort_keys=True), encoding="utf-8")
    return out


def match_name(name: str, lookup: dict[str, list[str]]) -> tuple[str, str, str] | None:
    """``(cik, matched name, 'exact'|'fuzzy')`` for a company name, or None."""
    key = canonical_name(name)
    if not key:
        return None
    hit = lookup.get(key)
    if hit and len(hit) == 1:
        return hit[0], key, "exact"
    if hit:
        return hit[0], key, "exact"
    close = difflib.get_close_matches(key, lookup.keys(), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return lookup[close[0]][0], close[0], "fuzzy"
    return None


# --- the periodic-filing screen ---------------------------------------------------------------


#: cik -> every periodic filingDate it has, ascending. Filled by periodic_dates; the submissions
#: JSON is parsed once per run however many screens ask about it.
_PERIODIC_CACHE: dict[str, tuple[str, ...]] = {}


def periodic_dates(fetcher: SecFetcher, cik: str) -> tuple[str, ...]:
    """Every periodic-report ``filingDate`` ``cik`` has on EDGAR, ascending ISO strings.

    The ``recent`` block holds only the newest 1000 filings; everything older lives in the
    overflow files the submissions JSON lists under ``filings.files``, and a long-lived filer's
    2009 reports are always in there. Both are read.
    """
    cached = _PERIODIC_CACHE.get(cik)
    if cached is not None:
        return cached
    data = fetcher.json(SUBMISSIONS_URL.format(cik=cik), f"submissions-{cik}.json")
    found: list[str] = []

    def take(block: dict[str, Any]) -> None:
        for form, filed in zip(block.get("form", []), block.get("filingDate", [])):
            if form in PERIODIC_FORMS:
                found.append(filed)

    take(data.get("filings", {}).get("recent", {}))
    for extra in data.get("filings", {}).get("files", []):
        take(fetcher.json(
            "https://data.sec.gov/submissions/" + extra["name"], f"submissions-{extra['name']}"
        ))
    dates = tuple(sorted(found))
    _PERIODIC_CACHE[cik] = dates
    return dates


def filed_inside(fetcher: SecFetcher, cik: str, start: date, end: date | None) -> int:
    """How many periodic reports ``cik`` filed with filingDate in ``[start, end)``."""
    lo, hi = start.isoformat(), (end.isoformat() if end else "9999-12-31")
    return sum(1 for filed in periodic_dates(fetcher, cik) if lo <= filed < hi)


# --- assembly -----------------------------------------------------------------------------


def spans(intervals: Iterable[membership.Interval]) -> dict[str, tuple[date, date | None]]:
    """``symbol -> (start, end)``: the hull of its membership, clipped to ``[SINCE, ...)``.

    The hull, not the individual intervals: a symbol that leaves an index and rejoins still had
    a filer in between, so covering the gap is both correct and simpler.
    """
    out: dict[str, tuple[date, date | None]] = {}
    for iv in intervals:
        start = max(iv.start_date, SINCE)
        if iv.end_date is not None and iv.end_date <= SINCE:
            continue
        prev = out.get(iv.symbol)
        if prev is None:
            out[iv.symbol] = (start, iv.end_date)
            continue
        p_start, p_end = prev
        new_end = None if (p_end is None or iv.end_date is None) else max(p_end, iv.end_date)
        out[iv.symbol] = (min(p_start, start), new_end)
    return out


def build(args: argparse.Namespace) -> int:
    cache = Path(args.cache).resolve()
    contact = args.contact or os.environ.get("SEC_CONTACT_EMAIL") or ""
    fetcher = SecFetcher(contact, cache)

    intervals = membership.compute_universe(membership.DATA_DIR)
    span = spans(intervals)
    symbols = sorted(span)
    log(f"ever-members since {SINCE}: {len(symbols)}")

    rows: list[dict[str, str]] = []
    resolved: set[str] = set()
    counts: dict[str, int] = {s: 0 for s in ("manual", "current", "edgar", "exact", "fuzzy")}

    # tier 0 -- manual
    for symbol, entries in MANUAL.items():
        if symbol not in span:
            raise BuildError(f"MANUAL has {symbol}, which is not an ever-member since {SINCE}")
        for position, (cik, start, end, name, note) in enumerate(entries):
            if not start and position:
                raise BuildError(
                    f"MANUAL {symbol}: only the first row may leave start empty; row "
                    f"{position + 1} is a handover and must carry its literal start date"
                )
            rows.append(
                {
                    "symbol": symbol,
                    "cik": cik,
                    "start_date": start or span[symbol][0].isoformat(),
                    "end_date": end,
                    "company_name": name,
                    "source": "manual",
                    "note": note,
                }
            )
        resolved.add(symbol)
        counts["manual"] += 1

    # tier 1 -- company_tickers.json
    current = tier_current(fetcher)
    for symbol in symbols:
        if symbol in resolved or symbol not in current:
            continue
        cik, name = current[symbol]
        rows.append(_row(symbol, cik, name, "current", "", span))
        resolved.add(symbol)
        counts["current"] += 1

    # tier 2 -- EDGAR's ticker lookup
    for symbol in symbols:
        if symbol in resolved:
            continue
        hit = tier_edgar(fetcher, symbol)
        if hit is None:
            continue
        cik, name = hit
        rows.append(_row(symbol, cik, name, "edgar", "", span))
        resolved.add(symbol)
        counts["edgar"] += 1

    # tiers 3-4 -- Massive delisted name -> cik-lookup-data.txt
    remaining = [s for s in symbols if s not in resolved]
    if remaining:
        log(f"{len(remaining)} symbols need the name-matching path")
        names = massive_delisted_names(config.require("MASSIVE_API_KEY"), cache)
        lookup = load_cik_lookup(fetcher)
        for symbol in remaining:
            raw_name = names.get(symbol)
            if not raw_name:
                continue
            hit = match_name(raw_name, lookup)
            if hit is None:
                continue
            cik, matched, kind = hit
            note = f"massive name {raw_name!r} -> cik-lookup {matched!r} ({kind})"
            rows.append(_row(symbol, cik, raw_name, kind, note, span))
            resolved.add(symbol)
            counts[kind] += 1

    unresolved = [s for s in symbols if s not in resolved]
    if unresolved:
        log("")
        log(f"UNRESOLVED ({len(unresolved)}) -- add each to MANUAL after checking EDGAR by hand:")
        for symbol in unresolved:
            start, end = span[symbol]
            log(f"  {symbol:8s} {start} .. {end or 'open'}")
        return 1

    # the screens. Two questions, one submissions JSON per CIK:
    #   1. did this filer file a periodic report anywhere inside the span?  (wrong company)
    #   2. did it file one near the START of the span?                      (start extended back
    #      past a handover -- invisible to question 1, because the later filings still count)
    suspect: list[str] = []
    late: list[str] = []
    for row in rows:
        if row["cik"] == NO_FILER:
            continue  # no filer to screen; the NONE row is itself the audited answer
        start = date.fromisoformat(row["start_date"])
        end = date.fromisoformat(row["end_date"]) if row["end_date"] else None
        if row["symbol"] not in SCREEN_EXEMPT:
            if filed_inside(fetcher, row["cik"], start, end) == 0:
                suspect.append(f"{row['symbol']} -> {row['cik']} {row['company_name']}")
        if row["symbol"] in EARLY_EXEMPT:
            continue  # hand-verified silence at the span's open; see EARLY_EXEMPT
        window_end = start + timedelta(days=EARLY_WINDOW_DAYS)
        if end is not None and end <= window_end:
            continue  # the span is shorter than the window; question 1 already asked this
        if filed_inside(fetcher, row["cik"], start, window_end) == 0:
            known = periodic_dates(fetcher, row["cik"])
            first = known[0] if known else "never"
            late.append(
                f"{row['symbol']} -> {row['cik']} {row['company_name']}: span opens "
                f"{start}, first periodic filing {first}"
            )
    if suspect:
        log("")
        log(f"SCREEN ({len(suspect)}) -- no periodic filing inside the span; wrong company, a "
            f"filer change mid-span, or a genuinely silent filer. Resolve each in MANUAL:")
        for line in suspect:
            log(f"  {line}")
    if late:
        log("")
        log(f"EARLY ({len(late)}) -- no periodic filing in the first {EARLY_WINDOW_DAYS} days "
            f"of the span, so the start reaches back past this filer. Split the tenure into two "
            f"dated MANUAL rows, or exempt it in EARLY_EXEMPT with the reason:")
        for line in late:
            log(f"  {line}")
    if suspect or late:
        return 1

    rows.sort(key=lambda r: (r["symbol"], r["start_date"]))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(HEADER), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    log("")
    log(f"wrote {out_path}: {len(rows)} rows, {len(resolved)} symbols")
    log("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def _row(
    symbol: str,
    cik: str,
    name: str,
    source: str,
    note: str,
    span: dict[str, tuple[date, date | None]],
) -> dict[str, str]:
    start, end = span[symbol]
    return {
        "symbol": symbol,
        "cik": cik,
        "start_date": start.isoformat(),
        "end_date": end.isoformat() if end else "",
        "company_name": name,
        "source": source,
        "note": note,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="engine/data/ticker_cik.csv")
    parser.add_argument("--cache", default="engine/.cache/cik")
    parser.add_argument("--contact", default=None, help="defaults to $SEC_CONTACT_EMAIL")
    try:
        return build(parser.parse_args(argv))
    except (BuildError, config.ConfigError) as exc:
        log(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
