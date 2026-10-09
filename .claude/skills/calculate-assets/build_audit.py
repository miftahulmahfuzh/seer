#!/usr/bin/env python3
"""The roster audit page, built from the calculate-assets JSONs and the lab's own verdicts."""
import json
import sys
from datetime import date

S = "/tmp/claude-1000/-home-miftah-seer/a9bbceac-2a9d-48c8-a03d-1c5630d980bb/scratchpad"
out = sys.argv[1]

# roster id -> (what it is, the json, the lab's formal verdict on this METHOD)
ROWS = [
    ("MVW-FR-GT", "MVW · Steady weights", "M0008-N30-C07", f"{S}/M0008-N30-C07.json",
     "M0008", "rejected — never testable", "Re-evaluated today and still rejected at the current bars, so the lab will not give it a look."),
    ("RAW-FR-GT", "RAW · Unbraked momentum", "M0007-N20-RAW", f"{S}/assets.json",
     "M0007", "dev-eligible — no formal look", "The variant you hold. Measured as a report today; its method has never spent a counted look."),
    ("MOM-FR-GT", "MOM · Regime momentum", "M0002-REL-85", f"{S}/M0002-REL-85.json",
     "M0002", "test-failed", "Formally tested today on the exact variant you hold. Failed beats SPY TR, max DD and PF."),
    ("RMW-FR-GT", "RMW · Braked momentum", "M0022-W-TV16", f"{S}/M0022-W-TV16.json",
     "M0022", "test-failed", "The lab tested W-TV14, its best variant, not the W-TV16 you hold. It failed three conditions."),
]

rows = []
for rid, name, cand, path, mid, verdict, note in ROWS:
    d = json.load(open(path))
    rows.append(dict(rid=rid, name=name, cand=cand, mid=mid, verdict=verdict, note=note, d=d))

base = rows[0]["d"]
PAID = base["total_in_idr"]
SPY = base["end_spy_idr"]
SPY_R = base["mwr_spy"]
START, END, YEARS = base["start"], base["end"], base["years"]
rows.sort(key=lambda r: -r["d"]["end_book_real_idr"])
TOP = max(SPY, *[r["d"]["end_book_real_idr"] for r in rows])


def full(v):
    return "Rp " + f"{round(v):,}".replace(",", ".")


def money(v):
    return f"Rp {v/1e9:.2f} M".replace(".", ",") if v >= 1e9 else f"Rp {v/1e6:,.0f} jt"


def pct(x):
    return "n/a" if x is None else f"{x*100:+.1f}%"


def fall(x):
    return "n/a" if x is None else f"{abs(x)*100:.1f}%"


def bar(v, colour, label):
    w = max(0.5, 100 * v / TOP)
    return (f'<div class="brow"><div class="bname">{label}</div>'
            f'<div class="btrack"><span style="width:{w:.1f}%;background:{colour}"></span></div>'
            f'<div class="bval n">{full(v)}</div></div>')


bars = bar(SPY, "var(--s2)", "Just buying SPY")
for r in rows:
    bars += bar(r["d"]["end_book_real_idr"], "var(--s1)", r["name"].split(" · ")[0])
bars += bar(PAID, "var(--ref)", "What you paid in")

# ---- small multiples: each book's value as a fraction of SPY's, same deposits both sides ----
SW, SH, SP = 250, 78, 8
spark = ""
for r in rows:
    d = r["d"]
    b = {date.fromisoformat(a): v for a, v in d["series"]["book_real"]}
    s = {date.fromisoformat(a): v for a, v in d["series"]["spy"]}
    days = [t for t in sorted(b) if s.get(t)]
    rat = [(t, b[t] / s[t]) for t in days]
    lo, hi = min(v for _, v in rat), max(max(v for _, v in rat), 1.0)
    span = (days[-1] - days[0]).days or 1

    def X(t):
        return SP + (SW - 2 * SP) * (t - days[0]).days / span

    def Y(v):
        return SP + (SH - 2 * SP) * (1 - (v - lo) / ((hi - lo) or 1))

    path = "M " + " L ".join(f"{X(t):.1f} {Y(v):.1f}" for t, v in rat)
    one = Y(1.0)
    end = rat[-1][1]
    spark += f"""
    <figure class="sm">
      <figcaption><strong>{r['name']}</strong><span class="n">{end:.2f}&times;</span></figcaption>
      <svg viewBox="0 0 {SW} {SH}" role="img" aria-label="{r['name']} ended at {end:.2f} times SPY">
        <line class="one" x1="{SP}" y1="{one:.1f}" x2="{SW-SP}" y2="{one:.1f}"/>
        <text class="onelbl" x="{SW-SP}" y="{one-4:.1f}" text-anchor="end">SPY</text>
        <path class="sl" d="{path}"/>
        <circle class="sd" cx="{X(days[-1]):.1f}" cy="{Y(end):.1f}" r="3"/>
      </svg>
    </figure>"""

table = "".join(
    f"<tr><td><strong>{r['name']}</strong><br><span class='fine'>{r['cand']}</span></td>"
    f"<td class='n'>{full(r['d']['end_book_real_idr'])}</td>"
    f"<td class='n'>{pct(r['d']['mwr_book_real'])}</td>"
    f"<td class='n loss'>{full(r['d']['end_book_real_idr'] - SPY)}</td>"
    f"<td class='n'>{fall(r['d']['max_drawdown'])}</td>"
    f"<td><span class='tag {'bad' if 'failed' in r['verdict'] else 'warn'}'>{r['verdict']}</span></td></tr>"
    for r in rows
)

HTML = f"""<title>The Roster Against SPY</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
:root {{
  color-scheme: light;
  --bg:#faf9f6; --panel:#f3f1ec; --ink:#16201f; --ink2:#4a5654; --ink3:#7b8785;
  --rule:#ddd9d0; --hair:#e7e3da; --s1:#0d9488; --s2:#c2410c; --ref:#9aa3a1; --loss:#9f1239;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  color-scheme: dark;
  --bg:#141b1a; --panel:#1b2423; --ink:#eef3f2; --ink2:#a8b4b2; --ink3:#76817f;
  --rule:#2a3534; --hair:#232e2d; --s1:#19a89a; --s2:#d4731f; --ref:#6d7876; --loss:#e05570;
}} }}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg:#141b1a; --panel:#1b2423; --ink:#eef3f2; --ink2:#a8b4b2; --ink3:#76817f;
  --rule:#2a3534; --hair:#232e2d; --s1:#19a89a; --s2:#d4731f; --ref:#6d7876; --loss:#e05570;
}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--ink);margin:0;
  font-family:"Source Serif 4",Georgia,serif;font-size:16.5px;line-height:1.6}}
.wrap{{max-width:1000px;margin:0 auto;padding-inline:22px;padding-block:46px 70px}}
h1,h2,.ui{{font-family:Archivo,"Helvetica Neue",Arial,sans-serif}}
h1{{font-size:clamp(1.9rem,5vw,2.9rem);font-weight:700;letter-spacing:-.025em;line-height:1.05;
  margin:0 0 14px;text-wrap:balance}}
h2{{font-size:1.2rem;font-weight:600;margin:0 0 14px;letter-spacing:-.012em}}
.eyebrow{{font-family:"IBM Plex Mono",monospace;font-size:.72rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--ink3);margin:0 0 18px}}
.sub{{color:var(--ink2);max-width:64ch;margin:0 0 8px}}
.n{{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}}
.fine{{color:var(--ink3);font-size:.82rem}}
hr{{border:0;border-top:1px solid var(--rule);margin:36px 0}}
p{{margin:0 0 13px;max-width:66ch}}

.verdict{{border-left:3px solid var(--loss);background:var(--panel);padding:16px 18px;margin:28px 0 0}}
.verdict p{{margin:0}}
.verdict strong{{font-family:Archivo,sans-serif}}

.brow{{display:grid;grid-template-columns:150px 1fr 160px;align-items:center;gap:14px;
  margin-bottom:9px;font-family:Archivo,sans-serif;font-size:.88rem}}
.btrack{{background:var(--hair);height:19px}}
.btrack span{{display:block;height:100%}}
.bval{{text-align:right;font-size:.86rem}}

.sms{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:20px 26px;margin-top:6px}}
.sm{{margin:0}}
.sm figcaption{{display:flex;justify-content:space-between;gap:10px;font-family:Archivo,sans-serif;
  font-size:.83rem;color:var(--ink2);margin-bottom:2px}}
.sm svg{{display:block;width:100%;height:auto;overflow:visible}}
.sl{{fill:none;stroke:var(--s1);stroke-width:1.8;stroke-linejoin:round}}
.sd{{fill:var(--s1)}}
.one{{stroke:var(--s2);stroke-width:1;stroke-dasharray:3 3}}
.onelbl{{font-size:8px;fill:var(--s2);font-family:"IBM Plex Mono",monospace}}

table{{border-collapse:collapse;width:100%;font-size:.88rem}}
th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--hair);vertical-align:top}}
th{{font-family:Archivo,sans-serif;font-size:.76rem;color:var(--ink2);font-weight:600}}
td.n,th.n{{text-align:right}}
td.loss{{color:var(--loss)}}
.tablewrap{{overflow-x:auto}}
.tag{{font-family:Archivo,sans-serif;font-size:.72rem;padding:2px 7px;white-space:nowrap;
  border:1px solid currentColor}}
.tag.bad{{color:var(--loss)}}
.tag.warn{{color:var(--ink2)}}
.notes li{{margin-bottom:9px;color:var(--ink2);font-size:.93rem}}
@media (max-width:640px){{
  .brow{{grid-template-columns:1fr;gap:3px;margin-bottom:15px}}
  .bval{{text-align:left}}
  .onelbl{{font-size:13px}}
}}
</style>

<div class="wrap">
  <p class="eyebrow">Paper roster &middot; {START} to {END} &middot; {YEARS:.1f} years &middot; 10jt + 5jt monthly at Gotrade fees</p>
  <h1>The roster against SPY</h1>
  <p class="sub">Every strategy on the paper roster, run on the owner&rsquo;s real funding plan over
  the window his real money would have covered, against a SPY fed the identical deposits on the
  identical days.</p>

  <div class="verdict">
    <p><strong>All four lost.</strong> Not one of the four strategies beat simply buying the index,
    and every one of them fell further than the 20% the roster&rsquo;s own risk rule allows. The
    best of them finished {full(SPY - rows[0]['d']['end_book_real_idr'])} behind SPY; the worst,
    {full(SPY - rows[-1]['d']['end_book_real_idr'])} behind.</p>
  </div>

  <hr>
  <h2>What {full(PAID)} of deposits became</h2>
  {bars}

  <hr>
  <h2>How much of SPY each one kept</h2>
  <p class="sub">Each book divided by the SPY that received the same deposits, month by month. The
  dashed line is SPY itself. A line below it is money the strategy gave away for being clever.</p>
  <div class="sms">{spark}</div>

  <hr>
  <h2>The record</h2>
  <div class="tablewrap">
    <table>
      <thead><tr><th>Strategy</th><th class="n">Ended with</th><th class="n">A year</th>
        <th class="n">vs SPY</th><th class="n">Deepest fall</th><th>Lab verdict</th></tr></thead>
      <tbody>
        <tr><td><strong>Just buying SPY</strong><br><span class="fine">the benchmark on the roster</span></td>
          <td class="n">{full(SPY)}</td><td class="n">{pct(SPY_R)}</td><td class="n">&mdash;</td>
          <td class="n">&mdash;</td><td><span class="tag warn">champion</span></td></tr>
        {table}
        <tr><td>What you paid in</td><td class="n">{full(PAID)}</td><td class="n">&mdash;</td>
          <td class="n">&mdash;</td><td class="n">&mdash;</td><td></td></tr>
      </tbody>
    </table>
  </div>

  <hr>
  <h2>How each one got onto the roster</h2>
  <ul class="notes">
    {''.join(f"<li><strong>{r['name']}</strong> &mdash; admitted by owner-override while {r['mid']} read <em>rejected</em>. {r['note']}</li>" for r in rows)}
  </ul>
  <p class="fine" style="margin-top:18px">Returns are money-weighted and taken over the rupiah: the
  rate a savings account would have had to pay on the same deposits, on the same days, to reach the
  same balance. Deepest falls read shallower than they felt, because monthly deposits keep topping
  the account up. Every figure here is computed from the runs, not transcribed.</p>
</div>
"""
open(out, "w").write(HTML)
print(f"wrote {out} ({len(HTML):,} bytes)")
