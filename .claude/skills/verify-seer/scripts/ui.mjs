// node ui.mjs <base-url> <steps.mjs> <evidence-dir> <session-cookie> [width] [theme]
// Steps module: `export default async ({ page, base, shot, log }) => { ... }`.
//   shot(name)  full-page screenshot into evidence
//   log(text)   line into the run's ui transcript
// Signed in as the run's owner (the cookie verify.sh minted). Records a video of the whole drive
// and a final screenshot, pass or fail. Fails on a console error, a page error, a redirect to
// /signin, or horizontal scroll at the end, the same failures web/scripts/shoot.mjs refuses.
// Run from the run's web snapshot (resolves playwright from its node_modules).
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { appendFileSync, readdirSync, renameSync, rmSync } from 'node:fs';
import path from 'node:path';

const [base, stepsPath, evidence, cookie, width = '1280', theme = 'dark'] = process.argv.slice(2);
if (!base || !stepsPath || !evidence || !cookie) {
  console.error('usage: node ui.mjs <base-url> <steps.mjs> <evidence-dir> <session-cookie> [width] [theme]');
  process.exit(2);
}

const require = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = require('playwright');

const n = readdirSync(evidence).filter((f) => /^\d\d-.*\.txt$/.test(f)).length;
const tag = `${String(n + 1).padStart(2, '0')}-ui-${path.basename(stepsPath, '.mjs')}`;
const transcript = path.join(evidence, `${tag}.txt`);
const log = (text) => {
  appendFileSync(transcript, `${text}\n`);
  console.log(text);
};

const browser = await chromium.launch({ args: ['--no-sandbox'] });
const context = await browser.newContext({
  viewport: { width: Number(width), height: 900 },
  colorScheme: theme === 'light' ? 'light' : 'dark',
  recordVideo: { dir: path.join(evidence, '.video') },
});
await context.addCookies([{ name: 'authjs.session-token', value: cookie, domain: new URL(base).hostname, path: '/',
  httpOnly: true, secure: false, sameSite: 'Lax' }]);
// Next's dev-tools badge (<nextjs-portal>, bottom-left) exists only under `next dev` and sits on top
// of the desktop rail's lowest icon (Sera), swallowing clicks. Hide it; the app is untouched.
await context.addInitScript(() => {
  const hide = () => {
    const st = document.createElement('style');
    st.textContent = 'nextjs-portal { display: none !important; }';
    document.head.appendChild(st);
  };
  if (document.head) hide(); else document.addEventListener('DOMContentLoaded', hide);
});
const page = await context.newPage();
const problems = [];
page.on('console', (m) => { if (m.type() === 'error') { problems.push(m.text()); log(`console.error: ${m.text()}`); } });
page.on('pageerror', (e) => { problems.push(e.message); log(`pageerror: ${e.message}`); });
let shots = 0;
const shot = async (name) => {
  const file = path.join(evidence, `${tag}-${++shots}-${name}.png`);
  // caret: 'initial' -- the default hides the caret by injecting a style, which races hydration
  // and is reported as a hydration mismatch that the app does not have.
  await page.screenshot({ path: file, fullPage: true, caret: 'initial' });
  log(`screenshot: ${file}`);
};

let failed = null;
try {
  log(`steps: ${stepsPath}  (${width}px, ${theme})`);
  const { default: steps } = await import(pathToFileURL(stepsPath).href);
  await steps({ page, base, shot, log });
  if (page.url().includes('/signin')) throw new Error(`ended on ${page.url()}: the session was rejected`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 0) throw new Error(`horizontal scroll: ${overflow}px wider than the ${width}px viewport`);
  if (problems.length) throw new Error(`${problems.length} console/page error(s)`);
  log('result: PASS');
} catch (err) {
  failed = err;
  log(`result: FAIL ${err?.stack ?? err}`);
} finally {
  await shot(failed ? 'failure' : 'final').catch(() => {});
  const video = page.video();
  await context.close();
  await browser.close();
  if (video) {
    const file = path.join(evidence, `${tag}.webm`);
    renameSync(await video.path(), file);
    rmSync(path.join(evidence, '.video'), { recursive: true, force: true });
    log(`video: ${file}`);
  }
  console.error(`[evidence: ${transcript}]`);
}
process.exit(failed ? 1 : 0);
