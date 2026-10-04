// Composes the home-screen icon: the generated Eye of Horus with its pupil replaced by the Lucide
// Sigma (the A · Quant icon), on the splash's coral. Writes app/apple-icon.png (iOS home screen)
// and public/icons/icon-{192,512}.png (manifest).
//
//   node scripts/make-icon.mjs            reads scripts/.icon/eye.png (promoted from gen_app_icon.py)
//   node scripts/make-icon.mjs --preview  also writes scripts/.icon/preview.png at 1024
//
// The model draws the eye, which nothing else here can do; this draws everything exact. It always
// draws a pupil however hard the prompt forbids it, so the pupil is erased here: the almond's inner
// lid edges are measured either side of the pupil, fitted with a quadratic each, and everything
// between the two curves across the pupil's span becomes ground again. Then the Sigma goes in, from
// Lucide's own path, so it is the same glyph the roster draws.
// sharp comes with next; no extra dependency.
import sharp from 'sharp';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(WEB, 'scripts/.icon/eye.png');
const PREVIEW = process.argv.includes('--preview');

// app/globals.css: --splash and --splash-ink.
const GROUND = '#f47862';
const INK = '#1d1c1a';
// lucide-react sigma, 24-unit box.
const SIGMA = 'M18 7V5a1 1 0 0 0-1-1H6.5a.5.5 0 0 0-.4.8l4.5 6a2 2 0 0 1 0 2.4l-4.5 6a.5.5 0 0 0 .4.8H17a1 1 0 0 0 1-1v-2';
const SIGMA_STROKE = 3; // Lucide's 2 is a hairline at 60px; this matches the eye's stroke weight
const SIGMA_FILL = 0.64; // glyph height as a share of the opening, so its bars clear both lids

const PX = 1024;
const EYE_W = 0.8; // eye width as a fraction of the tile: wide and short, so the squircle's corners stay clear
const LUM_LO = 70; // figure/ground luminance ramp, as in run-insights' make_icon_assets.py
const LUM_HI = 120;

/** Figure alpha (0..255) from luminance: ink is ~30, coral ~150. */
function alphaOf(data, w, h, ch) {
  const a = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) {
    const lum = 0.299 * data[i * ch] + 0.587 * data[i * ch + 1] + 0.114 * data[i * ch + 2];
    a[i] = lum <= LUM_LO ? 255 : lum >= LUM_HI ? 0 : Math.round(((LUM_HI - lum) * 255) / (LUM_HI - LUM_LO));
  }
  return a;
}

/** Chessboard distance to the nearest ground pixel, two-pass. Its maximum is the pupil, the thickest ink. */
function inkDepth(solid, w, h) {
  const d = new Int32Array(w * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (!solid[i]) continue;
      const up = y ? d[i - w] : 0, left = x ? d[i - 1] : 0;
      const ul = x && y ? d[i - w - 1] : 0, ur = y && x < w - 1 ? d[i - w + 1] : 0;
      d[i] = 1 + Math.min(up, left, ul, ur);
    }
  for (let y = h - 1; y >= 0; y--)
    for (let x = w - 1; x >= 0; x--) {
      const i = y * w + x;
      if (!solid[i]) continue;
      const dn = y < h - 1 ? d[i + w] : 0, right = x < w - 1 ? d[i + 1] : 0;
      const dr = x < w - 1 && y < h - 1 ? d[i + w + 1] : 0, dl = x && y < h - 1 ? d[i + w - 1] : 0;
      d[i] = Math.min(d[i], 1 + Math.min(dn, right, dr, dl));
    }
  return d;
}

/** Least-squares quadratic through (x, y) points; returns y(x). */
function fitQuadratic(pts) {
  const s = Array(5).fill(0), t = Array(3).fill(0);
  for (const [x, y] of pts) {
    for (let k = 0; k < 5; k++) s[k] += x ** k;
    for (let k = 0; k < 3; k++) t[k] += y * x ** k;
  }
  const m = [[s[0], s[1], s[2], t[0]], [s[1], s[2], s[3], t[1]], [s[2], s[3], s[4], t[2]]];
  for (let c = 0; c < 3; c++)
    for (let r = c + 1; r < 3; r++) {
      const f = m[r][c] / m[c][c];
      for (let k = c; k < 4; k++) m[r][k] -= f * m[c][k];
    }
  const q = [0, 0, 0];
  for (let r = 2; r >= 0; r--) {
    let acc = m[r][3];
    for (let k = r + 1; k < 3; k++) acc -= m[r][k] * q[k];
    q[r] = acc / m[r][r];
  }
  return x => q[0] + q[1] * x + q[2] * x * x;
}

const { data, info } = await sharp(SRC).removeAlpha().raw().toBuffer({ resolveWithObject: true });
const { width: w, height: h, channels: ch } = info;
const alpha = alphaOf(data, w, h, ch);
const solid = alpha.map(v => (v >= 128 ? 1 : 0));

// The pupil: centre of the deepest ink, radius from its depth.
const depth = inkDepth(solid, w, h);
let pi = 0;
for (let i = 1; i < depth.length; i++) if (depth[i] > depth[pi]) pi = i;
const cx = pi % w, cy = Math.floor(pi / w), r = depth[pi];

// The almond's inner edges, sampled in columns just clear of the pupil: walking up and down from the
// pupil's centre row, the first ink met is the upper and lower lid.
const top = [], bottom = [];
for (let x = Math.round(cx - 3 * r); x <= cx + 3 * r; x++) {
  if (Math.abs(x - cx) < r * 1.25) continue;
  if (solid[cy * w + x]) continue; // in a lid or the corner, not the opening
  let yu = cy, yd = cy;
  while (yu > 0 && !solid[(yu - 1) * w + x]) yu--;
  while (yd < h - 1 && !solid[(yd + 1) * w + x]) yd++;
  if (cy - yu > 2.5 * r || yd - cy > 2.5 * r) continue; // ran out of the eye
  top.push([x, yu]);
  bottom.push([x, yd]);
}
if (top.length < 20) throw new Error(`could not trace the almond around the pupil at (${cx}, ${cy}) r=${r}`);
const topY = fitQuadratic(top), botY = fitQuadratic(bottom);

// Erase the pupil: ground between the two fitted lid edges across the pupil's span, feathered 1px.
for (let x = Math.round(cx - 1.6 * r); x <= cx + 1.6 * r; x++) {
  const y0 = topY(x), y1 = botY(x);
  for (let y = Math.floor(y0); y <= Math.ceil(y1); y++) {
    const edge = Math.min(y - y0, y1 - y);
    const keep = edge >= 1 ? 0 : 1 - Math.max(0, edge);
    alpha[y * w + x] = Math.round(alpha[y * w + x] * keep);
  }
}
const openTop = topY(cx), openBot = botY(cx);
console.log(`pupil (${cx}, ${cy}) r=${r} · opening ${Math.round(openTop)}..${Math.round(openBot)} · ${top.length} columns traced`);

// Trim the eye to its own box and scale it onto the tile.
let x0 = w, y0 = h, x1 = 0, y1 = 0;
for (let y = 0; y < h; y++)
  for (let x = 0; x < w; x++)
    if (alpha[y * w + x] > 8) {
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
const bw = x1 - x0 + 1, bh = y1 - y0 + 1;
const scale = (PX * EYE_W) / bw;
const ew = Math.round(bw * scale), eh = Math.round(bh * scale);
const ox = Math.round((PX - ew) / 2), oy = Math.round((PX - eh) / 2);

const rgba = Buffer.alloc(bw * bh * 4);
const [ir, ig, ib] = [1, 3, 5].map(k => parseInt(INK.slice(k, k + 2), 16));
for (let y = 0; y < bh; y++)
  for (let x = 0; x < bw; x++) {
    const o = (y * bw + x) * 4;
    rgba[o] = ir; rgba[o + 1] = ig; rgba[o + 2] = ib;
    rgba[o + 3] = alpha[(y + y0) * w + (x + x0)];
  }
const eye = await sharp(rgba, { raw: { width: bw, height: bh, channels: 4 } }).resize(ew, eh, { kernel: 'lanczos3' }).png().toBuffer();

// The Sigma, centred in the opening, as tall as the opening allows. Lucide's glyph spans y 4..20.
const sCx = ox + (cx - x0) * scale, sCy = oy + ((openTop + openBot) / 2 - y0) * scale;
const sH = (openBot - openTop) * scale * SIGMA_FILL;
const unit = sH / 16;
const sigma = Buffer.from(
  `<svg xmlns="http://www.w3.org/2000/svg" width="${PX}" height="${PX}" viewBox="0 0 ${PX} ${PX}">` +
    `<g transform="translate(${sCx - 12 * unit} ${sCy - 12 * unit}) scale(${unit})">` +
    `<path d="${SIGMA}" fill="none" stroke="${INK}" stroke-width="${SIGMA_STROKE}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `</g></svg>`,
);

// RGB, never RGBA: iOS composites a transparent apple-touch-icon onto black.
const master = await sharp({ create: { width: PX, height: PX, channels: 3, background: GROUND } })
  .composite([{ input: eye, left: ox, top: oy }, { input: sigma, left: 0, top: 0 }])
  .removeAlpha()
  .png()
  .toBuffer();

const outputs = [
  ['app/apple-icon.png', 180],
  ['public/icons/icon-192.png', 192],
  ['public/icons/icon-512.png', 512],
  ...(PREVIEW ? [['scripts/.icon/preview.png', PX]] : []),
];
for (const [path, size] of outputs) {
  const out = join(WEB, path);
  mkdirSync(dirname(out), { recursive: true });
  await sharp(master).resize(size, size, { kernel: 'lanczos3' }).removeAlpha().png({ compressionLevel: 9 }).toFile(out);
  console.log(`wrote ${path} ${size}²`);
}
