#!/usr/bin/env node
// Record an animated GIF of the app, signed in -- `shoot.mjs` for things that move.
//
// A still proves a page renders. It cannot show the three things this app is actually about:
// opening "Why this pick" on a ticket, switching the roster with one icon, and walking the
// method lab from the Overview into a method. The README needs those, and so does any bug report
// about an interaction.
//
// It takes a little scene language, one step per argument, run in order:
//
//   goto:/sera          navigate (same session, same tab)
//   click:SELECTOR      Playwright selector; the frames around the click are kept
//   scroll:PX           scroll down PX pixels, eased over --ease frames
//   hold:MS             stay still for MS (one frame per --interval)
//
//   npm run film -- --out docs/media/today.gif --width 1280 \
//     goto:/ hold:900 'click:text=Why this pick' hold:1500 scroll:400 hold:800
//
// Frames are captured at --interval ms and assembled by ffmpeg with a per-GIF palette, which is
// what keeps a dark UI from banding. ffmpeg must be on PATH.
//
// Options:
//   --out FILE     the .gif to write (required)
//   --base URL     the server (default: http://localhost:3111)
//   --width N      viewport width (default 1280); --height N (default 800)
//   --theme T      light | dark (default: dark)
//   --fps N        GIF frame rate (default 12); --interval MS between captures (default 1000/fps)
//   --scale N      output width in pixels (default 1000); -1 keeps the capture width
//   --ease N       frames a scroll step is spread over (default 10)
//   --keep         keep the PNG frames next to the GIF
import { mkdir, mkdtemp, readdir, rm, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { chromium } from 'playwright';
import { ensureState } from './session.mjs';

const DEFAULTS = { base: 'http://localhost:3111', width: 1280, height: 800, theme: 'dark',
  fps: 12, scale: 1000, ease: 10, keep: false };

function parseArgs(argv) {
  const o = { ...DEFAULTS, steps: [], out: null, interval: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') o.out = argv[++i];
    else if (a === '--base') o.base = argv[++i];
    else if (a === '--width') o.width = Number(argv[++i]);
    else if (a === '--height') o.height = Number(argv[++i]);
    else if (a === '--theme') o.theme = argv[++i];
    else if (a === '--fps') o.fps = Number(argv[++i]);
    else if (a === '--interval') o.interval = Number(argv[++i]);
    else if (a === '--scale') o.scale = Number(argv[++i]);
    else if (a === '--ease') o.ease = Number(argv[++i]);
    else if (a === '--keep') o.keep = true;
    else if (a.startsWith('--')) throw new Error(`unknown option ${a}`);
    else o.steps.push(a);
  }
  if (!o.out) throw new Error('--out FILE is required');
  if (!o.steps.length) throw new Error('no scene steps: try goto:/ hold:1000');
  if (!['light', 'dark'].includes(o.theme)) throw new Error('--theme must be light or dark');
  o.interval ??= Math.round(1000 / o.fps);
  return o;
}

const o = parseArgs(process.argv.slice(2));
const frames = await mkdtemp(join(tmpdir(), 'seer-film-'));
let n = 0;
const problems = [];

const run = (cmd, args) => new Promise((resolve, reject) => {
  const p = spawn(cmd, args, { stdio: ['ignore', 'ignore', 'pipe'] });
  let err = '';
  p.stderr.on('data', d => { err += d; });
  p.on('error', e => reject(new Error(`${cmd}: ${e.message}`)));
  p.on('exit', code => (code === 0 ? resolve() : reject(new Error(`${cmd} exited ${code}\n${err.slice(-2000)}`))));
});

const browser = await chromium.launch({ args: ['--no-sandbox'] });
const { state } = await ensureState(o.base);
const ctx = await browser.newContext({
  viewport: { width: o.width, height: o.height },
  colorScheme: o.theme,
  deviceScaleFactor: 1, // a GIF is not a retina still; 2x quadruples the palette work for nothing
  storageState: state,
  reducedMotion: 'no-preference',
});
const page = await ctx.newPage();
page.on('pageerror', e => problems.push(String(e)));
page.on('console', m => m.type() === 'error' && problems.push(m.text()));

/** One frame, numbered so ffmpeg's glob reads them in order. */
const frame = async () => {
  await page.screenshot({ path: join(frames, `f${String(n++).padStart(5, '0')}.png`) });
};

const hold = async ms => {
  const shots = Math.max(1, Math.round(ms / o.interval));
  for (let i = 0; i < shots; i++) {
    await page.waitForTimeout(o.interval);
    await frame();
  }
};

try {
  for (const step of o.steps) {
    const i = step.indexOf(':');
    const [verb, arg] = i < 0 ? [step, ''] : [step.slice(0, i), step.slice(i + 1)];
    if (verb === 'goto') {
      const res = await page.goto(o.base + arg, { waitUntil: 'networkidle', timeout: 60_000 });
      if ((res?.status() ?? 0) >= 400) problems.push(`${arg} HTTP ${res.status()}`);
      if (page.url().includes('/signin')) problems.push(`${arg} redirected to /signin`);
      await frame();
    } else if (verb === 'click') {
      await page.locator(arg).first().scrollIntoViewIfNeeded();
      await frame();
      await page.locator(arg).first().click({ timeout: 15_000 });
      await frame();
    } else if (verb === 'scroll') {
      const by = Number(arg);
      for (let k = 1; k <= o.ease; k++) {
        // ease-in-out, so the scroll reads as a gesture and not a jump cut
        const t = k / o.ease;
        const e = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
        const prev = (k - 1) / o.ease;
        const ePrev = prev < 0.5 ? 2 * prev * prev : 1 - (-2 * prev + 2) ** 2 / 2;
        await page.mouse.wheel(0, by * (e - ePrev));
        await page.waitForTimeout(o.interval);
        await frame();
      }
    } else if (verb === 'hold') {
      await hold(Number(arg));
    } else {
      throw new Error(`unknown step "${step}" (goto, click, scroll, hold)`);
    }
  }
} finally {
  await ctx.close();
  await browser.close();
}

if (n === 0) throw new Error('no frames captured');
await mkdir(dirname(o.out), { recursive: true });

// One palette for the whole GIF, then dither against it: a flat dark UI banded badly without this.
const vf = `fps=${o.fps},scale=${o.scale}:-1:flags=lanczos`;
const palette = join(frames, 'palette.png');
await run('ffmpeg', ['-v', 'error', '-y', '-framerate', String(o.fps), '-i', join(frames, 'f%05d.png'),
  '-vf', `${vf},palettegen=stats_mode=diff`, palette]);
await run('ffmpeg', ['-v', 'error', '-y', '-framerate', String(o.fps), '-i', join(frames, 'f%05d.png'),
  '-i', palette, '-lavfi', `${vf} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3`,
  '-loop', '0', o.out]);

if (o.keep) {
  const dir = o.out.replace(/\.gif$/, '') + '-frames';
  await mkdir(dir, { recursive: true });
  for (const f of await readdir(frames)) await writeFile(join(dir, f), await (await import('node:fs/promises')).readFile(join(frames, f)));
  console.log(`  frames kept in ${dir}/`);
}
await rm(frames, { recursive: true, force: true });

console.log(`  ${o.out}  ${n} frames @ ${o.fps}fps, ${o.theme}, ${o.width}px wide`);
if (problems.length) {
  console.error('\nPROBLEMS:');
  for (const p of problems) console.error('  ' + p);
  process.exit(1);
}
