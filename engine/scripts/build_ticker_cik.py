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

Measured 2026-10-05 over the 795 ever-members: MANUAL covers 9 symbols (CA and DTV reach no
tier at all), tier 1 resolves 649 of the rest and tier 2 a further 51, leaving 93 for tiers 3-4.

A ticker alone never identifies a company: tiers 1-2 answer with whoever holds the ticker TODAY.
The screen below (a candidate must have filed a periodic report inside the symbol's membership
span) rejected the wrong answers for MON, PLL and ALTR but NOT for LLL or DTV, so the six
recycled tickers stay in MANUAL permanently.
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
from datetime import date
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

SUFFIXES = (
    "INC", "CORP", "CORPORATION", "CO", "COMPANY", "PLC", "LTD", "LIMITED", "LP", "LLC",
    "HOLDINGS", "HOLDING", "GROUP", "THE", "CLASS A", "CLASS B", "CLASS C", "COM", "NEW",
)
_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_SPACE = re.compile(r"\s+")

# symbol -> ((cik, start, end, company_name, note), ...). end "" means still current.
# Hand-audited; wins over every automated tier. Every CIK below was confirmed against
# https://data.sec.gov/submissions/CIK<cik>.json on 2026-10-05.
MANUAL: dict[str, tuple[tuple[str, str, str, str, str], ...]] = {
    # --- recycled tickers: EDGAR's ticker lookup answers with today's holder -------------
    "CA": (
        ("0000356028", "2015-01-02", "2018-11-06", "CA, INC.",
         "recycled: CA is now an Xtrackers ETF share class; CA Inc (ex-Computer Associates) "
         "was acquired by Broadcom 2018-11-05"),
    ),
    "MON": (
        ("0001110783", "2015-01-02", "2018-06-07", "MONSANTO CO /NEW/",
         "recycled: browse-edgar answers 0001828325 Monument Circle Acquisition Corp; "
         "Monsanto was acquired by Bayer 2018-06-07"),
    ),
    "PLL": (
        ("0000075829", "2015-01-02", "2015-08-31", "PALL CORP",
         "recycled: browse-edgar answers 0001728205 Piedmont Lithium; Pall Corp was acquired "
         "by Danaher 2015-08-31"),
    ),
    "ALTR": (
        ("0000768251", "2015-01-02", "2015-12-28", "ALTERA CORP",
         "recycled: browse-edgar answers 0001701732 Altair Engineering; Altera was acquired "
         "by Intel 2015-12-28"),
    ),
    "LLL": (
        ("0001039101", "2015-01-02", "2019-07-01", "L3 TECHNOLOGIES, INC.",
         "recycled: browse-edgar answers 0001546383 JX Luxventure, which also filed 5 periodic "
         "reports inside the span, so the filing screen does NOT catch it; L3 merged with "
         "Harris 2019-06-29"),
    ),
    "DTV": (
        ("0001465112", "2015-01-02", "2015-07-27", "DIRECTV",
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
        ("0001288776", "2015-01-02", "2015-10-02", "GOOGLE INC.",
         "Google Inc was the registrant until the Alphabet holdco reorg closed 2015-10-02"),
        ("0001652044", "2015-10-02", "", "ALPHABET INC.", "Alphabet holdco reorg 2015-10-02"),
    ),
    "GOOG": (
        ("0001288776", "2015-01-02", "2015-10-02", "GOOGLE INC.",
         "class C of the same filer as GOOGL; Google Inc until 2015-10-02"),
        ("0001652044", "2015-10-02", "", "ALPHABET INC.", "Alphabet holdco reorg 2015-10-02"),
    ),
    # --- hand-audited 2026-10-05: the 33 the automated tiers left unresolved -------------
    "AABA": (
        ("0001011006", "2015-01-02", "2017-06-19", "ALTABA INC.",
         "EDGAR former name YAHOO INC (1996-08-14..2017-06-15); the operating business went to "
         "Verizon 2017-06-13 and the rump became Altaba; 10 periodic filings inside the span"),
    ),
    "ADS": (
        ("0001101215", "2015-01-02", "2020-06-22", "BREAD FINANCIAL HOLDINGS, INC.",
         "EDGAR former name ALLIANCE DATA SYSTEMS CORP (2000-06-09..2022-03-23); a pure rename on "
         "the same CIK; 18 periodic filings inside the span"),
    ),
    "BCR": (
        ("0000009892", "2015-01-02", "2017-12-29", "BARD C R INC /NJ/",
         "C.R. Bard, acquired by Becton Dickinson 2017-12-29; 12 periodic filings inside the "
         "span; the predecessor CIK 0000275110 filed none inside it"),
    ),
    "BRCM": (
        ("0001054374", "2015-01-02", "2016-02-01", "BROADCOM CORP",
         "the original Broadcom Corp, acquired by Avago 2016-02-01; Avago then took the Broadcom "
         "name and the AVGO ticker under a different CIK; 4 periodic filings inside the span"),
    ),
    "BXLT": (
        ("0001620546", "2015-07-01", "2016-06-03", "Baxalta Inc",
         "Baxter spinoff 2015-07-01, acquired by Shire 2016-06-03; 4 periodic filings inside the "
         "span"),
    ),
    "CAM": (
        ("0000941548", "2015-01-02", "2016-04-04", "CAMERON INTERNATIONAL CORP",
         "EDGAR former name COOPER CAMERON CORP; acquired by Schlumberger 2016-04-01; 5 periodic "
         "filings inside the span"),
    ),
    "CCE": (
        ("0001491675", "2015-01-02", "2016-05-31", "COCA-COLA EUROPEAN PARTNERS US, LLC",
         "the 2010 Coca-Cola Enterprises, Inc. (EDGAR former name 2010-06-22..2016-05-26); 6 "
         "periodic filings inside the span; NOT 0000804055, the pre-2010 Coca Cola Enterprises "
         "Inc now Coca-Cola Refreshments USA, which filed none inside the span"),
    ),
    "CELG": (
        ("0000816284", "2015-01-02", "2019-11-21", "CELGENE CORP /DE/",
         "acquired by Bristol-Myers Squibb 2019-11-20; 20 periodic filings inside the span"),
    ),
    "CMCSK": (
        ("0001166691", "2015-09-21", "2015-12-14", "COMCAST CORP",
         "Comcast class K special stock: the same filer as CMCSA, which is why no uniqueness "
         "check applies to cik; 1 periodic filing inside the short span (10-Q 2015-10-27), "
         "visible only in the submissions overflow files"),
    ),
    "COV": (
        ("0001385187", "2015-01-02", "2015-01-27", "Covidien plc",
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
        ("0001363851", "2015-01-02", "2015-07-24", "Catamaran Corp",
         "EDGAR former name SXC Health Solutions Corp; acquired by UnitedHealth OptumRx "
         "2015-07-23; 2 periodic filings inside the span"),
    ),
    "CVC": (
        ("0001053112", "2015-01-02", "2016-06-21", "CABLEVISION SYSTEMS CORP /NY",
         "the registrant behind the listed equity, acquired by Altice 2016-06-21; 6 periodic "
         "filings inside the span; NOT 0000784681 CSC Holdings LLC, the debt-issuing subsidiary "
         "that co-files on the very same dates"),
    ),
    "DISCK": (
        ("0001437107", "2015-01-02", "2022-04-11", "Warner Bros. Discovery, Inc.",
         "Discovery series C; EDGAR former names Discovery Communications, Inc. "
         "(2008-06-11..2018-03-05) and Discovery, Inc. (2018-03-06..2022-04-08); the WarnerMedia "
         "merger closed 2022-04-08 on the same CIK; 8 periodic filings inside the span"),
    ),
    "EMC": (
        ("0000790070", "2015-01-02", "2016-09-07", "EMC CORP",
         "acquired by Dell 2016-09-07; 7 periodic filings inside the span"),
    ),
    "FLIR": (
        ("0000354908", "2015-01-02", "2021-05-14", "Teledyne FLIR, LLC",
         "EDGAR former name FLIR SYSTEMS INC (1996-08-14..2021-05-14); acquired by Teledyne "
         "2021-05-14 on the same CIK; 26 periodic filings inside the span"),
    ),
    "GMCR": (
        ("0000909954", "2015-01-02", "2016-03-03", "KEURIG GREEN MOUNTAIN, INC.",
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
        ("0001530721", "2015-01-02", "2018-09-19", "Capri Holdings Ltd",
         "EDGAR former name Michael Kors Holdings Ltd (2011-12-02..2018-12-21); renamed Capri on "
         "the Versace deal, same CIK; 15 periodic filings inside the span"),
    ),
    "KRFT": (
        ("0001545158", "2015-01-02", "2015-07-06", "Kraft Foods Group, Inc.",
         "merged with H.J. Heinz into Kraft Heinz (KHC, its own ever-member) 2015-07-02; 2 "
         "periodic filings inside the span"),
    ),
    "LMCA": (
        ("0001560385", "2015-01-02", "2016-06-20", "Liberty Media Corp",
         "Liberty Media series A; EDGAR former name Liberty Spinco, Inc.; replaced by the Liberty "
         "SiriusXM/Braves/Media tracking stocks in 2016; 6 periodic filings inside the span, "
         "visible only in the submissions overflow files; NOT 0001507934 (Starz, traded STRZA) "
         "nor 0001355096 (Liberty Interactive, traded LVNTA/QVCA)"),
    ),
    "LMCK": (
        ("0001560385", "2015-01-02", "2016-06-20", "Liberty Media Corp",
         "Liberty Media series C, the same filer as LMCA; 6 periodic filings inside the span, "
         "visible only in the submissions overflow files"),
    ),
    "LO": (
        ("0001424847", "2015-01-02", "2015-06-12", "LORILLARD, LLC",
         "EDGAR former name LORILLARD, INC. (2008-02-05..2015-06-12); acquired by Reynolds "
         "American 2015-06-12; 2 periodic filings inside the span"),
    ),
    "NDOI": (
        ("NONE", "2015-01-02", "2016-07-18", "",
         "phantom ticker in the Wikipedia-derived ndx_history.csv: present in every snapshot "
         "2007-02-01..2016-07-18, always between MSFT and NIHD. No EDGAR filer exists - absent "
         "from company_tickers.json, from browse-edgar's ticker lookup, from cik-lookup-data.txt "
         "and from all 21250 of Massive's delisted US tickers. The same file carries NLTI, a "
         "transposition of NTLI (NTL Inc), so mangled tickers are a known defect of this source. "
         "A membership_overrides.csv correction belongs to the membership owner, not to this "
         "phase"),
    ),
    "NFX": (
        ("0000912750", "2015-01-02", "2019-02-15", "NEWFIELD EXPLORATION CO /DE/",
         "acquired by Encana 2019-02-13; 16 periodic filings inside the span"),
    ),
    "PCL": (
        ("0000849213", "2015-01-02", "2016-02-22", "PLUM CREEK TIMBER CO INC",
         "merged into Weyerhaeuser 2016-02-19; 5 periodic filings inside the span"),
    ),
    "SHPG": (
        ("0000936402", "2016-10-19", "2018-12-24", "Shire plc",
         "EDGAR former names Shire Ltd. and SHIRE PHARMACEUTICALS GROUP PLC; acquired by Takeda, "
         "ADSs delisted 2018-12-24; 9 periodic filings inside the span; Massive's name for this "
         "ticker is the OCR artifact 'Shire pic', which is why the automated name match failed"),
    ),
    "SNI": (
        ("0001430602", "2015-01-02", "2018-03-07", "Scripps Networks Interactive, Inc.",
         "acquired by Discovery 2018-03-06; 13 periodic filings inside the span"),
    ),
    "SPLS": (
        ("0000791519", "2015-01-02", "2017-09-13", "STAPLES INC",
         "taken private by Sycamore Partners 2017-09-12; 11 periodic filings inside the span"),
    ),
    "TEG": (
        ("0000916863", "2015-01-02", "2015-06-30", "INTEGRYS HOLDING, INC.",
         "EDGAR former names INTEGRYS ENERGY GROUP, INC. (2007-02-23..2015-06-29) and WPS "
         "RESOURCES CORP; acquired by Wisconsin Energy 2015-06-29; 2 periodic filings inside the "
         "span"),
    ),
    "TWC": (
        ("0001377013", "2015-01-02", "2016-05-18", "SPECTRUM MANAGEMENT HOLDING COMPANY, LLC",
         "EDGAR former name TIME WARNER CABLE INC. (2006-10-18..2016-06-01); acquired by Charter "
         "2016-05-18 on the same CIK; 6 periodic filings inside the span"),
    ),
    "WYND": (
        ("0001361658", "2015-01-02", "2018-05-31", "Travel & Leisure Co.",
         "EDGAR former names WYNDHAM WORLDWIDE CORP (2006-05-11..2018-05-23) and Wyndham "
         "Destinations, Inc. (2018-05-31..2021-02-16); the hotel business spun off as WH "
         "2018-05-31 and the rump kept this CIK; 14 periodic filings inside the span, visible "
         "only in the submissions overflow files"),
    ),
    # --- hand-audited 2026-10-05: the one fuzzy match, which was wrong -------------------
    "HAR": (
        ("0000800459", "2015-01-02", "2017-03-13", "HARMAN INTERNATIONAL INDUSTRIES INC /DE/",
         "the only fuzzy-tier row, and it was wrong: difflib matched Massive's 'Harman "
         "International Industries' to cik-lookup 'AMERICAN INTERNATIONAL INDUSTRIES' "
         "(0001073146), an unrelated company that filed 4 periodic reports inside the span and so "
         "passed the screen -- the same net-not-a-gate failure as LLL and DTV. Harman was "
         "acquired by Samsung 2017-03-10; 9 periodic filings inside the span"),
    ),
    # --- hand-audited 2026-10-05: rows the periodic-filing screen caught -----------------
    "ADT": (
        ("0001546640", "2015-01-02", "2016-05-02", "ADT Corp",
         "recycled: browse-edgar answers 0001703056 ADT Inc., the 2017 Apollo/Prime Security "
         "entity whose filings start 2017-04-11; The ADT Corporation was the 2012 Tyco spinoff, "
         "taken private by Apollo 2016-05-02; 5 periodic filings inside the span"),
    ),
    "APC": (
        ("0000773910", "2015-01-02", "2019-08-09", "ANADARKO PETROLEUM CORP",
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
        ("0001458891", "2015-01-02", "2015-07-20", "Noble Corp",
         "recycled across a reorganisation: the ticker now carries Noble Corp plc 0001895262 "
         "(filings start 2021-12-20, former Noble Finco Ltd); the filer in this window is CIK "
         "0001458891, EDGAR former names Noble Corp / Switzerland and Noble Corp plc; 2 periodic "
         "filings inside the span"),
    ),
    "POM": (
        ("0001135971", "2015-01-02", "2016-03-24", "PEPCO HOLDINGS LLC",
         "recycled: the ticker now carries POMDOCTOR Ltd (0001877971, filings start 2021-09-30); "
         "Pepco Holdings (EDGAR former name PEPCO HOLDINGS INC) was acquired by Exelon "
         "2016-03-23; 5 periodic filings inside the span"),
    ),
    "SE": (
        ("0001373835", "2015-01-02", "2017-02-27", "Spectra Energy Corp.",
         "recycled: the ticker now carries Sea Ltd (0001703399, filings start 2017-04-24); "
         "Spectra Energy merged into Enbridge 2017-02-27; 9 periodic filings inside the span"),
    ),
    "STI": (
        ("0000750556", "2015-01-02", "2019-12-09", "SUNTRUST BANKS INC",
         "recycled: the ticker now carries Solidion Technology (0001881551, former Nubia Brand "
         "International Corp); SunTrust merged with BB&T into Truist 2019-12-06; 20 periodic "
         "filings inside the span"),
    ),
    "TE": (
        ("0000350563", "2015-01-02", "2016-07-01", "TECO ENERGY INC",
         "recycled: the ticker now carries T1 Energy (0001992243, former FREYR Battery); TECO "
         "Energy was acquired by Emera 2016-07-01; 6 periodic filings inside the span"),
    ),
    "VIP": (
        ("0001468091", "2015-01-02", "2015-12-21", "VEON Ltd.",
         "recycled: the ticker now carries Vulcan Infrastructure & Power (0001844971, former "
         "Greenidge Generation); VimpelCom Ltd (EDGAR former name of this CIK until 2017-03-28) "
         "is the filer for this window; 1 periodic filing inside the span (20-F, a foreign "
         "private issuer)"),
    ),
    "PX": (
        ("0000884905", "2015-01-02", "2018-10-31", "LINDE INC",
         "recycled: the ticker now carries Ridgepost Capital (0001841968, former P10 Inc); EDGAR "
         "former name PRAXAIR INC (1995-02-14..2022-02-03) on the same CIK, merged into Linde "
         "2018-10-31; 15 periodic filings inside the span"),
    ),
    "XL": (
        ("0000875159", "2015-01-02", "2018-09-12", "XL GROUP LTD",
         "recycled: the ticker now carries Spruce Power Holding (0001772720, former XL Fleet Corp "
         "/ Pivotal Investment Corp II); XL Group (EDGAR former names XL GROUP PLC, XL CAPITAL "
         "LTD, EXEL LTD) was acquired by AXA 2018-09-12; 15 periodic filings inside the span"),
    ),
    "DNB": (
        ("0001115222", "2015-01-02", "2017-04-05", "DUN & BRADSTREET CORP/NW",
         "the ticker was reissued to Dun & Bradstreet Holdings (0001799208) at its 2020 re-IPO; "
         "the filer for this window is the old Dun & Bradstreet Corp, taken private 2019-02-08; 9 "
         "periodic filings inside the span"),
    ),
    "AET": (
        ("0001122304", "2015-01-02", "2018-11-29", "AETNA INC /PA/",
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
        ("0000791907", "2015-01-02", "2017-03-13", "LINEAR TECHNOLOGY CORP /CA/",
         "name match picked 0001160656 CLEAR TECHNOLOGY INC, an unrelated company with 6 filings "
         "ending 2007; Linear Technology is CIK 0000791907, acquired by Analog Devices "
         "2017-03-10; 9 periodic filings inside the span"),
    ),
    "MJN": (
        ("0001452575", "2015-01-02", "2017-06-15", "Mead Johnson Nutrition Co",
         "two CIKs carry the name: 0001444904 filed only 4 documents in 2008; the listed issuer "
         "is 0001452575, acquired by Reckitt Benckiser 2017-06-15; 10 periodic filings inside the "
         "span"),
    ),
    "MNK": (
        ("0001567892", "2015-01-02", "2017-07-26", "Keenova Therapeutics plc",
         "name match picked 0000051396 MALLINCKRODT INC /MO (former IMCERA GROUP), whose filings "
         "end 2001; the index member is CIK 0001567892, EDGAR former name Mallinckrodt plc "
         "(2013-02-01..2025-11-10); 9 periodic filings inside the span"),
    ),
    "PETM": (
        ("0000863157", "2015-01-02", "2015-03-12", "PETSMART INC",
         "name match picked 0001088628 PETSMART COM INC, the dot-com subsidiary with 2 filings in "
         "2000; the index member is CIK 0000863157, taken private by BC Partners 2015-03-11. No "
         "periodic filing falls inside the 10-week span because the FY2014 10-K was due after the "
         "buyout, so this symbol is also in SCREEN_EXEMPT"),
    ),
    "RTN": (
        ("0001047122", "2015-01-02", "2020-04-06", "RAYTHEON CO/",
         "name match picked 0000082267 RAYTHEON CO, the pre-1997 entity whose filings end "
         "2013-03-25; the index member is CIK 0001047122 (EDGAR former name HE HOLDINGS INC), "
         "merged with United Technologies into Raytheon Technologies 2020-04-03; 21 periodic "
         "filings inside the span"),
    ),
    "TWX": (
        ("0001105705", "2015-01-02", "2018-06-15", "WARNER MEDIA, LLC",
         "name match picked 0000736157 TIME WARNER COMPANIES INC, whose filings end 2006; the "
         "index member is CIK 0001105705, EDGAR former names AOL TIME WARNER INC then TIME WARNER "
         "INC., acquired by AT&T 2018-06-14; 14 periodic filings inside the span"),
    ),
    "WFM": (
        ("0000865436", "2015-01-02", "2017-08-28", "WHOLE FOODS MARKET INC",
         "name match picked 0001681416 Whole Foods Market Group, Inc., a subsidiary with 8 "
         "registration-statement filings; the index member is CIK 0000865436, acquired by Amazon "
         "2017-08-28; 11 periodic filings inside the span"),
    ),
    "WFMI": (
        ("0000865436", "2015-01-02", "2016-12-19", "WHOLE FOODS MARKET INC",
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


def filed_inside(fetcher: SecFetcher, cik: str, start: date, end: date | None) -> int:
    """How many periodic reports ``cik`` filed with filingDate in ``[start, end)``."""
    data = fetcher.json(SUBMISSIONS_URL.format(cik=cik), f"submissions-{cik}.json")
    lo, hi = start.isoformat(), (end.isoformat() if end else "9999-12-31")
    count = 0

    def take(block: dict[str, Any]) -> None:
        nonlocal count
        for form, filed in zip(block.get("form", []), block.get("filingDate", [])):
            if form in PERIODIC_FORMS and lo <= filed < hi:
                count += 1

    take(data.get("filings", {}).get("recent", {}))
    for extra in data.get("filings", {}).get("files", []):
        take(fetcher.json(
            "https://data.sec.gov/submissions/" + extra["name"], f"submissions-{extra['name']}"
        ))
    return count


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
        for cik, start, end, name, note in entries:
            rows.append(
                {
                    "symbol": symbol, "cik": cik, "start_date": start, "end_date": end,
                    "company_name": name, "source": "manual", "note": note,
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

    # the screen
    suspect: list[str] = []
    for row in rows:
        if row["cik"] == NO_FILER:
            continue  # no filer to screen; the NONE row is itself the audited answer
        if row["symbol"] in SCREEN_EXEMPT:
            continue  # hand-verified absence; see SCREEN_EXEMPT for the reason
        start = date.fromisoformat(row["start_date"])
        end = date.fromisoformat(row["end_date"]) if row["end_date"] else None
        if filed_inside(fetcher, row["cik"], start, end) == 0:
            suspect.append(f"{row['symbol']} -> {row['cik']} {row['company_name']}")
    if suspect:
        log("")
        log(f"SCREEN ({len(suspect)}) -- no periodic filing inside the span; wrong company, a "
            f"filer change mid-span, or a genuinely silent filer. Resolve each in MANUAL:")
        for line in suspect:
            log(f"  {line}")
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
