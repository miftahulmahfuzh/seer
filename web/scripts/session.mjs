// The one place that knows what a signed-in Seer session is.
//
// Both `scripts/signin.mjs` (which produces one) and `scripts/shoot.mjs` (which consumes one)
// import this, so the cookie name, the salt rule and the storage format are stated once.
//
// THE SALT RULE, which is the whole trick and is easy to get wrong: Auth.js derives the JWE
// encryption key from AUTH_SECRET *and the cookie's own name*. Encode with the wrong salt and
// `auth()` returns null with no error anywhere -- the page just redirects to /signin as if no one
// were signed in. It also means a cookie copied from https://seertrade.site cannot be used
// verbatim on http://localhost: the two have different cookie names, so different salts. It can
// be DECODED with its own salt and re-encoded with ours, which is what `signin --paste` does and
// why that path yields a real session rather than an invented one.
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { decode, encode } from 'next-auth/jwt';

const here = dirname(fileURLToPath(import.meta.url));

/** Auth.js's cookie name over http (no `__Secure-` prefix) -- and therefore our salt. */
export const COOKIE = 'authjs.session-token';
/** What the same cookie is called over https, where Auth.js adds the prefix. */
export const SECURE_COOKIE = `__Secure-${COOKIE}`;
/** Playwright storageState, git-ignored. One artifact, whichever way it was filled. */
export const STATE = join(here, '..', '.auth', 'state.json');

function secret() {
  const s = process.env.AUTH_SECRET;
  if (!s) throw new Error('AUTH_SECRET is not set -- run through `node scripts/with-env.mjs`');
  return s;
}

/** The allowlisted owner. `lib/allow.ts` is the authority; this only needs the first entry. */
export function ownerEmail() {
  const a = process.env.ALLOWED_EMAIL;
  if (!a) throw new Error('ALLOWED_EMAIL is not set -- auth() would reject every email');
  return a.split(',')[0].trim();
}

/**
 * A session token for this app, from a token payload.
 *
 * `maxAge` is seconds. Auth.js stamps `exp` itself from it, so the cookie's own `expires` and the
 * JWT's `exp` are kept in step by passing the same number to both.
 */
export async function mint(token, maxAge = 60 * 60 * 24 * 7) {
  return encode({ token, secret: secret(), salt: COOKIE, maxAge });
}

/**
 * Read a session token, trying the http salt and then the https one.
 *
 * Returns `{ token, salt }`, or null when neither works -- which means the value is not a session
 * for THIS AUTH_SECRET (a different deployment, or a truncated copy-paste).
 */
export async function read(value) {
  for (const salt of [COOKIE, SECURE_COOKIE]) {
    try {
      const token = await decode({ token: value, secret: secret(), salt });
      if (token) return { token, salt };
    } catch {
      // Wrong salt decrypts to garbage and throws; try the other before giving up.
    }
  }
  return null;
}

/** A Playwright cookie for `base`, from a minted or re-minted token value. */
export function cookieFor(base, value, expiresSec) {
  return {
    name: COOKIE,
    value,
    domain: new URL(base).hostname,
    path: '/',
    expires: expiresSec ?? Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 7,
    httpOnly: true,
    secure: false,
    sameSite: 'Lax',
  };
}

export async function saveState(cookie) {
  await mkdir(dirname(STATE), { recursive: true });
  await writeFile(STATE, JSON.stringify({ cookies: [cookie], origins: [] }, null, 2));
  return STATE;
}

/** How long a minted session lasts, and how close to the end `ensureState` renews it. */
export const WEEK = 60 * 60 * 24 * 7;
const RENEW_WITHIN = 60 * 60 * 24;  // a day

/** `sub` of a session this machine minted, as opposed to one a real Google sign-in produced. */
export const MINTED_SUB = 'local-signin';

/**
 * The saved session, or null when there is none, it is for another host, or it expires within
 * `graceSec`. Never throws: a missing or corrupt file just means "no saved session".
 */
export async function loadState(base, graceSec = 300) {
  try {
    const state = JSON.parse(await readFile(STATE, 'utf8'));
    const host = new URL(base).hostname;
    const c = state.cookies?.find(c => c.name === COOKIE && c.domain === host);
    if (!c) return null;
    if (c.expires > 0 && c.expires < Date.now() / 1000 + graceSec) return null;
    return state;
  } catch {
    return null;
  }
}

/** A fresh session for `base`, minted now. The path that needs no human, ever. */
export async function mintedState(base, maxAge = WEEK) {
  const value = await mint({ name: 'Owner', email: ownerEmail(), sub: MINTED_SUB }, maxAge);
  return { cookies: [cookieFor(base, value, Math.floor(Date.now() / 1000) + maxAge)], origins: [] };
}

export const expiresAt = state => new Date(state.cookies[0].expires * 1000);
export const daysLeft = state => (state.cookies[0].expires - Date.now() / 1000) / 86400;
export const isMinted = async state =>
  (await read(state.cookies[0].value))?.token?.sub === MINTED_SUB;

/**
 * A session that works, every time, without asking anyone.
 *
 * Reuses the saved one while it has more than a day left, and otherwise mints a new week and
 * SAVES it -- so a run a month from now behaves exactly like a run today. That persistence is
 * the point: an expiry the owner has to notice is an expiry that interrupts him, and the only
 * thing a sign-in buys this app is an email string it already has in ALLOWED_EMAIL.
 *
 * A real session (`signin --paste` / `--google`) is preferred while it lasts, then replaced by a
 * minted one rather than blocking. `renewed` says which happened, for the caller to report.
 */
export async function ensureState(base) {
  const saved = await loadState(base, RENEW_WITHIN);
  if (saved) return { state: saved, renewed: false, real: !(await isMinted(saved)) };
  const stale = await loadState(base, -Infinity);  // expired, but tells us what it WAS
  const wasReal = stale ? !(await isMinted(stale)) : false;
  const state = await mintedState(base);
  await saveState(state.cookies[0]);
  return { state, renewed: true, real: false, replacedReal: wasReal };
}
