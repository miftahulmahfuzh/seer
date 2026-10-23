"""Find reconstructed price series that make moves no real share makes (M0317).

M0309 showed the survivorship-check store can manufacture an edge: its thin-stock book earned a
large gain on `.research-sv` that was not there on the dev store, and the edge died at the first
notch of a liveness filter. One of the symbols responsible, CBE, prints a single-day 49x on
2004-02-10 that is a split-reconstruction failure, not a market event -- its price ranged
$0.10-$0.75 (median $0.35) for over two years before the jump and sat at $27-29 for months after,
a sustained level discontinuity no corporate action in `splits.csv` explains.

This script looks for the same signature across every symbol the survivorship-check store adds
that the dev store does not carry (`.research-sv` minus `.research`, 450 symbols as of
2026-10-23): a single-day close-to-close move of 3x or worse (or its inverse) with no split
recorded in `splits.csv` within 10 days.

Read-only. Loads two research stores (plain CSV reads, not `research.load_store`, since the
point is to look *underneath* the manifest's hash guarantee for rows that are wrong but
internally consistent) and writes nothing. It does not journal, record a trial, or move the
lab's N.

    engine/.venv/bin/python engine/scripts/implausible_reconstruction.py

**A ticker ending in Q is not flagged.** US markets append a trailing Q to a Nasdaq ticker once
the company has filed Chapter 11; ENRNQ (Enron), WAMUQ (Washington Mutual), LEHMQ (Lehman
Brothers) and DPHIQ (Delphi) all carry a flagged move that is their real, final collapse, not a
reconstruction error. Flagging them as data-quality problems would delete the very events a
survivorship-free store exists to keep.

**The remaining flagged symbols still need a human judgement call**, which this script does not
make: a move with a near-exact split ratio (2x, 3x, 10x, ...) and a sustained new level is the
strongest reconstruction-failure signature (CBE, RAD); a flagged symbol with no absolute-price
corroboration and a plausible real catalyst (a biotech trial failure, a large spinoff) is reported
but is not evidence of bad data on its own. See the M0317 analysis
(`lab show M0317`) for which of the symbols below were excluded from the re-run and why.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

from seer_engine import config, research

DEV_STORE = config.REPO_ROOT / "engine" / ".research"
SV_STORE = config.REPO_ROOT / "engine" / ".research-sv"

#: >=3x or <=1/3 in one day. No liquid-enough-to-trade equity does this without a corporate
#: action; a lower bar (M0309's own ad hoc 2x check) catches real volatile micro-caps too.
RATIO_BAR = 3.0

#: a split within this many days of the flagged move is treated as a candidate explanation
#: (the detector still reports the row; it does not silently clear it).
SPLIT_WINDOW_DAYS = 10


def added_symbols(dev_store: Path = DEV_STORE, sv_store: Path = SV_STORE) -> set[str]:
    """Symbols the survivorship-check store serves that the dev store does not."""
    dev = set(pd.read_csv(dev_store / "bars.csv", usecols=["symbol"])["symbol"].unique())
    sv = set(pd.read_csv(sv_store / "bars.csv", usecols=["symbol"])["symbol"].unique())
    return sv - dev


def flag_implausible_moves(
    sv_store: Path = SV_STORE, symbols: set[str] | None = None, ratio_bar: float = RATIO_BAR
) -> pd.DataFrame:
    """One row per flagged single-day move: symbol, date, the move, whether a nearby split
    explains it, and whether the ticker's own Q suffix already says it is a real bankruptcy.
    """
    if symbols is None:
        symbols = added_symbols(sv_store=sv_store)
    bars = pd.read_csv(sv_store / "bars.csv")
    bars = bars[bars["symbol"].isin(symbols)].copy()
    bars["date"] = pd.to_datetime(bars["date"])
    bars = bars.sort_values(["symbol", "date"])
    bars["prev_close"] = bars.groupby("symbol")["close"].shift(1)
    bars["ratio"] = bars["close"] / bars["prev_close"]
    bars = bars.dropna(subset=["ratio"])

    flagged = bars[(bars["ratio"] >= ratio_bar) | (bars["ratio"] <= 1 / ratio_bar)].copy()
    if flagged.empty:
        return flagged.assign(near_split=pd.Series(dtype="object"), is_bankruptcy_ticker=pd.Series(dtype=bool))

    splits = pd.read_csv(sv_store / "splits.csv")
    splits["date"] = pd.to_datetime(splits["date"])

    def nearest_split(row: pd.Series) -> str | None:
        s = splits[splits["symbol"] == row["symbol"]]
        if s.empty:
            return None
        deltas = (s["date"] - row["date"]).abs()
        j = deltas.idxmin()
        days = int(deltas.loc[j].days)
        return f"{s.loc[j, 'ratio']}@{days}d" if days <= SPLIT_WINDOW_DAYS else None

    flagged["near_split"] = flagged.apply(nearest_split, axis=1)
    flagged["is_bankruptcy_ticker"] = flagged["symbol"].str.endswith("Q")
    return flagged[["symbol", "date", "prev_close", "close", "ratio", "near_split", "is_bankruptcy_ticker"]]


def build_excluded_store(
    out_dir: Path, exclude: set[str], sv_store: Path = SV_STORE
) -> dict:
    """Write a copy of ``sv_store`` at ``out_dir`` with every bar row for ``exclude`` removed and
    the manifest correctly recomputed (hashes, fingerprint, row counts), so the copy still loads
    through ``research.load_store`` and `lab survivorship --sv-store` still accepts it (the
    manifest's declared ``purpose`` is untouched).

    This is the "optional exclusion list" M0317 was pre-registered to build: a real store on disk
    that a report command can point at, not a code path that guesses what a filtered trial would
    have done. Only `bars.csv` changes; `splits.csv`, dividends and FX are untouched, so a
    confirmed-bad symbol is removed from the universe rather than patched.
    """
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(sv_store, out_dir)

    bars_path = out_dir / research.BARS_FILE
    lines = bars_path.read_text().splitlines(keepends=True)
    header, rows = lines[0], lines[1:]
    kept = [r for r in rows if r.split(",", 1)[0] not in exclude]
    bars_path.write_text(header + "".join(kept))

    manifest = json.loads((out_dir / research.MANIFEST_FILE).read_text())
    files = {name: research.file_sha256(out_dir / name) for name in manifest["files"]}
    frame = research._read_bars(bars_path, research.DEV_END)
    dividends = research._read_dividends(out_dir / research.DIVIDENDS_FILE, research.DEV_END)
    fx_rows = research._read_fx(out_dir / research.FX_FILE, research.DEV_END)
    unserved = research._read_unserved(out_dir / research.UNSERVED_FILE)
    served = int(frame["symbol"].nunique()) if len(frame) else 0
    manifest.update(
        bar_rows=int(len(frame)),
        dividend_rows=sum(len(v) for v in dividends.values()),
        fx_rows=len(fx_rows),
        symbols_requested=served + len(unserved),
        symbols_served=served,
        files=files,
        fingerprint=research.fingerprint_of(files),
    )
    (out_dir / research.MANIFEST_FILE).write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    research.load_store(out_dir, window=research.DEV_WINDOW)  # raises if anything is inconsistent
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-excluding",
        nargs="+",
        metavar="SYMBOL",
        help="write a filtered copy of the sv-store excluding these symbols (needs --out)",
    )
    parser.add_argument("--out", type=Path, help="output directory for --build-excluding")
    args = parser.parse_args(argv)

    if args.build_excluding:
        if args.out is None:
            parser.error("--build-excluding needs --out")
        manifest = build_excluded_store(args.out, set(args.build_excluding))
        print(f"wrote {args.out}, fingerprint {manifest['fingerprint']}", file=sys.stderr)
        return 0

    symbols = added_symbols()
    print(f"sv-added symbols (sv-store minus dev-store): {len(symbols)}", file=sys.stderr)
    flagged = flag_implausible_moves(symbols=symbols)
    bankrupt = flagged[flagged["is_bankruptcy_ticker"]]
    candidates = flagged[~flagged["is_bankruptcy_ticker"]]
    print(f"flagged rows: {len(flagged)} across {flagged['symbol'].nunique()} symbols", file=sys.stderr)
    print(
        f"  of which real bankruptcies (Q-suffix, not excluded): "
        f"{bankrupt['symbol'].nunique()} symbols: {sorted(bankrupt['symbol'].unique())}",
        file=sys.stderr,
    )
    print(
        f"  reconstruction-failure CANDIDATES (need a human read, see M0317): "
        f"{candidates['symbol'].nunique()} symbols: {sorted(candidates['symbol'].unique())}",
        file=sys.stderr,
    )
    print(flagged.sort_values(["symbol", "date"]).to_string(index=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
