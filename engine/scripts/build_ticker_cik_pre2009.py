"""One-off generator for engine/data/ticker_cik_pre2009.csv. Run by hand, never imported.

    export SEC_CONTACT_EMAIL=you@example.com
    python engine/scripts/build_ticker_cik_pre2009.py --out engine/data/ticker_cik_pre2009.csv

``ticker_cik.csv`` deliberately stops at ``cik.SINCE`` (2009-01-01): it exists to join SEC XBRL
facts, and XBRL does not exist before 2009. Sector labels have no such floor. The index's
1996-2008 membership needs a filer too, or a sector cap would be blind to a third of the
backtest history. This script writes the companion file for exactly that stretch:
``[first membership day, 2009-01-01)`` for every symbol that was an S&P 500 or Nasdaq-100
member before 2009 -- 918 symbols, 352 of them with no row in ``ticker_cik.csv`` at all.

The two files never overlap: every row here ends on or before 2009-01-01 and every row there
starts on or after it, so ``cik.load_index_with_history`` can concatenate them and the merged
index is still one non-overlapping tenure list per symbol.

Membership is split into stints first: overlapping or touching intervals merge, a real gap
starts a new stint, because before 2009 a gap usually means a different company (AMP Inc, then
Ameriprise). Each stint is answered by one of, highest priority first:

  manual  MANUAL below -- hand-audited, with the evidence in the note.
  carry   the stint runs into 2009-01-01 and the symbol's 2009 row in ticker_cik.csv starts
          exactly at that floor (it was clamped there), so the same filer is carried backwards. Screened like everything else: a holdco reorg or a
          merger that put a younger CIK on the ticker shows up as a filer with nothing filed near
          the span's start.
  exact   HINTS below gives the company's name as it was during the membership (from the
          membership source's tickers, Massive's delisted names, Wikipedia's historical-components
          table and hand research); every cik-lookup-data.txt entity whose normalised name
          matches is scored by how many periodic reports it filed over the stint and the 450 days
          before it, and the best one wins. A tie, or a best of zero, is not an answer.

A ticker is never looked up by itself here. Before 2009 the recycling is far worse than after it:
many of the 352 symbols with no 2009 row belong today to an unrelated company (G is Genpact,
not Gillette; H is Hyatt, not Harcourt General; CR is the 2023 Crane Company, not the
Crane Co of 1996, whose CIK is now Crane NXT's). EDGAR's ticker lookup answers with those.

Three screens then run on every row, and none of them is a gate -- see SOURCES.md for the cases
each one misses:

  INSIDE  a row of INSIDE_MIN_DAYS or more holds at least one periodic report.
  EARLY   the filer filed one within EARLY_WINDOW_DAYS either side of the row's start (a start
          that reaches back past a handover: the filer did not exist yet).
  LATE    ... and one in the EARLY_WINDOW_DAYS before the row's end (an end that reaches forward
          past the filer's last report). Waived for rows ending at the 2009-01-01 seam, whose
          filer continues.

EDGAR's electronic filing was phased in from 1993 and became mandatory for every domestic
registrant in May 1996, so a 1996-01-02 start can have nothing electronic before mid-1996; the
450-day window covers that. Foreign private issuers (20-F, 40-F) were not required to file on
EDGAR until 2002, so a Canadian or European member's right filer can fail EARLY; those are in
SCREEN_EXEMPT with the reason. A stint no source can name is NONE, with that said in the note.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from seer_engine import cik, config, membership  # noqa: E402

_BASE_PATH = Path(__file__).resolve().with_name("build_ticker_cik.py")
_spec = importlib.util.spec_from_file_location("build_ticker_cik", _BASE_PATH)
assert _spec is not None and _spec.loader is not None
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

_plain_bytes = base.SecFetcher.bytes


def _bytes_with_retries(self, url: str, name: str) -> bytes:
    """``SecFetcher.bytes`` plus retries: a sweep of ~2,000 SEC calls meets the odd TLS
    handshake timeout, and the base generator would die on the first one. HTTP errors (a 404
    for an unknown CIK) are not retried."""
    import time
    import urllib.error

    for attempt in range(5):
        try:
            return _plain_bytes(self, url, name)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            log(f"retry {attempt + 1}/5 after {exc} for {name}")
            time.sleep(2 * (attempt + 1))
    return _plain_bytes(self, url, name)


base.SecFetcher.bytes = _bytes_with_retries

CUTOFF = cik.SINCE
EARLY_WINDOW_DAYS = base.EARLY_WINDOW_DAYS
SUBMISSIONS_URL = base.SUBMISSIONS_URL
MAX_CANDIDATES = 15

_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_SPACE = re.compile(r"\s+")
_DROP = (
    "INC", "CORP", "CORPORATION", "CO", "COMPANY", "PLC", "LTD", "LIMITED", "LP", "LLC",
    "HOLDINGS", "HOLDING", "THE", "COM", "NEW", "DE", "NY", "NJ", "OH", "PA", "MD", "VA", "DEL",
    "AND", "INCORPORATED", "CL", "A", "B", "NV", "N V", "SA",
)


def canon(raw: str) -> str:
    """Upper-case, apostrophes and periods deleted, other punctuation spaced, suffixes dropped.

    Stricter than build_ticker_cik.canonical_name in one way that matters here: ``WENDY'S`` must
    meet EDGAR's ``WENDYS``, and ``W.R. GRACE`` must meet ``W R GRACE``, so apostrophes vanish
    while periods between initials become nothing too.
    """
    text = raw.upper().replace("'", "").replace("’", "").replace("&", " AND ")
    text = text.split("/")[0]
    text = _PUNCT.sub(" ", text.replace(".", " "))
    words = [w for w in _SPACE.sub(" ", text).strip().split(" ") if w]
    while words and words[-1] in _DROP:
        words.pop()
    while words and words[0] == "THE":
        words.pop(0)
    joined = " ".join(words)
    # initials: "W R GRACE" and "WR GRACE" are the same name
    return re.sub(r"\b([A-Z]) (?=[A-Z]\b)", r"\1", joined)


# symbol -> name(s) of the company that held the ticker during its pre-2009 membership. Several
# names separated by "|" are alternatives (a rename inside the span), all searched.
HINTS: dict[str, str] = {
    # gap cases: symbols with a 2009+ row whose pre-2009 stint is separate
    "CDNS": "Cadence Design Systems",
    "LVLT": "Level 3 Communications",
    "PETM": "PetSmart",
    "SIRI": "Sirius Satellite Radio|Sirius XM Radio|Sirius XM Holdings",
    "VMED": "Virgin Media|NTL Inc",
    "WBD": "Discovery Holding Co|Discovery Communications",
    "WFMI": "Whole Foods Market",
    "AAL": "Alexander & Alexander Services",
    "BR": "Burlington Resources",
    "CCI": "Citicorp",
    "CE": "Concord EFS",
    "CNC": "Conseco",
    "DG": "Dollar General",
    "FL": "Woolworth|Venator Group|Foot Locker",
    "FMC": "FMC Corp",
    "GGP": "General Growth Properties",
    "HCA": "Columbia/HCA Healthcare|HCA Healthcare|HCA Inc",
    "HLT": "Hilton Hotels",
    "HP": "Helmerich & Payne",
    "KMI": "Kinder Morgan|KN Energy",
    "KSU": "Kansas City Southern Industries|Kansas City Southern",
    "OI": "Owens-Illinois",
    "OKE": "ONEOK",
    "PTC": "Parametric Technology",
    "RIG": "Transocean|Transocean Sedco Forex|Transocean Offshore",
    "TT": "Ingersoll-Rand",
    # no 2009 row at all
    "AAMRQ": "AMR Corp",
    "ABI": "Applera|PE Corp|Perkin-Elmer|Perkin Elmer",
    "ABKFQ": "Ambac Financial Group",
    "ABS": "Albertsons|Albertson's Inc",
    "ABX": "Barrick Gold",
    "ACKH": "Armstrong World Industries|Armstrong Holdings",
    "ACV": "Alberto-Culver",
    "ADCT": "ADC Telecommunications",
    "AEOS": "American Eagle Outfitters",
    "AFS.A": "Associates First Capital",
    "AGC": "American General Corp",
    "AHM": "H.F. Ahmanson|Ahmanson H F",
    "AIT": "Ameritech",
    "AL": "Alcan Aluminium|Alcan Inc",
    "AM": "American Greetings",
    "AMCC": "Applied Micro Circuits",
    "AMH": "Amdahl",
    "AMLN": "Amylin Pharmaceuticals",
    "ANDW": "Andrew Corp",
    "APCC": "American Power Conversion",
    "AR": "ASARCO",
    "ARC": "Atlantic Richfield",
    "AS": "Armco",
    "ASC": "American Stores",
    "ASH": "Ashland Inc|Ashland Oil",
    "ASN": "Archstone-Smith Trust|Archstone Smith Trust",
    "ASND": "Ascend Communications",
    "ASO": "AmSouth Bancorporation",
    "AT": "Alltel",
    "AV": "Avaya",
    "AW": "Allied Waste Industries",
    "AWE": "AT&T Wireless Services",
    "AZA.A": "Alza Corp",
    "BAY": "Bay Networks",
    "BBI": "Barnett Banks",
    "BC": "Brunswick Corp",
    "BEAS": "BEA Systems",
    "BEV": "Beverly Enterprises",
    "BFI": "Browning-Ferris Industries",
    "BFO": "Bestfoods|CPC International",
    "BGEN": "Biogen",
    "BGG": "Briggs & Stratton",
    "BHMSQ": "Bethlehem Steel",
    "BKB": "BankBoston|Bank of Boston",
    "BLS": "BellSouth",
    "BLY": "Bally Entertainment",
    "BMET": "Biomet",
    "BMGCA": "Battle Mountain Gold",
    "BNL": "Beneficial Corp",
    "BOAT": "Boatmen's Bancshares",
    "BOL": "Bausch & Lomb",
    "BRL": "Barr Pharmaceuticals|Barr Laboratories",
    "BSC": "Bear Stearns Companies",
    "BT": "Bankers Trust New York|Bankers Trust Corp",
    "BUD": "Anheuser-Busch Companies",
    "BVSN": "BroadVision",
    "CAR": "CUC International|Cendant|Avis Budget Group",
    "CBB": "Caliber System|Roadway Services",
    "CBH": "Commerce Bancorp",
    "CBSS": "Compass Bancshares",
    "CCB": "Capital Cities/ABC|Capital Cities ABC",
    "CCK": "Crown Cork & Seal",
    "CCTYQ": "Circuit City Stores",
    "CCU": "Clear Channel Communications",
    "CDWC": "CDW Corp|CDW Computer Centers",
    "CEN": "Ceridian",
    "CFC": "Countrywide Financial|Countrywide Credit Industries",
    "CFL": "CoreStates Financial",
    "CG": "Columbia Energy Group|Columbia Gas System",
    "CGP": "Coastal Corp",
    "CHA": "Champion International",
    "CHIR": "Chiron Corp",
    "CIN": "Cinergy",
    "CIT.A": "CIT Group",
    "CKFR": "CheckFree",
    "CMB": "Chase Manhattan Corp",
    "CMVT": "Comverse Technology",
    "CMX": "Caremark Rx|MedPartners",
    "CNG": "Consolidated Natural Gas",
    "CNXT": "Conexant Systems",
    "COC.B": "Conoco Inc",
    "COMS": "3Com",
    "CPNLQ": "Calpine",
    "CPQ": "Compaq Computer",
    "CR": "Crane Co",
    "CRR": "Conrail",
    "CSE": "Case Corp",
    "CSR": "Central & South West",
    "CTB": "Cooper Tire & Rubber",
    "CYM": "Cyprus Amax Minerals",
    "CYR": "Cray Research",
    "DALRQ": "Delta Air Lines",
    "DCNAQ": "Dana Corp",
    "DDS": "Dillard's|Dillard Department Stores",
    "DEC": "Digital Equipment",
    "DGN": "Data General",
    "DI": "Dresser Industries",
    "DIGI": "DSC Communications",
    "DJ": "Dow Jones & Co",
    "DLX": "Deluxe Corp",
    "DPHIQ": "Delphi Corp|Delphi Automotive Systems",
    "DWD": "Dean Witter Discover|Morgan Stanley Dean Witter",
    "EC": "Engelhard",
    "ECH": "Echlin",
    "ECO": "Echo Bay Mines",
    "EDS": "Electronic Data Systems",
    "EFU": "Eastern Enterprises",
    "EHC": "HealthSouth",
    "ENRNQ": "Enron Corp",
    "ENS": "Enserch",
    "EOP": "Equity Office Properties Trust",
    "ERIC": "Ericsson|Telefonaktiebolaget LM Ericsson",
    "FBF": "FleetBoston Financial|Fleet Financial Group|Fleet Boston",
    "FBO": "Federal Paper Board",
    "FCN": "First Chicago NBD",
    "FDC": "First Data",
    "FG": "USF&G",
    "FJ": "Fort James|James River Corp of Virginia",
    "FLMIQ": "Fleming Companies",
    "FLTWQ": "Fleetwood Enterprises",
    "FMCC": "Federal Home Loan Mortgage",
    "FMY": "Fred Meyer",
    "FNMA": "Federal National Mortgage Association",
    "FPC": "Florida Progress",
    "FRO": "Frontier Corp",
    "FSH": "Fisher Scientific International",
    "FSL": "Freescale Semiconductor",
    "FTL.A": "Fruit of the Loom",
    "G": "Gillette",
    "GAPTQ": "Great Atlantic & Pacific Tea",
    "GDT": "Guidant",
    "GDW": "Golden West Financial",
    "GFS.A": "Giant Food",
    "GIDL": "Giddings & Lewis",
    "GLD": "Santa Fe Pacific Gold",
    "GLK": "Great Lakes Chemical",
    "GNT": "Green Tree Financial",
    "GP": "Georgia-Pacific",
    "GPU": "GPU Inc|General Public Utilities",
    "GRA": "W. R. Grace",
    "GRN": "General Re",
    "GSX": "General Signal",
    "GTE": "GTE Corp",
    "GTW": "Gateway Inc|Gateway 2000",
    "GWF": "Great Western Financial",
    "GX": "Global Crossing",
    "HBOC": "HBO & Co",
    "HCR": "Manor Care|HCR Manor Care",
    "HDLM": "Handleman",
    "HET": "Harrah's Entertainment",
    "HFS": "HFS Inc",
    "HI": "Household International",
    "HM": "Homestake Mining",
    "HMA": "Health Management Associates",
    "HPC": "Hercules Inc",
    "HPH": "Harnischfeger Industries",
    "I": "First Interstate Bancorp",
    "IAC": "IAC/InterActiveCorp|IAC InterActiveCorp",
    "IKN": "IKON Office Solutions|Alco Standard",
    "IMNX": "Immunex",
    "INCLF": "Inco Ltd",
    "JH": "John H. Harland|Harland John H",
    "JHF": "John Hancock Financial Services|Hancock John Financial Services",
    "JOS": "Jostens",
    "JP": "Jefferson-Pilot",
    "KATE": "Liz Claiborne",
    "KM": "Kmart",
    "KMG": "Kerr-McGee",
    "KRB": "MBNA",
    "KRI": "Knight Ridder|Knight-Ridder",
    "KSE": "KeySpan",
    "KWP": "King World Productions",
    "LAMR": "Lamar Advertising",
    "LDG": "Longs Drug Stores",
    "LDW.B": "Laidlaw Inc",
    "LEAP": "Leap Wireless International",
    "LEHMQ": "Lehman Brothers Holdings",
    "LLX": "Louisiana Land & Exploration",
    "LOR": "Loral Corp",
    "LPX": "Louisiana-Pacific",
    "LU": "Lucent Technologies",
    "LUB": "Luby's|Lubys Cafeterias",
    "MAY": "May Department Stores",
    "MCIC": "MCI Communications",
    "MD": "McDonnell Douglas",
    "MDR": "McDermott International",
    "MEA": "Mead Corp",
    "MEDI": "MedImmune",
    "MEL": "Mellon Financial|Mellon Bank Corp",
    "MERQ": "Mercury Interactive",
    "MII": "Morton International",
    "MKG": "Mallinckrodt",
    "MNR": "Manor Care",
    "MOB": "Mobil Corp",
    "MST": "Mercantile Stores",
    "MTG": "MGIC Investment",
    "MTL": "Mercantile Bancorporation",
    "MWI": "Moore Corp",
    "MYG": "Maytag",
    "MZIAQ": "Milacron|Cincinnati Milacron",
    "NAV": "Navistar International",
    "NC": "NACCO Industries",
    "NCE": "New Century Energies",
    "NCR": "NCR Corp",
    "NFB": "North Fork Bancorporation",
    "NGH": "Nabisco Group Holdings|RJR Nabisco Holdings",
    "NLC": "Nalco Chemical",
    "NLTI": "NTL Inc|Virgin Media",
    "NMK": "Niagara Mohawk Holdings|Niagara Mohawk Power",
    "NRTLQ": "Nortel Networks|Northern Telecom",
    "NSI": "National Service Industries",
    "NXTL": "Nextel Communications",
    "NYN": "NYNEX",
    "OAT": "Quaker Oats",
    "OK": "Old Kent Financial",
    "OM": "Outboard Marine",
    "OMX": "OfficeMax|Boise Cascade",
    "ONE": "Bank One Corp|Banc One Corp",
    "ORX": "Oryx Energy",
    "OWENQ": "Owens Corning|Owens-Corning Fiberglas",
    "PAC": "Pacific Telesis Group",
    "PALM": "Palm Inc",
    "PBY": "Pep Boys",
    "PCH": "Potlatch",
    "PCS": "Sprint Corp",
    "PD": "Phelps Dodge",
    "PDG": "Placer Dome",
    "PEL": "PanEnergy",
    "PET": "Pacific Enterprises",
    "PGL": "Peoples Energy",
    "PHA": "Pharmacia Corp|Monsanto Co",
    "PHB": "Pioneer Hi-Bred International",
    "PMCS": "PMC-Sierra",
    "PNU": "Pharmacia & Upjohn",
    "PPW": "PacifiCorp",
    "PRD": "Polaroid",
    "PSFT": "PeopleSoft",
    "PTEN": "Patterson-UTI Energy",
    "PVN": "Providian Financial",
    "PVT": "Provident Companies|UnumProvident|Unum Group",
    "PWER": "Power-One",
    "PWJ": "PaineWebber Group|Paine Webber Group",
    "PZE": "Pennzoil|PennzEnergy",
    "QTRN": "Quintiles Transnational",
    "RAD": "Rite Aid",
    "RAL": "Ralston Purina",
    "RATL": "Rational Software",
    "RBD": "Rubbermaid",
    "RBK": "Reebok International",
    "RDS.A": "Royal Dutch Petroleum",
    "RLM": "Reynolds Metals",
    "RML": "Russell Corp",
    "RNB": "Republic New York",
    "RYC": "Raychem",
    "SAF": "Safeco",
    "SAI": "SunAmerica",
    "SANM": "Sanmina|Sanmina-SCI",
    "SAPE": "Sapient",
    "SB": "Salomon Inc",
    "SBL": "Symbol Technologies",
    "SCI": "Service Corp International",
    "SDS": "SunGard Data Systems",
    "SEBL": "Siebel Systems",
    "SEG": "Seagate Technology",
    "SEPR": "Sepracor",
    "SFA": "Scientific-Atlanta",
    "SGID": "Silicon Graphics",
    "SHN": "Shoney's",
    "SK": "Safety-Kleen",
    "SLR": "Solectron",
    "SMI": "Springs Industries",
    "SMS": "Shared Medical Systems",
    "SNT": "Sonat",
    "SNV": "Synovus Financial",
    "SOTR": "SouthTrust",
    "SRR": "Stride Rite",
    "SSP": "E.W. Scripps|Scripps E W",
    "STO": "Stone Container",
    "SUB": "Summit Bancorp|UJB Financial",
    "SXCL": "Adaptec",
    "TA": "Transamerica Corp",
    "TCOMA": "Tele-Communications Inc",
    "TDM": "Tandem Computers",
    "TEK": "Tektronix",
    "TEN": "Tenneco",
    "TEX": "Terex",
    "TIN": "Temple-Inland",
    "TKR": "Timken",
    "TMC": "Times Mirror",
    "TMC.A": "Times Mirror",
    "TNB": "Thomas & Betts",
    "TOS": "Tosco",
    "TOY": "Toys R Us",
    "TRB": "Tribune Co",
    "TRW": "TRW Inc",
    "TSG": "Sabre Holdings|Sabre Group Holdings",
    "TUP": "Tupperware",
    "TX": "Texaco",
    "TXU": "TXU Corp|Texas Utilities",
    "UAUA": "UAL Corp",
    "UAWGQ": "US Airways Group|USAir Group",
    "UCC": "Union Camp",
    "UCL": "Unocal",
    "UCM": "Unicom Corp",
    "UIS": "Unisys",
    "UK": "Union Carbide",
    "UN": "Unilever N.V.|Unilever NV",
    "UPC": "Union Planters",
    "UPR": "Union Pacific Resources Group",
    "USBC": "U.S. Bancorp",
    "USH": "USLIFE",
    "USHC": "U.S. Healthcare|US Healthcare",
    "USS": "United States Surgical",
    "USW": "U S West|US West|MediaOne Group",
    "UVN": "Univision Communications",
    "VAT": "Varity",
    "VO": "Seagram",
    "VRTS": "Veritas Software",
    "VSTNQ": "Visteon",
    "VTSS": "Vitesse Semiconductor",
    "WAI": "Western Atlas",
    "WAMUQ": "Washington Mutual",
    "WCOEQ": "WorldCom|MCI WorldCom|LDDS WorldCom",
    "WEN": "Wendy's International",
    "WLA": "Warner-Lambert",
    "WLL": "Willamette Industries",
    "WLP": "WellPoint Health Networks",
    "WMX": "WMX Technologies",
    "WNDXQ": "Winn-Dixie Stores",
    "WOR": "Worthington Industries",
    "WWY": "Wm. Wrigley Jr.|Wrigley Wm Jr",
    "XMSR": "XM Satellite Radio Holdings",
    "YNR": "Young & Rubicam",
    "YRCW": "Yellow Corp|Yellow Roadway|YRC Worldwide",
}

# symbol -> ((cik, start, end, company_name, note), ...). ``start``/``end`` empty mean the span's
# own start/end. Hand-audited against https://data.sec.gov/submissions/CIK<cik>.json.
MANUAL: dict[str, tuple[tuple[str, str, str, str, str], ...]] = {
    # --- holdco reorgs and mergers that put a younger CIK on a continuing ticker. The carry
    # tier proposed the 2009 filer; EARLY showed it filed nothing near the span's start. Each
    # handover date is the day the successor's shares began trading under the ticker (or the
    # closing date where trading was continuous); predecessor former names are EDGAR's.
    "AEE": (
        ("0000100826", "", "1998-01-02", "UNION ELECTRIC CO",
         "Union Electric until the 1997-12-31 CIPSCO merger formed Ameren; fja05680 back-fills "
         "AEE over the Union Electric slot"),
        ("0001002910", "1998-01-02", "", "AMEREN CORP", "Ameren from its 1998 first trading day"),
    ),
    "AET": (
        ("0000002648", "", "1996-07-19", "AETNA LIFE & CASUALTY CO",
         "EDGAR former name AETNA LIFE & CASUALTY CO (1994..1996-07-16); the U.S. Healthcare "
         "merger closed 1996-07-19 under a new holding company"),
        ("0001013761", "1996-07-19", "2000-12-14", "AETNA INC /CT/",
         "Aetna Inc 1996-2000; sold its financial services arm to ING and spun the health "
         "business 2000-12-13"),
        ("0001122304", "2000-12-14", "", "AETNA INC /PA/",
         "the spun health company (EDGAR former name AETNA U S HEALTHCARE INC)"),
    ),
    "BNY": (
        ("0000009626", "", "2007-07-02", "BANK OF NEW YORK CO INC",
         "Bank of New York Co until the 2007-07-01 Mellon merger formed BNY Mellon"),
        ("0001390777", "2007-07-02", "", "Bank of New York Mellon Corp", "BNY Mellon"),
    ),
    "CBE": (
        ("0000024454", "", "2002-05-22", "COOPER INDUSTRIES INC",
         "Ohio Cooper Industries until the 2002-05-22 Bermuda reincorporation"),
        ("0001141982", "2002-05-22", "", "Cooper Industries plc",
         "Cooper Industries Ltd (Bermuda), later plc"),
    ),
    "CEG": (
        ("0000009466", "", "1999-05-03", "BALTIMORE GAS & ELECTRIC CO",
         "BGE until Constellation Energy Group became its holding company 1999-04-30"),
        ("0001004440", "1999-05-03", "", "CONSTELLATION ENERGY GROUP INC", "Constellation"),
    ),
    "CMCSA": (
        ("0000022301", "", "2002-11-19", "COMCAST CORP",
         "the original Comcast Corp (EDGAR now COMCAST HOLDINGS CORP) until the AT&T Broadband "
         "close 2002-11-18 put a new parent on the ticker"),
        ("0001166691", "2002-11-19", "", "COMCAST CORP", "former name AT&T COMCAST CORP"),
    ),
    "CNP": (
        ("0000202131", "", "1997-08-06", "HOUSTON INDUSTRIES INC /OLD",
         "Houston Industries until the 1997-08-06 NorAm merger moved the parent onto the "
         "utility's CIK"),
        ("0000048732", "1997-08-06", "2002-09-03", "RELIANT ENERGY INC",
         "Houston Industries Inc, renamed Reliant Energy 1999 (EDGAR now CenterPoint Energy "
         "Houston Electric); CenterPoint became the parent 2002-08-31"),
        ("0001130310", "2002-09-03", "", "CENTERPOINT ENERGY INC", "CenterPoint Energy"),
    ),
    "COP": (
        ("0000078214", "", "2002-09-03", "PHILLIPS PETROLEUM CO",
         "fja05680 back-fills COP over Phillips Petroleum; the Conoco merger closed 2002-08-30"),
        ("0001163165", "2002-09-03", "", "CONOCOPHILLIPS", "ConocoPhillips"),
    ),
    "DISCK": (
        ("0001320482", "", "2008-09-18", "Discovery Holding CO",
         "Nasdaq-100 slot back-filled as DISCK; Discovery Holding until Discovery Communications "
         "became the parent 2008-09-17"),
        ("0001437107", "2008-09-18", "", "Discovery Communications, Inc.",
         "EDGAR now Warner Bros. Discovery"),
    ),
    "WBD": (
        ("0001320482", "", "2008-09-18", "Discovery Holding CO",
         "Nasdaq-100 2007-2008 stint back-filled as WBD; Discovery Holding until 2008-09-17"),
        ("0001437107", "2008-09-18", "", "Discovery Communications, Inc.",
         "EDGAR now Warner Bros. Discovery"),
    ),
    "DTV": (
        ("0000944868", "", "", "DIRECTV GROUP INC",
         "The DIRECTV Group (former name HUGHES ELECTRONICS CORP), the filer until the 2009-11-19 "
         "Liberty Entertainment merger; ticker_cik.csv's 0001465112 filed nothing before 2010"),
    ),
    "DUK": (
        ("0000030371", "", "2006-04-03", "DUKE ENERGY CORP",
         "Duke Power, renamed Duke Energy 1997 (EDGAR now Duke Energy Carolinas) until the "
         "2006-04-03 Cinergy merger put a new parent on the ticker"),
        ("0001326160", "2006-04-03", "", "Duke Energy CORP", "former name Duke Energy Holding Corp."),
    ),
    "DXC": (
        ("0000023082", "", "", "COMPUTER SCIENCES CORP",
         "the DXC slot is Computer Sciences Corp before the 2017 merger that created DXC"),
    ),
    "DYN": (
        ("0000879215", "", "2007-04-03", "DYNEGY INC /IL/",
         "Dynegy Inc (Illinois, former NGC Corp) until the 2007-04-02 LS Power combination put "
         "Dynegy Acquisition Inc on the ticker"),
        ("0001379895", "2007-04-03", "", "DYNEGY INC.", "former name Dynegy Acquisition, Inc."),
    ),
    "ED": (
        ("0000023632", "", "1998-01-02", "CONSOLIDATED EDISON CO OF NEW YORK INC",
         "Con Edison of New York until Consolidated Edison Inc became its holding company "
         "1998-01-01"),
        ("0001047862", "1998-01-02", "", "CONSOLIDATED EDISON INC", "Consolidated Edison Inc"),
    ),
    "EP": (
        ("0001066107", "", "", "EL PASO CORP/DE",
         "El Paso Energy Corp, renamed El Paso Corp 2001; ticker_cik.csv's 2009 row names "
         "0000887396 Empire Petroleum, today's holder of the recycled ticker"),
    ),
    "CPWR": (
        ("0000859014", "", "", "COMPUWARE CORP",
         "Compuware; ticker_cik.csv's 2009 row names 0000827099 Ocean Thermal Energy, today's "
         "holder of the recycled ticker"),
    ),
    "EXC": (
        ("0000078100", "", "2000-10-20", "PECO ENERGY CO",
         "PECO Energy until the 2000-10-20 Unicom merger formed Exelon"),
        ("0001109357", "2000-10-20", "", "EXELON CORP", "Exelon"),
    ),
    "FDX": (
        ("0000230211", "", "1998-01-27", "FEDERAL EXPRESS CORP",
         "Federal Express Corp until FDX Corp became its holding company at the 1998-01-27 "
         "Caliber close"),
        ("0001048911", "1998-01-27", "", "FEDEX CORP", "FDX Corp, renamed FedEx 2000"),
    ),
    "FE": (
        ("0000073960", "", "1997-11-10", "OHIO EDISON CO",
         "Ohio Edison until the 1997-11-07 Centerior merger formed FirstEnergy. EDGAR's latest "
         "SIC for this CIK is 6189 (asset-backed), so the sector label for this stretch is the "
         "not-point-in-time artefact sectors.py documents"),
        ("0001031296", "1997-11-10", "", "FIRSTENERGY CORP", "FirstEnergy"),
    ),
    "IR": (
        ("0000050485", "", "2001-12-31", "INGERSOLL RAND CO",
         "New Jersey Ingersoll-Rand until the 2001-12-31 Bermuda reorganisation"),
        ("0001160497", "2001-12-31", "", "INGERSOLL RAND CO LTD", "Ingersoll-Rand Co Ltd"),
    ),
    "JCP": (
        ("0000077182", "", "2002-01-28", "J C PENNEY CORP INC",
         "J. C. Penney Co (EDGAR now J C PENNEY CORP INC) until the 2002-01-28 holding company"),
        ("0001166126", "2002-01-28", "", "J.C. Penney Company, Inc.", "the holding company"),
    ),
    "LMCK": (
        ("0001355096", "", "", "LIBERTY MEDIA CORP",
         "LOW CONFIDENCE: the Nasdaq-100 source carries a Liberty slot back-filled as LMCK from "
         "2007; in 2007-2008 the listed Liberty tracking stocks (LINTA, LCAPA) were all issued "
         "by Liberty Media Corp 0001355096 (EDGAR now Old QVC Group), so the filer is right but "
         "which tracking stock the slot was is not known"),
    ),
    "MCO": (
        ("0000030419", "", "1998-07-01", "DUN & BRADSTREET CORP",
         "the old Dun & Bradstreet (EDGAR now DEX ONE, former R H DONNELLEY); fja05680 "
         "back-fills MCO over the D&B slot; the 1998-07-01 split moved D&B onto a new CIK"),
        ("0001059556", "1998-07-01", "", "MOODYS CORP /DE/",
         "Dun & Bradstreet 1998-2000, renamed Moody's at the 2000 spin"),
    ),
    "MI": (
        ("0000062741", "", "2007-11-01", "MARSHALL & ILSLEY CORP/WI/",
         "Marshall & Ilsley until the 2007-11-01 Metavante separation put New M&I on the ticker"),
        ("0001399315", "2007-11-01", "", "MARSHALL & ILSLEY CORP", "former name NEW M&I CORP"),
    ),
    "MWV": (
        ("0000106498", "", "2002-01-29", "WESTVACO CORP",
         "fja05680 back-fills MWV over Westvaco; the Mead merger closed 2002-01-29"),
        ("0001159297", "2002-01-29", "", "MEADWESTVACO CORP", "MeadWestvaco"),
    ),
    "NBR": (
        ("0000798943", "", "2002-06-24", "NABORS INDUSTRIES INC",
         "Delaware Nabors until the 2002-06-24 Bermuda reorganisation"),
        ("0001163739", "2002-06-24", "", "NABORS INDUSTRIES LTD", "Nabors Industries Ltd"),
    ),
    "NE": (
        ("0000777201", "", "2002-05-01", "NOBLE DRILLING CORP",
         "Noble Drilling until the 2002-04-30 Cayman reorganisation"),
        ("0001169055", "2002-05-01", "", "NOBLE CORP",
         "Noble Corp (Cayman; EDGAR now Noble Finance Co), the parent until the 2009-03-27 Swiss "
         "move"),
    ),
    "NEM": (
        ("0000071824", "", "2002-02-16", "NEWMONT MINING CORP",
         "Newmont Mining (EDGAR now NEWMONT USA LTD) until the 2002-02-15 Normandy/Franco-Nevada "
         "holding company"),
        ("0001164727", "2002-02-16", "", "NEWMONT MINING CORP /DE/", "former name DELTA HOLDCO"),
    ),
    "NOC": (
        ("0000072945", "", "2001-04-03", "NORTHROP GRUMMAN CORP",
         "the original Northrop Grumman until the 2001-04-03 Litton holding company"),
        ("0001133421", "2001-04-03", "", "NORTHROP GRUMMAN CORP /DE/", "former name NNG INC"),
    ),
    "ORCL": (
        ("0000777676", "", "2006-02-01", "ORACLE CORP /DE/",
         "the original Oracle until the 2006-01-31 Siebel close put Ozark Holding on the ticker"),
        ("0001341439", "2006-02-01", "", "ORACLE CORP", "former name Ozark Holding Inc."),
    ),
    "PGN": (
        ("0000017797", "", "2000-06-19", "CAROLINA POWER & LIGHT CO",
         "fja05680 back-fills PGN over Carolina Power & Light; CP&L Energy became the holding "
         "company 2000-06-19"),
        ("0001094093", "2000-06-19", "", "PROGRESS ENERGY INC", "CP&L Energy, renamed 2000-12"),
    ),
    "PSA": (
        ("0000318380", "", "2007-06-01", "PUBLIC STORAGE INC /CA",
         "Public Storage Inc until the 2007-06-01 Maryland REIT reorganisation"),
        ("0001393311", "2007-06-01", "", "Public Storage", "Public Storage (Maryland)"),
    ),
    "PSKY": (
        ("0000813828", "", "", "VIACOM INC",
         "LOW CONFIDENCE on the company, not the sector: fja05680 back-fills one CBS slot from "
         "1996. Viacom Inc (renamed CBS Corp 2006, now Paramount Global) is the filer whose "
         "ticker became PSKY; for 1996-2000 the slot may instead be Westinghouse/CBS Corp "
         "(0000106413), which the universe otherwise lacks. Both are television broadcasters "
         "(SIC 4833), so the sector label is the same either way"),
    ),
    "RAI": (
        ("0000083612", "", "2004-07-30", "RJ REYNOLDS TOBACCO HOLDINGS INC",
         "R.J. Reynolds Tobacco Holdings until the 2004-07-30 Brown & Williamson combination "
         "formed Reynolds American"),
        ("0001275283", "2004-07-30", "", "Reynolds American Inc", "Reynolds American"),
    ),
    "RF": (
        ("0000036032", "", "2004-07-01", "REGIONS FINANCIAL CORP",
         "the original Regions until the 2004-07-01 Union Planters merger"),
        ("0001281761", "2004-07-01", "", "REGIONS FINANCIAL CORP", "former New Regions"),
    ),
    "RTN": (
        ("0000082267", "", "1997-12-18", "RAYTHEON CO",
         "the original Raytheon until the 1997-12-17 Hughes defense merger"),
        ("0001047122", "1997-12-18", "", "RAYTHEON CO/", "former name HE HOLDINGS INC"),
    ),
    "RX": (
        ("0001019876", "", "1998-07-01", "COGNIZANT CORP",
         "Cognizant Corp (EDGAR now NIELSEN MEDIA RESEARCH) until it spun IMS Health 1998-07-01"),
        ("0001058083", "1998-07-01", "", "IMS HEALTH INC", "IMS Health"),
    ),
    "TROW": (
        ("0000080255", "", "2000-12-29", "PRICE T ROWE ASSOCIATES INC /MD/",
         "T. Rowe Price Associates until T. Rowe Price Group became the parent 2000-12-28"),
        ("0001113169", "2000-12-29", "", "PRICE T ROWE GROUP INC", "T. Rowe Price Group"),
    ),
    "TWX": (
        ("0000736157", "", "1996-10-10", "TIME WARNER INC",
         "the 1990 Time Warner (EDGAR now TIME WARNER COMPANIES INC) until the 1996-10-10 TBS "
         "merger holding company"),
        ("0001021387", "1996-10-10", "2001-01-12", "TIME WARNER INC/",
         "Time Warner 1996-2001 (EDGAR now HISTORIC TW INC)"),
        ("0001105705", "2001-01-12", "", "AOL TIME WARNER INC",
         "AOL Time Warner, renamed Time Warner 2003"),
    ),
    "VMC": (
        ("0000103973", "", "2007-11-16", "VULCAN MATERIALS CO",
         "the original Vulcan (EDGAR now Legacy Vulcan Corp) until the 2007-11-16 Florida Rock "
         "holding company"),
        ("0001396009", "2007-11-16", "", "Vulcan Materials CO", "former Virginia Holdco"),
    ),
    "VTRS": (
        ("0000069499", "", "", "MYLAN INC.",
         "the VTRS slot is Mylan Laboratories / Mylan Inc before the 2020 Viatris combination"),
    ),
    "X": (
        ("0000101778", "", "2002-01-02", "USX CORP",
         "USX-U.S. Steel Group, a tracking stock of USX Corp, until United States Steel was "
         "separated 2001-12-31. USX is now Marathon Oil and EDGAR's latest SIC for it is 1311, "
         "so the sector label for this stretch is the not-point-in-time artefact sectors.py "
         "documents (steel labelled as energy)"),
        ("0001163302", "2002-01-02", "", "UNITED STATES STEEL CORP", "United States Steel"),
    ),
    # --- the same symbol, two companies before 2009 -----------------------------------------
    "AMP": (
        ("0000006164", "1996-01-02", "1999-04-05", "AMP INC",
         "AMP Inc (connectors), acquired by Tyco 1999; the ticker went to Ameriprise in 2005"),
    ),
    "AN": (
        ("0000093397", "1996-01-02", "1999-01-04", "AMOCO CORP",
         "Amoco (EDGAR now BP CORP NORTH AMERICA), merged with BP 1998-12-31; the ticker went "
         "to AutoNation"),
    ),
    "CF": (
        ("0000819692", "2000-06-19", "2004-09-01", "CHARTER ONE FINANCIAL INC",
         "Charter One Financial, acquired by Citizens 2004-08-31; the ticker went to CF "
         "Industries"),
    ),
    "COV": (
        ("NONE", "1996-01-02", "1996-08-16", "",
         "unidentified: a 1996 S&P 500 member under COV in fja05680, eleven years before "
         "Covidien; no name source checked (Massive, EODHD, Wikipedia) knows it"),
    ),
    "FWLT": (
        ("0000038321", "1996-01-02", "2000-01-31", "FOSTER WHEELER CORP",
         "the original Foster Wheeler Corp; its 2001 Bermuda successor rejoined the indexes in "
         "2007"),
    ),
    "LHX": (
        ("0000202058", "1996-01-02", "1999-11-08", "HARRIS CORP /DE/",
         "Harris Corp's first stint, the same filer as the 2009 row"),
    ),
    "MEE": (
        ("0000037748", "1996-01-02", "2000-12-22", "FLUOR CORP/DE/",
         "the original Fluor Corp, which kept its CIK and became Massey Energy in the 2000-11-30 "
         "reverse spin; EDGAR's latest SIC (coal mining) therefore labels Fluor's engineering "
         "years as energy, the not-point-in-time artefact sectors.py documents"),
    ),
    "MXIM": (
        ("0000743316", "2000-05-10", "2007-09-27", "MAXIM INTEGRATED PRODUCTS INC",
         "Maxim's first stint, the same filer as the 2009 row"),
    ),
    "ROST": (
        ("0000745732", "2007-02-01", "2007-12-24", "ROSS STORES INC",
         "Ross Stores' first Nasdaq-100 stint, the same filer as the 2009 row"),
    ),
    "H": (
        ("0000040493", "1996-01-02", "2001-06-29", "HARCOURT GENERAL INC",
         "Harcourt General, acquired by Reed Elsevier 2001; 31 periodic filings 1994-2001"),
        ("0001355001", "2006-08-01", "2007-04-10", "REALOGY CORP",
         "Realogy, spun from Cendant 2006-07-31 under H and taken private by Apollo 2007-04-10 "
         "(EDGAR now Anywhere Real Estate Group LLC); H is Hyatt today"),
    ),
    "MIR": (
        ("0000042246", "1997-08-07", "2000-06-01", "MIRAGE RESORTS INC",
         "Mirage Resorts, acquired by MGM Grand 2000-05-31"),
        ("0001010775", "2001-04-03", "2003-07-17", "MIRANT CORP",
         "Mirant, spun from Southern 2001-04-02"),
    ),
    # --- tenures split by a merger or holdco change inside a dead symbol ---------------------
    "ASH": (
        ("0000007694", "", "2005-06-30", "ASHLAND INC",
         "the original Ashland until the 2005-06-30 MAP transaction put a new Ashland Inc on "
         "the ticker"),
        ("0001305014", "2005-06-30", "", "ASHLAND INC.", "former name New EXM Inc."),
    ),
    "GRA": (
        ("0000042872", "", "1996-09-30", "GRACE W R & CO /NY/",
         "the New York W.R. Grace until the 1996-09-30 National Medical Care spin (EDGAR now "
         "Fresenius Medical Care Holdings, whose latest SIC 3841 labels Grace's chemical years "
         "as health care, the artefact sectors.py documents)"),
        ("0001012100", "1996-09-30", "1998-03-31", "WR GRACE & CO/DE",
         "Grace's 1996 holding company, renamed Sealed Air at the 1998-03-31 Cryovac merger"),
        ("0001045309", "1998-03-31", "", "W R GRACE & CO",
         "the specialty-chemicals Grace spun at the Cryovac merger"),
    ),
    "KMG": (
        ("0000055458", "", "2001-08-01", "KERR MCGEE CORP",
         "the original Kerr-McGee until the 2001-08-01 HS Resources holding company"),
        ("0001141185", "2001-08-01", "", "KERR MCGEE CORP /DE", "former Kerr McGee Holdco"),
    ),
    "MII": (
        ("0000068361", "", "1997-05-01", "MORTON INTERNATIONAL INC",
         "the original Morton until its airbag business merged into Autoliv 1997-05-01"),
        ("0001035972", "1997-05-01", "", "MORTON INTERNATIONAL INC /IN/",
         "the specialty-chemicals Morton spun at the Autoliv merger, acquired by Rohm and Haas "
         "1999-06"),
    ),
    "OKE": (
        ("0000074154", "", "1997-11-26", "ONEOK INC",
         "the original ONEOK until the 1997-11-26 Western Resources gas-asset combination"),
        ("0001039684", "1997-11-26", "", "ONEOK INC /NEW/", "former name WAI INC"),
    ),
    "ONE": (
        ("0000036090", "", "1998-10-02", "BANC ONE CORP /OH/",
         "Banc One until the 1998-10-02 First Chicago NBD merger formed Bank One"),
        ("0001067092", "1998-10-02", "", "BANK ONE CORP", "Bank One Corp"),
    ),
    "PVN": (
        ("0000017206", "", "1997-06-11", "PROVIDIAN CORP",
         "Providian Corp (insurance) until it spun Providian Financial and sold the rest to "
         "AEGON, 1997-06"),
        ("0001035713", "1997-06-11", "", "PROVIDIAN FINANCIAL CORP", "Providian Financial"),
    ),
    "TEN": (
        ("0000823549", "", "1996-12-12", "TENNECO INC /DE/",
         "the original Tenneco until its energy business merged into El Paso 1996-12-12 (EDGAR "
         "now El Paso Tennessee Pipeline)"),
        ("0001024725", "1996-12-12", "", "TENNECO INC /DE",
         "New Tenneco, which spun Pactiv and became Tenneco Automotive 1999-11"),
    ),
    "TXU": (
        ("0000097561", "", "1997-08-05", "TEXAS UTILITIES CO",
         "the original Texas Utilities until the 1997-08-05 ENSERCH holding company"),
        ("0001023291", "1997-08-05", "", "TEXAS UTILITIES CO /TX/",
         "renamed TXU 2000 (EDGAR now Energy Future Holdings)"),
    ),
    "USW": (
        ("0000732718", "", "1998-06-15", "US WEST INC",
         "U S West Inc (communications group stock) until the 1998-06-12 split of the "
         "communications and media groups"),
        ("0001054522", "1998-06-15", "", "U S WEST INC /DE/",
         "the new U S West, acquired by Qwest 2000-06-30"),
    ),
    # --- names the automated tier could not settle ------------------------------------------
    "UMG": (
        ("0000732718", "", "", "MEDIAONE GROUP INC",
         "U S West Media Group, a tracking stock of U S West Inc trading as UMG, which became "
         "MediaOne Group in the 1998 split and was acquired by AT&T 2000-06-15 (EDGAR now Comcast "
         "MO Group)"),
    ),
    "TT": (
        ("0000836102", "", "", "AMERICAN STANDARD COMPANIES INC",
         "fja05680 back-fills TT over American Standard, renamed Trane Inc 2007-11 and acquired by "
         "Ingersoll-Rand 2008-06-05"),
    ),
    "CMB": (
        ("0000019489", "", "", "CHASE MANHATTAN CORP",
         "the original Chase Manhattan, merged into Chemical Banking (which took the Chase name "
         "and is JPMorgan Chase today) 1996-03-31"),
    ),
    "BGEN": (
        ("0000714655", "", "", "BIOGEN INC",
         "the original Biogen (EDGAR now BIOGEN IDEC MA INC); 0000875045, today's Biogen Inc, "
         "was IDEC Pharmaceuticals until the 2003-11-12 merger"),
    ),
    "KATE": (
        ("0000352363", "", "", "CLAIBORNE LIZ INC",
         "Liz Claiborne (renamed Fifth & Pacific, then Kate Spade & Co); 0001170403, the other "
         "same-name entity, is a different filer"),
    ),
    "NGH": (
        ("0000847903", "", "", "NABISCO GROUP HOLDINGS CORP",
         "RJR Nabisco Holdings, renamed Nabisco Group Holdings 1999-06; 0000083612 is the "
         "tobacco company spun off then"),
    ),
    "NRTLQ": (
        ("0000072911", "", "", "NORTEL NETWORKS CORP",
         "Northern Telecom, renamed Nortel Networks; a Canadian filer whose periodic reports "
         "reach EDGAR only from 2000-11 (0001119664 is its operating subsidiary)"),
    ),
    "TCOMA": (
        ("0000925692", "", "", "TELE COMMUNICATIONS INC /CO/",
         "the 1994 TCI holding company, acquired by AT&T 1999-03-09 (EDGAR now Comcast Cable "
         "Holdings); 0000096903 is its TCI Communications subsidiary"),
    ),
    "UN": (
        ("0000110390", "", "", "UNILEVER N V",
         "Unilever N.V., a foreign private issuer filing 20-F; 0000217410 is Unilever PLC"),
    ),
    "USBC": (
        ("0000101542", "", "", "US BANCORP /OR/",
         "the Portland U.S. Bancorp, acquired 1997 by First Bank System, which took its name "
         "(0000036104 is that acquirer, today's U.S. Bancorp)"),
    ),
    "XMSR": (
        ("0001091530", "", "", "XM SATELLITE RADIO HOLDINGS INC",
         "the listed holding company; 0001116317 is its operating subsidiary"),
    ),
    "LAMR": (
        ("0001090425", "", "", "LAMAR ADVERTISING CO/NEW",
         "the listed company; 0000899045 Lamar Media is its subsidiary"),
    ),
    "CDWC": (
        ("0000899171", "", "", "CDW CORP",
         "CDW Corp (former CDW Computer Centers), taken private 2007-10"),
    ),
    "PBY": (
        ("0000077449", "", "", "PEP BOYS MANNY MOE & JACK", "the full EDGAR name"),
    ),
    "LDW.B": (
        ("0000737874", "", "", "LAIDLAW INC",
         "Laidlaw Inc (EDGAR now LAIDLAW INTERNATIONAL), a Canadian filer with no periodic "
         "reports on EDGAR before 2002"),
    ),
    "MWI": (
        ("0000067931", "", "", "MOORE CORPORATION LTD",
         "Moore Corp Ltd, renamed Moore Wallace 2003; a Canadian filer with no periodic reports "
         "on EDGAR inside the span (filings from 1996-08, periodic from 1999-10)"),
    ),
    "ERIC": (
        ("0000717826", "", "", "ERICSSON LM TELEPHONE CO", "Ericsson, a 20-F filer"),
    ),
    "I": (
        ("0000105982", "", "", "FIRST INTERSTATE BANCORP /DE/",
         "First Interstate, acquired by Wells Fargo 1996-04-01 (EDGAR now WELLS FARGO BANK & CO)"),
    ),
    "ANV": (
        ("0000059198", "", "", "AEROQUIP-VICKERS INC",
         "Aeroquip-Vickers (former TRINOVA), NYSE ANV, acquired by Eaton 1999-04-09; identified "
         "from the ticker and the removal date"),
    ),
    "ETS": (
        ("0000846909", "", "", "CABLETRON SYSTEMS INC",
         "Cabletron Systems, which became Enterasys Networks (NYSE ETS) at its 2001-08-06 "
         "reorganisation; fja05680 back-fills the later ticker"),
    ),
    "NAE": (
        ("0000007314", "", "", "NORAM ENERGY CORP",
         "NorAm Energy (former Arkla), NYSE NAE, acquired by Houston Industries 1997-08-06"),
    ),
    "RYI": (
        ("0000790528", "", "", "INLAND STEEL INDUSTRIES INC /DE/",
         "Inland Steel Industries, renamed Ryerson Tull 1999 and Ryerson Inc (NYSE RYI) later; "
         "fja05680 back-fills the later ticker; its removal fits the 1998-07 sale of Inland Steel "
         "Co to Ispat"),
    ),
    "PMI": (
        ("0000800575", "", "", "PREMARK INTERNATIONAL INC",
         "LOW CONFIDENCE: Premark (NYSE PMI) kept filing until 1999, but the slot ends the day "
         "its Tupperware spin-off (TUP) joins, consistent with S&P swapping one for the other"),
    ),
    "PAS": (
        ("0000049573", "", "", "WHITMAN CORP",
         "LOW CONFIDENCE: Whitman Corp became PepsiAmericas (NYSE PAS), so a back-filled PAS fits "
         "it; nothing independent confirms Whitman left the index 1998-01-30"),
    ),
    "CHRS": (
        ("0000019353", "", "", "CHARMING SHOPPES INC",
         "LOW CONFIDENCE: Nasdaq CHRS was Charming Shoppes; no source confirms its S&P 500 "
         "membership or the 1998-04-08 removal"),
    ),
    "INGR": (
        ("0000351145", "", "", "INTERGRAPH CORP",
         "LOW CONFIDENCE: Nasdaq INGR was Intergraph; no source confirms its S&P 500 membership "
         "or the 1997-07-28 removal"),
    ),
    "CNW": (
        ("0000854884", "", "", "CHICAGO & NORTH WESTERN TRANSPORTATION CO /DE/",
         "LOW CONFIDENCE: NYSE CNW was the Chicago & North Western, whose last periodic report is "
         "1995-05 (Union Pacific completed its purchase in 1995); the slot runs to 1996-12-03, "
         "which fits only if the source carried it late"),
    ),
    # --- no filer could be identified ----------------------------------------------------------
    "BCO": (("NONE", "", "", "",
             "unidentified: a 20-day 1996 member under BCO in fja05680 (not Brink's, which took "
             "BCO in 2003); no name source checked knows it"),),
    "CAL": (("NONE", "", "", "",
             "unidentified: a 1996 member under CAL in fja05680; Continental Airlines, the "
             "obvious holder, was not an S&P 500 member then"),),
    "NLV": (("NONE", "", "", "",
             "unidentified: an S&P 500 member 1996-04-01 .. 2000-01-06 under NLV in fja05680; no "
             "name source checked knows the ticker"),),
    "RYAN": (("NONE", "", "", "",
              "unidentified: a 1996 member under RYAN in fja05680; no name source checked knows "
              "it"),),
    "SFS": (("NONE", "", "", "",
             "unidentified: a 1996-1997 member under SFS in fja05680; Massive and EODHD answer "
             "Smart & Final, which was never large enough for the index"),),
    "THY": (("NONE", "", "", "",
             "unidentified: a 1996 member under THY in fja05680; no name source checked knows "
             "it"),),
    "NDOI": (("NONE", "", "", "",
              "phantom in the Wikipedia-derived ndx_history.csv; see the NDOI row of "
              "ticker_cik.csv"),),
}

# symbol -> reason a screen may stay silent for it. Add; never remove, never weaken.
SCREEN_EXEMPT: dict[str, str] = {
    # Foreign private issuers were not required to file on EDGAR until May 2002, so a Canadian
    # or European member's periodic reports start then, years after its span opens.
    "ABX": "Barrick Gold (EDGAR BARRICK MINING CORP), a Canadian 40-F filer; periodic from 2002",
    "AL": "Alcan, a Canadian filer; first electronic 10-K 1997-03-28, 15 months into the span",
    "INCLF": "Inco, a Canadian filer; periodic reports on EDGAR from 2001-10",
    "PDG": "Placer Dome, a Canadian 40-F filer; periodic reports on EDGAR from 2002",
    "RDS.A": "Royal Dutch Petroleum, a Dutch 20-F filer; periodic reports on EDGAR from 2002",
    "NRTLQ": "Nortel Networks, a Canadian filer; periodic reports on EDGAR from 2000-11",
    "LDW.B": "Laidlaw Inc, a Canadian filer; periodic reports on EDGAR from 2002",
    "MWI": "Moore Corp, a Canadian filer; periodic reports on EDGAR from 1999-10",
    "ERIC": "Ericsson, a Swedish 20-F filer",
    "UN": "Unilever N.V., a Dutch 20-F filer",
    # US registrants whose silence is documented.
    "FMCC": "Freddie Mac was exempt from SEC registration until it registered voluntarily in "
            "2008-07; its first 10-Q is 2008-08-06",
    "FNMA": "Fannie Mae registered with the SEC only in 2003-03; its first 10-K is 2003-03-31",
    "NAV": "Navistar filed no 10-K or 10-Q from 2005-08 to 2007-12 while it restated its "
           "accounts, which is why the index dropped it 2006-12-20",
    "CNW": "see the LOW CONFIDENCE note: the filer stopped reporting in 1995",
    "MXIM": "Maxim filed no 10-K or 10-Q from 2006-09 to 2008-09 while it restated for option "
            "backdating; Nasdaq delisted it 2007-10, which is why the index dropped it 2007-09-27",
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def stints_before(intervals: Iterable[membership.Interval]) -> dict[str, list[tuple[date, date]]]:
    """``symbol -> [(start, end), ...]``: its membership before CUTOFF, ends clipped to it.

    Overlapping or touching intervals (the same name in both indexes) merge; a real gap does
    not. Unlike ``build_ticker_cik.spans`` this keeps the stints apart, because before 2009 a
    gap is usually a different company: AMP was AMP Inc until 1999 and Ameriprise from 2005,
    AN was Amoco and then AutoNation, H was Harcourt General and then Realogy.
    """
    raw: dict[str, list[tuple[date, date]]] = {}
    for iv in intervals:
        if iv.start_date >= CUTOFF:
            continue
        end = CUTOFF if iv.end_date is None or iv.end_date > CUTOFF else iv.end_date
        raw.setdefault(iv.symbol, []).append((iv.start_date, end))
    out: dict[str, list[tuple[date, date]]] = {}
    for symbol, spans in raw.items():
        merged: list[list[date]] = []
        for start, end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        out[symbol] = [(a, b) for a, b in merged]
    return out


def submissions(fetcher, cik10: str) -> dict:
    return fetcher.json(SUBMISSIONS_URL.format(cik=cik10), f"submissions-{cik10}.json")


def edgar_name(fetcher, cik10: str) -> str:
    return str(submissions(fetcher, cik10).get("name") or "").strip()


def count_in(fetcher, cik10: str, start: date, end: date) -> int:
    return base.filed_inside(fetcher, cik10, start, end)


def evidence(fetcher, cik10: str, start: date, end: date) -> str:
    lo, hi = start.isoformat(), end.isoformat()
    dates = [d for d in base.periodic_dates(fetcher, cik10) if lo <= d < hi]
    if not dates:
        return "0 periodic filings inside the span"
    return f"{len(dates)} periodic filings inside the span ({dates[0]} .. {dates[-1]})"


WINDOW = timedelta(days=EARLY_WINDOW_DAYS)
#: A span at least this long must contain a 10-Q or 10-K deadline (45 days after a quarter).
INSIDE_MIN_DAYS = 135


def build(args: argparse.Namespace) -> int:
    cache = Path(args.cache).resolve()
    contact = args.contact or os.environ.get("SEC_CONTACT_EMAIL") or ""
    fetcher = base.SecFetcher(contact, cache)

    intervals = membership.compute_universe(membership.DATA_DIR)
    stints = stints_before(intervals)
    index = cik.load_index(cik.DATA_DIR)
    symbols = sorted(stints)
    log(f"members before {CUTOFF}: {len(symbols)} ({sum(s not in index for s in symbols)} "
        f"with no row in ticker_cik.csv)")
    unknown = sorted(set(MANUAL) - set(symbols))
    if unknown:
        raise base.BuildError(f"MANUAL names symbols with no pre-{CUTOFF} membership: {unknown}")

    rows: list[dict[str, str]] = []
    unresolved: list[str] = []
    lookup: dict[str, list[str]] | None = None

    for symbol in symbols:
        spans = stints[symbol]
        first_start, last_end = spans[0][0], spans[-1][1]
        manual = []
        for pos, (c, s, e, name, note) in enumerate(MANUAL.get(symbol, ())):
            if not s and pos:
                raise base.BuildError(f"MANUAL {symbol}: only the first row may leave start empty")
            start, end = date.fromisoformat(s) if s else first_start, (
                date.fromisoformat(e) if e else last_end)
            manual.append((start, end))
            rows.append(_row(symbol, c, start.isoformat(), end.isoformat(), name, "manual", note))
        for start, end in spans:
            if any(m_start < end and start < m_end for m_start, m_end in manual):
                continue  # MANUAL answers for this stint
            first = index[symbol][0] if symbol in index else None
            if (first is not None and first.cik and first.start_date == CUTOFF
                    and end == CUTOFF):
                note = (f"carried back from the 2009 row ({first.source}); "
                        f"{evidence(fetcher, first.cik, start, end)}")
                rows.append(_row(symbol, first.cik, start.isoformat(), end.isoformat(),
                                 first.company_name, "carry", note))
                continue
            hint = HINTS.get(symbol)
            if not hint:
                unresolved.append(f"{symbol:7s} {start} .. {end}  (no HINT)")
                continue
            if lookup is None:
                lookup = _lookup(fetcher)
            cands: list[str] = []
            for alt in hint.split("|"):
                for c in lookup.get(canon(alt), []):
                    if c not in cands:
                        cands.append(c)
            if not cands:
                unresolved.append(f"{symbol:7s} {start} .. {end}  hint {hint!r}: no EDGAR entity")
                continue
            # scored over the span plus the window before it: a member of early 1996 often
            # filed its last electronic 10-K in 1995
            scored = sorted(
                ((count_in(fetcher, c, start - WINDOW, end), c) for c in cands[:MAX_CANDIDATES]),
                reverse=True,
            )
            best_n, best = scored[0]
            if best_n == 0 or (len(scored) > 1 and scored[1][0] == best_n):
                unresolved.append(
                    f"{symbol:7s} {start} .. {end}  hint {hint!r}: "
                    + ", ".join(f"{c} {edgar_name(fetcher, c)!r}={n}" for n, c in scored[:6])
                )
                continue
            name = edgar_name(fetcher, best)
            note = (f"name {hint.split('|')[0]!r} -> EDGAR {name!r}; "
                    f"{evidence(fetcher, best, start, end)}"
                    + (f"; best of {len(scored)} same-name entities" if len(scored) > 1 else ""))
            rows.append(_row(symbol, best, start.isoformat(), end.isoformat(), name, "exact", note))

    flagged: list[str] = []
    for row in rows:
        sym, c = row["symbol"], row["cik"]
        if c == cik.NO_FILER or sym in SCREEN_EXEMPT:
            continue
        s, e = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
        problems = []
        if (e - s).days >= INSIDE_MIN_DAYS and count_in(fetcher, c, s, e) == 0:
            problems.append("INSIDE")
        if count_in(fetcher, c, s - WINDOW, s + WINDOW) == 0:
            problems.append("EARLY")
        if e != CUTOFF and count_in(fetcher, c, e - WINDOW, e) == 0:
            problems.append("LATE")
        if problems:
            dates = base.periodic_dates(fetcher, c)
            flagged.append(
                f"{'+'.join(problems):12s} {sym:7s} {s} .. {e} -> {c} {row['company_name']!r} "
                f"[{row['source']}] periodic {dates[0] if dates else 'never'} .. "
                f"{dates[-1] if dates else 'never'}"
            )

    if args.review:
        Path(args.review).write_text(
            "".join(f"{r['symbol']}\t{r['start_date']}\t{r['end_date']}\t{r['cik']}\t"
                    f"{r['company_name']}\t{r['source']}\t{r['note']}\n" for r in rows),
            encoding="utf-8",
        )
    if unresolved:
        log(f"\nUNRESOLVED ({len(unresolved)}) -- add a HINT or a MANUAL entry:")
        for line in unresolved:
            log("  " + line)
    if flagged:
        log(f"\nSCREENS ({len(flagged)}) -- resolve in MANUAL, or exempt with the reason:")
        for line in flagged:
            log("  " + line)
    if unresolved or flagged:
        return 1

    rows.sort(key=lambda r: (r["symbol"], r["start_date"]))
    out = Path(args.out)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(cik.HEADER), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    cik.load_ticker_cik(out, none_alone=False)  # the loader is the final word on the format
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    low = sum("LOW CONFIDENCE" in r["note"] for r in rows)
    none = sum(r["cik"] == cik.NO_FILER for r in rows)
    log(f"\nwrote {out}: {len(rows)} rows, {len({r['symbol'] for r in rows})} symbols; "
        + " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        + f"; NONE={none}; low-confidence={low}")
    return 0


def _lookup(fetcher) -> dict[str, list[str]]:
    text = fetcher.text(base.CIK_LOOKUP_URL, "cik-lookup-data.txt", encoding="latin-1")
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        parts = line.rstrip(":").rsplit(":", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            continue
        key = canon(parts[0])
        if key:
            bucket = out.setdefault(key, [])
            c = parts[1].zfill(10)
            if c not in bucket:
                bucket.append(c)
    log(f"cik-lookup-data.txt: {len(out)} normalised names")
    return out


def _row(symbol: str, c: str, start: str, end: str, name: str, source: str, note: str) -> dict[str, str]:
    return {"symbol": symbol, "cik": c, "start_date": start, "end_date": end,
            "company_name": name, "source": source, "note": note}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="engine/data/ticker_cik_pre2009.csv")
    parser.add_argument("--cache", default="engine/.cache/cik")
    parser.add_argument("--contact", default=None, help="defaults to $SEC_CONTACT_EMAIL")
    parser.add_argument("--review", default=None, help="also write every row as TSV here")
    config.load_env()
    try:
        return build(parser.parse_args(argv))
    except (base.BuildError, config.ConfigError) as exc:
        log(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
