#!/usr/bin/env python3
"""Turn calculate_assets' JSON into the artifact page. Numbers are never retyped by hand."""
import json
import sys
from datetime import date

src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src))

W, H = 980, 430           # chart viewBox
PAD = {"l": 74, "r": 128, "t": 18, "b": 40}
PLOT_W = W - PAD["l"] - PAD["r"]
PLOT_H = H - PAD["t"] - PAD["b"]

Y0 = d["start"][:4]
SERIES = [
    ("book_real", "your book", "var(--s1)", "none", 2.4),
    ("spy", "the same deposits in SPY", "var(--s2)", "none", 2.0),
    ("book_fixed", f"your book, rupiah frozen at {Y0}", "var(--s1)", "5 4", 1.8),
    ("deposited", "what you paid in", "var(--ref)", "none", 1.8),
]


def iso(s):
    return date.fromisoformat(s)


pts = {k: [(iso(a), v) for a, v in d["series"][k]] for k, _l, _c, _dd, _w in SERIES}
xs = [x for x, _ in pts["book_real"]]
x0, x1 = xs[0], xs[-1]
span = (x1 - x0).days or 1
ymax = max(v for k in pts for _, v in pts[k])


def X(dt):
    return PAD["l"] + PLOT_W * (dt - x0).days / span


def Y(v):
    return PAD["t"] + PLOT_H * (1 - v / (ymax * 1.06))


def money(v):
    """Rupiah at a glance, in the units Indonesians actually say them in."""
    if v >= 1e9:
        s = f"{v / 1e9:,.2f}".rstrip("0").rstrip(".")
        return f"Rp {s.replace(',', '.').replace('.', ',', 1) if False else s} M"
    return f"Rp {v / 1e6:,.0f} jt"


def full(v):
    return "Rp " + f"{round(v):,}".replace(",", ".")


def pct(x):
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def fall(x):
    """A drawdown, unsigned: it is a fall, and `+18.0%` reads like a gain."""
    return "n/a" if x is None else f"{abs(x) * 100:.1f}%"


def path(key):
    return "M " + " L ".join(f"{X(dt):.1f} {Y(v):.1f}" for dt, v in pts[key])


# y ticks: 5 rounded steps
step = ymax / 4
mag = 10 ** (len(str(int(step))) - 1)
step = round(step / mag) * mag or mag
ticks = []
t = 0.0
while t <= ymax * 1.06:
    ticks.append(t)
    t += step

years = sorted({x.year for x in xs})
year_ticks = [y for y in years if y % 2 == 0] or years

grid = "".join(
    f'<line class="grid" x1="{PAD["l"]}" y1="{Y(t):.1f}" x2="{PAD["l"] + PLOT_W}" y2="{Y(t):.1f}"/>'
    f'<text class="ytick" x="{PAD["l"] - 10}" y="{Y(t) + 4:.1f}" text-anchor="end">{money(t)}</text>'
    for t in ticks
)
xaxis = "".join(
    f'<text class="xtick" x="{X(date(y, 1, 1)):.1f}" y="{H - 14}" text-anchor="middle">{y}</text>'
    for y in year_ticks
    if x0 <= date(y, 1, 1) <= x1
)
lines = "".join(
    f'<path class="ln" d="{path(k)}" stroke="{c}" stroke-width="{w}"'
    + (f' stroke-dasharray="{dd}"' if dd != "none" else "")
    + "/>"
    for k, _l, c, dd, w in SERIES
)

# direct labels at the right edge, nudged apart so they never collide
ends = sorted(((pts[k][-1][1], k, c) for k, _l, c, _dd, _w in SERIES), reverse=True)
placed, LBL = [], 15
for v, k, c in ends:
    y = Y(v)
    while any(abs(y - p) < LBL for p in placed):
        y += 1
    placed.append(y)
    lines += (
        f'<text class="endlbl" x="{PAD["l"] + PLOT_W + 8}" y="{y + 4:.1f}" fill="{c}">{money(v)}</text>'
    )

rows = "".join(
    f"<tr><td>{l}</td><td class='n'>{full(pts[k][-1][1])}</td><td class='n'>{pct(d[m])}</td></tr>"
    for (k, l, _c, _dd, _w), m in zip(
        SERIES, ["mwr_book_real", "mwr_spy", "mwr_book_fixed", None]
    )
    if m
)

series_json = json.dumps(
    {
        "labels": [x.isoformat() for x in xs],
        "series": [
            {"key": k, "label": l, "color": c, "dash": dd, "v": [v for _, v in pts[k]]}
            for k, l, c, dd, _w in SERIES
        ],
        "geom": {"l": PAD["l"], "t": PAD["t"], "w": PLOT_W, "h": PLOT_H, "W": W, "H": H},
    }
)

paid = d["total_in_idr"]
got = d["end_book_real_idr"]
spy = d["end_spy_idr"]
frozen = d["end_book_fixed_idr"]

HTML = f"""<title>If I Had Started in 2018</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>
:root {{
  color-scheme: light;
  --bg: #faf9f6; --panel: #f3f1ec; --ink: #16201f; --ink2: #4a5654; --ink3: #7b8785;
  --rule: #ddd9d0; --s1: #0d9488; --s2: #c2410c; --ref: #9aa3a1; --hair: #e7e3da;
  --loss: #9f1239;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --bg: #141b1a; --panel: #1b2423; --ink: #eef3f2; --ink2: #a8b4b2; --ink3: #76817f;
    --rule: #2a3534; --s1: #19a89a; --s2: #d4731f; --ref: #6d7876; --hair: #232e2d;
    --loss: #e05570;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg: #141b1a; --panel: #1b2423; --ink: #eef3f2; --ink2: #a8b4b2; --ink3: #76817f;
  --rule: #2a3534; --s1: #19a89a; --s2: #d4731f; --ref: #6d7876; --hair: #232e2d;
  --loss: #e05570;
}}
* {{ box-sizing: border-box; }}
body {{
  background: var(--bg); color: var(--ink);
  font-family: "Source Serif 4", Georgia, serif; font-size: 16.5px; line-height: 1.6;
  margin: 0;
}}
.wrap {{ max-width: 1040px; margin: 0 auto; padding-inline: 22px; padding-block: 46px 70px; }}
h1, h2, h3, .ui {{ font-family: Archivo, "Helvetica Neue", Arial, sans-serif; }}
h1 {{ font-size: clamp(2rem, 5.2vw, 3.1rem); font-weight: 700; letter-spacing: -0.025em;
     line-height: 1.04; margin: 0 0 14px; text-wrap: balance; }}
.sub {{ color: var(--ink2); max-width: 63ch; margin: 0 0 6px; }}
.eyebrow {{ font-family: "IBM Plex Mono", monospace; font-size: 0.72rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--ink3); margin: 0 0 18px; }}
.rule {{ border: 0; border-top: 1px solid var(--rule); margin: 38px 0; }}
.n, .fig, .ytick, .xtick, .endlbl, td.n {{ font-family: "IBM Plex Mono", monospace;
  font-variant-numeric: tabular-nums; }}

.tiles {{ display: grid; gap: 1px; background: var(--rule); border: 1px solid var(--rule);
  grid-template-columns: repeat(3, 1fr); margin: 34px 0 10px; }}
.tile {{ background: var(--bg); padding: 18px 18px 16px; }}
.tile .k {{ font-family: Archivo, sans-serif; font-size: 0.78rem; letter-spacing: 0.04em;
  color: var(--ink2); margin: 0 0 7px; }}
.tile .fig {{ font-size: clamp(1.15rem, 3vw, 1.6rem); font-weight: 500; letter-spacing: -0.02em; }}
.tile .note {{ font-size: 0.84rem; color: var(--ink3); margin-top: 5px; }}
.tile.hero .fig {{ color: var(--s1); }}

figure {{ margin: 26px 0 0; }}
.chartbox {{ position: relative; background: var(--bg); }}
svg {{ display: block; width: 100%; height: auto; overflow: visible; }}
.grid {{ stroke: var(--hair); stroke-width: 1; }}
.ln {{ fill: none; stroke-linejoin: round; stroke-linecap: round; }}
.ytick, .xtick {{ font-size: 11px; fill: var(--ink3); }}
.endlbl {{ font-size: 11.5px; font-weight: 500; }}
.cross {{ stroke: var(--ink3); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0; }}
.dot {{ opacity: 0; }}
figcaption {{ color: var(--ink3); font-size: 0.86rem; margin-top: 12px; }}

.legend {{ display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 16px 0 2px; padding: 0; list-style: none; }}
.legend li {{ display: flex; align-items: center; gap: 8px; font-size: 0.87rem; color: var(--ink2);
  font-family: Archivo, sans-serif; }}
.swatch {{ width: 22px; height: 0; border-top-width: 2.5px; border-top-style: solid; flex: none; }}

#tip {{ position: absolute; pointer-events: none; opacity: 0; transition: opacity .12s;
  background: var(--panel); border: 1px solid var(--rule); padding: 9px 11px; font-size: 0.8rem;
  font-family: Archivo, sans-serif; width: max-content; max-width: min(260px, 76vw); }}
#tip .when {{ font-family: "IBM Plex Mono", monospace; color: var(--ink3); font-size: 0.72rem;
  letter-spacing: 0.06em; margin-bottom: 6px; }}
#tip .row {{ display: flex; justify-content: space-between; gap: 14px; }}
#tip .row b {{ font-family: "IBM Plex Mono", monospace; font-weight: 500; }}

.split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }}
h2 {{ font-size: 1.22rem; font-weight: 600; letter-spacing: -0.012em; margin: 0 0 12px; }}
h3 {{ font-size: 0.96rem; font-weight: 600; margin: 22px 0 6px; }}
p {{ margin: 0 0 13px; max-width: 66ch; }}
.bars {{ list-style: none; padding: 0; margin: 4px 0 0; }}
.bars li {{ margin-bottom: 13px; }}
.bars .lbl {{ display: flex; justify-content: space-between; font-family: Archivo, sans-serif;
  font-size: 0.87rem; margin-bottom: 5px; gap: 12px; }}
.bars .bar {{ height: 9px; background: var(--hair); }}
.bars .bar span {{ display: block; height: 100%; }}

table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
caption {{ text-align: left; font-family: Archivo, sans-serif; font-size: 0.96rem;
  font-weight: 600; padding-bottom: 9px; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--hair); }}
th {{ font-family: Archivo, sans-serif; font-size: 0.78rem; color: var(--ink2); font-weight: 600; }}
td.n, th.n {{ text-align: right; }}
.tablewrap {{ overflow-x: auto; }}
.fine {{ color: var(--ink3); font-size: 0.85rem; }}
@media (max-width: 720px) {{
  .tiles {{ grid-template-columns: 1fr; }}
  .split {{ grid-template-columns: 1fr; gap: 6px; }}
  /* The SVG scales to the screen, so viewBox-unit text shrinks with it: 11px lands at about
     4px on a 400px phone. These sizes are chosen to read at that scale, not on a desktop. */
  .ytick, .xtick {{ font-size: 21px; }}
  .endlbl {{ font-size: 22px; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>

<div class="wrap">
  <p class="eyebrow">{d['candidate']} &middot; {d['start']} to {d['end']} &middot; {d['years']:.1f} years</p>
  <h1>If I had started in {d['start'][:4]}</h1>
  <p class="sub">Ten million rupiah to open and five million more on the 25th of every month,
  bought in fractional shares at Gotrade&rsquo;s real fees, run on the method as it is actually
  written. {d['deposits']} deposits, {d['years']:.1f} years, nothing invented.</p>

  <div class="tiles">
    <div class="tile">
      <p class="k">You would have paid in</p>
      <p class="fig">{full(paid)}</p>
      <p class="note">10jt to open, then 5jt &times; {d['deposits']}</p>
    </div>
    <div class="tile hero">
      <p class="k">You would have ended with</p>
      <p class="fig">{full(got)}</p>
      <p class="note">{pct(d['mwr_book_real'])} a year, money&#8209;weighted</p>
    </div>
    <div class="tile">
      <p class="k">The same deposits in SPY</p>
      <p class="fig">{full(spy)}</p>
      <p class="note">{pct(d['mwr_spy'])} a year, money&#8209;weighted</p>
    </div>
  </div>

  <figure>
    <div class="chartbox">
      <svg viewBox="0 0 {W} {H}" role="img" aria-label="Account value in rupiah from {d['start']} to {d['end']}, four lines: your book, the same deposits in SPY, your book with the rupiah frozen at its 2018 rate, and the money paid in.">
        {grid}{xaxis}{lines}
        <line class="cross" id="cross" y1="{PAD['t']}" y2="{PAD['t'] + PLOT_H}"/>
        <g id="dots"></g>
        <rect id="hit" x="{PAD['l']}" y="{PAD['t']}" width="{PLOT_W}" height="{PLOT_H}" fill="transparent"/>
      </svg>
      <div id="tip"></div>
    </div>
    <ul class="legend">
      {''.join(f'<li><span class="swatch" style="border-top-color:{c};border-top-style:{"dashed" if dd!="none" else "solid"}"></span>{l}</li>' for _k, l, c, dd, _w in SERIES)}
    </ul>
    <figcaption>Hover the chart for any month. Both rupiah lines are the same book: the solid one
    converts every deposit at the rate of the day it landed, the dashed one freezes USD/IDR at its
    {d['start'][:4]} level, so the gap between them is the rupiah and nothing else.</figcaption>
  </figure>

  <hr class="rule">

  <div class="split">
    <div>
      <h2>Where the money came from</h2>
      __LEDE__
      <ul class="bars">
        __BARS__
      </ul>
    </div>
    <div>
      <h2>Reading this honestly</h2>
      <p><strong>The returns are money&#8209;weighted.</strong> That is the rate a savings account
      would have had to pay on the same deposits, on the same days, to reach the same balance. The
      ordinary yearly&#8209;return figure is meaningless here: on a book fed monthly, it counts your
      own deposits as growth and reports numbers in the hundreds of percent.</p>
      <p><strong>The deepest fall reads shallower than it felt.</strong> It was
      {fall(d['max_drawdown'])} on paper, but money kept arriving every month and topping the
      account back up. A fall measured on money that just sat there would look worse.</p>
      <p><strong>{d['trades']:,} trades</strong> over {d['years']:.1f} years, each one paying
      Gotrade&rsquo;s real schedule &mdash; the trading fee with its $0.10 minimum, the regulatory
      fee, and 11% VAT on both.</p>
      __WHY__
    </div>
  </div>

  <hr class="rule">

  <div class="tablewrap">
    <table>
      <caption>At {d['end']}</caption>
      <thead><tr><th>&nbsp;</th><th class="n">Ending value</th><th class="n">A year, money-weighted</th></tr></thead>
      <tbody>
        <tr><td>What you paid in</td><td class="n">{full(paid)}</td><td class="n">&mdash;</td></tr>
        {rows}
      </tbody>
    </table>
  </div>
  <p class="fine" style="margin-top:14px">USD/IDR {d['open_rate']:,.0f} at the start,
  {d['end_rate']:,.0f} at the end. {d['swap']}</p>
</div>

<script>
const D = {series_json};
const tip = document.getElementById("tip"), cross = document.getElementById("cross"),
      dots = document.getElementById("dots"), hit = document.getElementById("hit"),
      g = D.geom, svg = hit.ownerSVGElement;
const n = D.labels.length, ymax = {ymax * 1.06};
const px = i => g.l + g.w * i / (n - 1);
const py = v => g.t + g.h * (1 - v / ymax);
const rp = v => "Rp " + Math.round(v).toLocaleString("de-DE");
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

D.series.forEach(s => {{
  const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  c.setAttribute("r", 4.5); c.setAttribute("fill", s.color); c.setAttribute("class", "dot");
  c.setAttribute("stroke", "var(--bg)"); c.setAttribute("stroke-width", 2);
  dots.appendChild(c); s.node = c;
}});

function at(i) {{
  const when = D.labels[i], [y, m] = when.split("-");
  cross.setAttribute("x1", px(i)); cross.setAttribute("x2", px(i));
  cross.style.opacity = 1;
  let rows = "";
  D.series.forEach(s => {{
    s.node.setAttribute("cx", px(i)); s.node.setAttribute("cy", py(s.v[i]));
    s.node.style.opacity = 1;
    rows += `<div class="row"><span style="color:${{s.color}}">&#9632;</span>` +
            `<span style="flex:1;margin-left:6px">${{s.label}}</span><b>${{rp(s.v[i])}}</b></div>`;
  }});
  tip.innerHTML = `<div class="when">${{MON[+m - 1]}} ${{y}}</div>${{rows}}`;
  tip.style.opacity = 1;
  const box = svg.getBoundingClientRect(), scale = box.width / g.W;
  const left = px(i) * scale, flip = left > box.width - 230;
  tip.style.left = (flip ? left - tip.offsetWidth - 14 : left + 14) + "px";
  tip.style.top = Math.max(4, py(Math.max(...D.series.map(s => s.v[i]))) * scale - 10) + "px";
}}

function near(ev) {{
  const box = svg.getBoundingClientRect();
  const x = (ev.clientX - box.left) / (box.width / g.W);
  return Math.max(0, Math.min(n - 1, Math.round((x - g.l) / g.w * (n - 1))));
}}
hit.addEventListener("pointermove", e => at(near(e)));
function rest() {{
  tip.style.opacity = 0; cross.style.opacity = 0;
  D.series.forEach(s => {{
    s.node.setAttribute("cx", px(n - 1)); s.node.setAttribute("cy", py(s.v[n - 1]));
    s.node.style.opacity = 1;
  }});
}}
hit.addEventListener("pointerleave", rest);
rest();
</script>
"""

# the decomposition bars, computed here so the page never carries a hand-typed figure
edge = got - spy
parts = [
    ("What you paid in", paid, "var(--ref)"),
    ("What being in the market added", spy - paid, "var(--s2)"),
    (
        "What the method added over SPY" if edge >= 0 else "What the method cost you against SPY",
        edge,
        "var(--s1)" if edge >= 0 else "var(--loss)",
    ),
]
total = max(got, spy, paid)
bars = "".join(
    f'<li><div class="lbl"><span>{k}</span>'
    f'<span class="n"{"" if v >= 0 else ' style="color:var(--loss)"'}>{full(v)}</span></div>'
    f'<div class="bar"><span style="width:{max(0.6, 100 * abs(v) / total):.1f}%;background:{c}"></span></div></li>'
    for k, v, c in parts
)

if edge >= 0:
    lede = (
        f"<p>Of the {full(got)} at the end, {full(paid)} is simply what you put in. The deposits "
        f"are most of the answer, and the method added {full(edge)} on top of what being in the "
        f"market gave you anyway.</p>"
    )
else:
    lede = (
        f"<p>Of the {full(got)} at the end, {full(paid)} is simply what you put in &mdash; the "
        f"deposits are most of the answer. The rest is not the method&rsquo;s doing. Putting the "
        f"identical deposits into SPY on the identical days would have ended at {full(spy)}, so "
        f"over these {d['years']:.1f} years the method <strong>cost</strong> you "
        f"{full(abs(edge))} against simply buying the market.</p>"
        f"<p>Your instinct was right, and it is the bigger half of the answer: time and the habit "
        f"of paying in every month did the work. The stock-picking did not.</p>"
    )

if edge >= 0:
    why = ""
else:
    why = (
        "<p><strong>Why it lost, and it was predicted.</strong> This book only buys when the "
        "market is above its long trend, so it sat in cash through early 2020 and much of 2022 "
        "&mdash; exactly the months a monthly buyer&rsquo;s new money was buying cheapest. "
        "M0032&rsquo;s own pre-registered note said this would happen: a money-weighted return "
        "&ldquo;rewards being invested when the money arrives&rdquo;, and the gate that makes this "
        "method look safe on a lump sum is what makes it lose on a monthly one.</p>"
    )
HTML = HTML.replace("__BARS__", bars).replace("__LEDE__", lede).replace("__WHY__", why)
open(out, "w").write(HTML)
print(f"wrote {out} ({len(HTML):,} bytes)")
