// Composes the home-screen icon: the generated Eye of Horus with its pupil replaced by the Lucide
// Sigma (the A · Quant icon), on the splash's coral. Writes app/apple-icon.png (iOS home screen),
// public/icons/icon-{192,512}.png (manifest) and app/icon.png (favicon, rounded).
//
//   node scripts/make-icon.mjs            reads scripts/.icon/eye.png (promoted from gen_app_icon.py)
//   node scripts/make-icon.mjs --preview  also writes scripts/.icon/preview.png at 1024
//
// The model draws the eye, which nothing else here can do; this draws everything exact. It always
// draws a pupil, but a lumpy one, so it is erased here: the almond's inner lid edges are measured
// either side of it, fitted with a quadratic each, and everything between the two curves across the
// pupil's span becomes ground again. A true circle goes back in its place, larger than the drawn one,
// and the Sigma (Lucide's own path, the glyph the roster draws) is cut out of it in the ground colour.
// The Sigma is grown until it would leave the ink, so its bars run into the lids instead of being
// shrunk to fit the pupil.
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
const SIGMA_STROKE = 4.5; // in Lucide units (its own is 2): heavy enough to stand next to the eye's strokes
const PUPIL = 1.8; // pupil radius over half the opening: big, so it swallows the lids at the centre
const RIM = 0.012; // ink left around the Sigma, as a share of the mask width
const K = 1.5; // the mark is built at 1.5x the source: the splash draws it ~520px wide on a 3x screen

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

// The mark: eye ∪ pupil − Sigma, as an alpha mask at K x the trimmed source, in one colour.
const mw = Math.round(bw * K), mh = Math.round(bh * K);
const openMid = ((openTop + openBot) / 2 - y0) * K; // the opening's centre row, in the mask
const pupilR = (PUPIL * (openBot - openTop) * K) / 2;
const svg = body => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${mw}" height="${mh}">${body}</svg>`);
// Lucide's glyph spans x 6..18, y 4..20, so (12, 12) is its centre.
const sigmaPath = (x, y, height, stroke) => {
  const unit = height / 16;
  return `<g transform="translate(${x - 12 * unit} ${y - 12 * unit}) scale(${unit})"><path d="${SIGMA}" fill="none" stroke="#fff" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round"/></g>`;
};
const alphaChannel = async img => (await sharp(img).ensureAlpha().extractChannel(3).raw().toBuffer());

/** Eye and pupil, white, mirrored or not; the pupil sits where the drawn one was. */
async function inkLayer(mirror) {
  const white = Buffer.alloc(bw * bh * 4, 255);
  for (let y = 0; y < bh; y++) for (let x = 0; x < bw; x++) white[(y * bw + x) * 4 + 3] = alpha[(y + y0) * w + (x + x0)];
  let eye = sharp(white, { raw: { width: bw, height: bh, channels: 4 } });
  if (mirror) eye = eye.flop();
  const px = (mirror ? x1 - cx : cx - x0) * K;
  const blank = { create: { width: mw, height: mh, channels: 4, background: { r: 255, g: 255, b: 255, alpha: 0 } } };
  const img = await sharp(blank)
    .composite([
      { input: await eye.resize(mw, mh, { kernel: 'lanczos3' }).png().toBuffer() },
      { input: svg(`<circle cx="${px}" cy="${openMid}" r="${pupilR}" fill="#fff"/>`) },
    ])
    .png()
    .toBuffer();
  return { img, px };
}

// Grow the Sigma (binary search on its height) while it, widened by the rim, stays inside the ink.
const plain = await inkLayer(false);
const ink = await alphaChannel(plain.img);
const rim = RIM * mw;
const fits = async height => {
  const unit = height / 16;
  const probe = await alphaChannel(svg(sigmaPath(plain.px, openMid, height, SIGMA_STROKE + (2 * rim) / unit)));
  for (let i = 0; i < probe.length; i++) if (probe[i] > 128 && ink[i] < 128) return false;
  return true;
};
let lo = pupilR * 0.5, hi = pupilR * 3;
for (let i = 0; i < 14; i++) { const mid = (lo + hi) / 2; if (await fits(mid)) lo = mid; else hi = mid; }
const sigmaH = lo;
console.log(`pupil r ${(pupilR / K).toFixed(0)} · sigma ${(sigmaH / K).toFixed(0)} tall, stroke ${((SIGMA_STROKE * sigmaH) / 16 / K).toFixed(0)} (source px)`);

/** The finished mark in `colour`: the ink layer with the Sigma cut out, upright even when mirrored. */
async function mark(colour, mirror) {
  const { img, px } = mirror ? await inkLayer(true) : plain;
  const cut = await sharp(img).composite([{ input: svg(sigmaPath(px, openMid, sigmaH, SIGMA_STROKE)), blend: 'dest-out' }]).png().toBuffer();
  const a = await alphaChannel(cut);
  const [r, g, b] = [1, 3, 5].map(k => parseInt(colour.slice(k, k + 2), 16));
  const out = Buffer.alloc(mw * mh * 4);
  for (let i = 0; i < mw * mh; i++) { out[i * 4] = r; out[i * 4 + 1] = g; out[i * 4 + 2] = b; out[i * 4 + 3] = a[i]; }
  return sharp(out, { raw: { width: mw, height: mh, channels: 4 } }).png().toBuffer();
}
const eye = await sharp(await mark(INK, false)).resize(ew, eh, { kernel: 'lanczos3' }).png().toBuffer();

// RGB, never RGBA: iOS composites a transparent apple-touch-icon onto black.
const master = await sharp({ create: { width: PX, height: PX, channels: 3, background: GROUND } })
  .composite([{ input: eye, left: ox, top: oy }])
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

// The favicon: the same art as a rounded tile (the old icon.svg's rx 22 of 100). Transparent
// corners are fine in a browser tab; only the home-screen icons above must stay RGB.
const FAV = 96;
const corners = Buffer.from(
  `<svg xmlns="http://www.w3.org/2000/svg" width="${FAV}" height="${FAV}"><rect width="${FAV}" height="${FAV}" rx="${FAV * 0.22}" fill="#fff"/></svg>`,
);
await sharp(master)
  .resize(FAV, FAV, { kernel: 'lanczos3' })
  .ensureAlpha()
  .composite([{ input: corners, blend: 'dest-in' }])
  .png({ compressionLevel: 9 })
  .toFile(join(WEB, 'app/icon.png'));
console.log(`wrote app/icon.png ${FAV}² (rounded favicon)`);

// The splash: the mark as an alpha mask, painted by CSS in --splash-star so it follows the colour
// scheme. Mirrored, so the spiral hangs right and the pocket under the eye's left end is empty for
// the "Seer." mark; the Sigma is cut after the flip so it stays the right way round.
await sharp(await mark('#ffffff', true)).png({ compressionLevel: 9 }).toFile(join(WEB, 'public/splash-eye.png'));
console.log(`wrote public/splash-eye.png ${mw}x${mh} (splash mask, mirrored) · aspect ${(mw / mh).toFixed(4)}`);

// The in-app header mark: the same mark unmirrored, as a mask painted in --ink. ~58px wide there.
const MARK_W = 240;
await sharp(await mark('#ffffff', false)).resize(MARK_W, Math.round((MARK_W * mh) / mw), { kernel: 'lanczos3' })
  .png({ compressionLevel: 9 }).toFile(join(WEB, 'public/eye-mark.png'));
console.log(`wrote public/eye-mark.png ${MARK_W}x${Math.round((MARK_W * mh) / mw)} (header mask)`);
