#!/usr/bin/env node
// Put a signed-in session in web/.auth/state.json, three ways. `scripts/shoot.mjs` reads it, and
// so can anything else that drives a browser.
//
//   npm run signin                 mint one from AUTH_SECRET          no human, never blocks
//   npm run signin -- --paste      re-mint YOUR real session          one copy-paste, no setup
//   npm run signin -- --google     sign in for real in a browser      needs a Google Console entry
//   npm run signin -- --check      is the saved session still good?
//
// WHICH TO USE. `--mint` is the default because the screenshot harness must never wait for a
// person. Reach for `--paste` when it matters that the session is a real one -- it carries your
// actual Google identity and expiry, costs one copy-paste, and needs no configuration anywhere.
// `--google` is the purist's path and the only one with a prerequisite, below.
import { chromium } from 'playwright';
import {
  COOKIE, SECURE_COOKIE, STATE, cookieFor, loadState, mint, mintedState, ownerEmail, read, saveState,
} from './session.mjs';

const BASE = process.env.SEER_BASE ?? 'http://localhost:3111';
const argv = process.argv.slice(2);
const has = f => argv.includes(f);
const GATED = '/history';

/** Does this state actually get past the redirect? The only check that means anything. */
async function verify(state) {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  try {
    const ctx = await browser.newContext({ storageState: state });
    const page = await ctx.newPage();
    const res = await page.goto(BASE + GATED, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    const url = page.url();
    await ctx.close();
    if (url.includes('/signin')) return { ok: false, why: 'redirected to /signin -- the cookie was rejected' };
    if ((res?.status() ?? 0) >= 400) return { ok: false, why: `HTTP ${res.status()}` };
    return { ok: true, why: `${GATED} rendered as ${ownerEmail()}` };
  } catch (e) {
    return { ok: false, why: `${e.message.split('\n')[0]} -- is the server up? \`npm run dev:env\`` };
  } finally {
    await browser.close();
  }
}

async function readStdin() {
  process.stderr.write(
    `\nPaste the session cookie, then Enter.\n\n` +
    `  1. open https://seertrade.site (or ${BASE}) signed in as yourself\n` +
    `  2. DevTools -> Application -> Cookies -> copy the VALUE of\n` +
    `     ${SECURE_COOKIE}  (https)   or   ${COOKIE}  (http)\n\n> `,
  );
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  return Buffer.concat(chunks).toString().trim();
}

async function paste() {
  const value = await readStdin();
  if (!value) throw new Error('nothing pasted');
  const found = await read(value);
  if (!found) {
    throw new Error(
      'that value is not a session for this AUTH_SECRET.\n' +
      '  Either it was truncated, or the site you copied it from was deployed with a different\n' +
      '  AUTH_SECRET than the one in .env.local. Check with `vercel env pull`.',
    );
  }
  const { token, salt } = found;
  // Re-encode under OUR cookie name: the salt is the name, so a copied https cookie cannot be
  // used verbatim over http. The identity and expiry are the real ones; only the wrapper changes.
  const maxAge = Math.max(60, (token.exp ?? 0) - Math.floor(Date.now() / 1000));
  const { exp, iat, jti, ...claims } = token;
  const value2 = await mint(claims, maxAge);
  console.error(
    `  decoded with salt ${salt === COOKIE ? 'authjs.session-token (http)' : '__Secure-… (https)'}` +
    `, re-minted for ${new URL(BASE).host}`,
  );
  console.error(`  signed in as ${token.email ?? '(no email in the token)'}`);
  if (token.email && token.email !== ownerEmail()) {
    console.error(`  WARNING: ALLOWED_EMAIL is ${ownerEmail()}; auth() will reject this session.`);
  }
  return { cookies: [cookieFor(BASE, value2, Math.floor(Date.now() / 1000) + maxAge)], origins: [] };
}

async function google() {
  const callback = `${BASE}/api/auth/callback/google`;
  console.error(
    `\nOpening a browser at ${BASE}/signin. Sign in with Google; this waits.\n\n` +
    `  PREREQUISITE: ${callback}\n` +
    `  must be an Authorized redirect URI on the OAuth client in the Google Cloud Console.\n` +
    `  Without it Google answers "redirect_uri_mismatch" and no sign-in is possible.\n\n` +
    `  Google also sometimes refuses an automated browser ("this browser may not be secure").\n` +
    `  If that happens, Ctrl-C and use \`--paste\` instead -- same real session, no console change.\n`,
  );
  const browser = await chromium.launch({ headless: false, args: ['--no-sandbox'] });
  try {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await page.goto(`${BASE}/signin`, { waitUntil: 'domcontentloaded' });
    // Done when Auth.js has set the cookie -- not when the URL changes, which it does mid-flow.
    const deadline = Date.now() + 5 * 60_000;
    for (;;) {
      const c = (await ctx.cookies(BASE)).find(c => c.name === COOKIE);
      if (c) { console.error('  signed in.'); return await ctx.storageState(); }
      if (Date.now() > deadline) throw new Error('timed out after 5 minutes waiting for the sign-in');
      if (page.isClosed()) throw new Error('the browser was closed before the sign-in finished');
      await page.waitForTimeout(1000);
    }
  } finally {
    await browser.close();
  }
}

const mode = has('--google') ? 'google' : has('--paste') ? 'paste' : has('--check') ? 'check' : 'mint';

let state;
if (mode === 'check') {
  state = await loadState(BASE);
  if (!state) { console.error(`No usable session in ${STATE} (missing, for another host, or expired).`); process.exit(1); }
} else if (mode === 'paste') {
  state = await paste();
} else if (mode === 'google') {
  state = await google();
} else {
  state = await mintedState(BASE);
  console.error(`  minted for ${ownerEmail()} from AUTH_SECRET`);
}

const v = await verify(state);
if (!v.ok) { console.error(`\nFAILED: ${v.why}`); process.exit(1); }
if (mode !== 'check') await saveState(state.cookies[0]);
const when = new Date(state.cookies[0].expires * 1000).toISOString().replace('T', ' ').slice(0, 16);
console.error(`\nOK: ${v.why}\n  ${mode === 'check' ? STATE : `saved to ${STATE}`}, good until ${when} UTC`);
