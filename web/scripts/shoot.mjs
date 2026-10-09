#!/usr/bin/env node
// Screenshot any page of the app, signed in, against whatever database .env.local points at.
//
// Every page under app/(app) and app/sean and app/sera redirects to /signin, so until this script
// existed a web change could only be proved by vitest and tsc -- and the owner's bug reports are
// usually about what a page SAYS and how it LOOKS, which neither of those can see. The session is
// a JWT and AUTH_SECRET is in .env.local, so the cookie can be minted here rather than signed in
// for.
//
//   node --env-file=../.env.local scripts/shoot.mjs /history?s=MOM-FR-GT
//   node --env-file=../.env.local scripts/shoot.mjs --out /tmp/shots '/history?v=activity' /positions
//
// Options:
//   --out DIR      where the PNGs go (default: .shots/, git-ignored)
//   --base URL     the server (default: http://localhost:3111)
//   --width N      viewport widths, repeatable (default: 390 and 1280 -- phone and desktop)
//   --theme T      light | dark | both (default: both)
//   --full         full-page shot instead of the viewport
//
// Start the server first, with the same env file:
//   node --env-file=../.env.local node_modules/.bin/next dev -p 3111
//
// Exits non-zero if any page 404s, 500s, or logs a console error -- a shell that renders while
// every fetch fails is the failure this is most likely to meet.
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { encode } from 'next-auth/jwt';

const DEFAULTS = { out: '.shots', base: 'http://localhost:3111', theme: 'both', full: false };

function parseArgs(argv) {
  const o = { ...DEFAULTS, widths: [], paths: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') o.out = argv[++i];
    else if (a === '--base') o.base = argv[++i];
    else if (a === '--width') o.widths.push(Number(argv[++i]));
    else if (a === '--theme') o.theme = argv[++i];
    else if (a === '--full') o.full = true;
    else if (a.startsWith('--')) throw new Error(`unknown option ${a}`);
    else o.paths.push(a.startsWith('/') ? a : `/${a}`);
  }
  if (!o.widths.length) o.widths = [390, 1280];
  if (!o.paths.length) o.paths = ['/'];
  if (!['light', 'dark', 'both'].includes(o.theme)) throw new Error(`--theme must be light, dark or both`);
  return o;
}

/** The next-auth session cookie for the allowlisted owner. `salt` must equal the cookie name. */
async function sessionCookie(base) {
  const { AUTH_SECRET, ALLOWED_EMAIL } = process.env;
  if (!AUTH_SECRET) throw new Error('AUTH_SECRET is not set -- run with `node --env-file=../.env.local`');
  if (!ALLOWED_EMAIL) throw new Error('ALLOWED_EMAIL is not set -- auth() would return null for any email');
  const email = ALLOWED_EMAIL.split(',')[0].trim();
  const value = await encode({
    token: { name: 'Owner', email, sub: 'local-shoot' },
    secret: AUTH_SECRET,
    salt: 'authjs.session-token',
    maxAge: 60 * 60,
  });
  const { hostname } = new URL(base);
  return { name: 'authjs.session-token', value, domain: hostname, path: '/', httpOnly: true, sameSite: 'Lax' };
}

/** A filename that survives a query string: /history?s=X&v=activity -> history_s-X_v-activity */
const slug = p =>
  (p.replace(/^\//, '').replace(/[?&]/g, '_').replace(/=/g, '-').replace(/[^\w.-]/g, '_') || 'index');

const o = parseArgs(process.argv.slice(2));
const themes = o.theme === 'both' ? ['light', 'dark'] : [o.theme];
await mkdir(o.out, { recursive: true });

const browser = await chromium.launch({ args: ['--no-sandbox'] });
const cookie = await sessionCookie(o.base);
const problems = [];
const made = [];

for (const theme of themes) {
  for (const width of o.widths) {
    const ctx = await browser.newContext({
      viewport: { width, height: 900 },
      colorScheme: theme,
      deviceScaleFactor: 2,
    });
    await ctx.addCookies([cookie]);
    const page = await ctx.newPage();
    const errors = [];
    page.on('console', m => m.type() === 'error' && errors.push(m.text()));
    page.on('pageerror', e => errors.push(String(e)));

    for (const path of o.paths) {
      errors.length = 0;
      const res = await page.goto(o.base + path, { waitUntil: 'networkidle', timeout: 60_000 });
      const status = res?.status() ?? 0;
      if (status >= 400) problems.push(`${path} [${theme} ${width}] HTTP ${status}`);
      if (page.url().includes('/signin')) problems.push(`${path} [${theme} ${width}] redirected to /signin -- the cookie was rejected`);
      for (const e of errors) problems.push(`${path} [${theme} ${width}] console: ${e}`);

      // The page's own text, so a reader can diff the copy without opening the PNG.
      const text = await page.evaluate(() => document.querySelector('main')?.innerText ?? document.body.innerText);
      const name = `${slug(path)}__${theme}__${width}`;
      await page.screenshot({ path: join(o.out, `${name}.png`), fullPage: o.full });
      await writeFile(join(o.out, `${name}.txt`), text);
      made.push(`${name}.png  HTTP ${status}  ${text.split('\n').length} lines`);
      // A horizontal scrollbar at phone width is the layout bug this catches on its own.
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (overflow > 1) problems.push(`${path} [${theme} ${width}] scrolls ${overflow}px horizontally`);
    }
    await ctx.close();
  }
}
await browser.close();

for (const m of made) console.log('  ' + m);
if (problems.length) {
  console.error('\nPROBLEMS:');
  for (const p of problems) console.error('  ' + p);
  process.exit(1);
}
console.log(`\n${made.length} shot(s) in ${o.out}/ -- no HTTP error, console error or horizontal scroll.`);
