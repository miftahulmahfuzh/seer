---
name: run-the-web-app
description: Use when a change to Seer's Next.js app (web/) needs to be SEEN rather than only tested — "run the app", "screenshot /history", "does this look right on a phone", "check it in dark mode", "did my change actually render", or before claiming any user-visible web change works. Starts the dev server against the real database, signs in without a human, and screenshots any page at phone and desktop widths in both themes.
---

# Run and photograph the Seer web app

Every page under `app/(app)`, `app/sean` and `app/sera` calls `currentUser()` and redirects to
`/signin`, so `curl` returns the sign-in screen and `vitest` + `tsc` are the only proof a change
works. That is not enough: the owner's web bug reports are almost always about what a page **says**
or how it **looks**, and both are invisible to those. This gets you a PNG.

## Two commands

```bash
cd web
npm run dev:env &                    # server on :3111 with the repo-root .env.local loaded
npm run shoot -- '/history?s=MOM-FR-GT' '/history?v=activity'
```

**Nobody has to sign in.** `shoot` keeps a session in `web/.auth/state.json`, renews it when it
has under a day left, and saves the renewal, so a run next month behaves like a run today. There
is no step to remember and nothing to ask the owner for.

Shots and the page's own text land in `web/.shots/` (git-ignored), one pair per page x theme x
width: `history_s-MOM-FR-GT__dark__390.png` and `.txt`. **Read the PNG** — a green exit only means
nothing threw.

Useful flags: `--width 430` (repeatable; default 390 and 1280), `--theme light|dark|both`,
`--full` (whole page, not the viewport), `--out DIR`, `--base URL`.

## It fails the run on these, so trust the exit code for them

HTTP >= 400 · a redirect to `/signin` (the cookie was rejected) · any browser console or page
error · **horizontal scroll at any width**. The last one is the one that earns its keep: the
Activity tab shipped with the Fees column pushed 51px off the right edge of a phone, through a
review that had read the rendered HTML and seen nothing wrong with it.

## The session

`scripts/session.mjs` is the only file that knows what a signed-in session is; `signin.mjs`
produces one and `shoot.mjs` consumes one, through `web/.auth/state.json` (git-ignored).

```
npm run signin                 mint one from AUTH_SECRET       no human, the default
npm run signin -- --paste      re-mint the owner's real one    one copy-paste, no setup
npm run signin -- --google     sign in for real in a browser   needs a Google Console entry
npm run signin -- --check      is the saved session still good?
```

**A minted session is not a lesser session.** `lib/allow.ts` compares `session.user.email` to
`ALLOWED_EMAIL` and `lib/sera/access.ts` does the same for Sera; nothing in the app reads a
Google-specific claim. A minted session carrying the owner's email renders byte-identical pages.
So prefer the default and do not ask him to sign in: it buys an email string that is already in
`.env.local`.

`--paste` exists for when the provenance matters (it carries his real `sub` and 30-day expiry).
It takes the cookie from **the live site** too, not just localhost — see the salt rule below.
`--google` needs `http://localhost:3111/api/auth/callback/google` registered as an Authorized
redirect URI in the Google Cloud Console, and Google sometimes refuses an automated browser;
`--paste` has neither problem.

**THE SALT RULE**, which is the whole trick: Auth.js derives the JWE key from `AUTH_SECRET` **and
the cookie's own name**. Encode with the wrong salt and `auth()` returns null with no error
anywhere — the page just redirects to `/signin` as though nobody were signed in. It is also why a
cookie copied from `https://seertrade.site` (`__Secure-authjs.session-token`) cannot be used
verbatim over http: `--paste` decodes it with its own salt and re-encodes it with ours, keeping
the real identity and expiry.

`scripts/with-env.mjs` loads the repo-root `.env.local` and spawns a plain child. Do not reach for
the obvious alternatives:

- `node --env-file=../.env.local ... next dev` — Next re-execs itself and passes the flag through
  `NODE_OPTIONS`, where node refuses it: *"--env-file= is not allowed in NODE_OPTIONS"*.
- a `web/.env.local` symlink — Next would read it, and it is one `git add -f` from committing the
  production database URL.
- `source .env.local` in zsh — a parse error: `DATABASE_URL` holds an unquoted `&`.

## Gotchas

- **`pkill -f "next dev"` kills your own shell**, because `-f` matches the command line you just
  typed. Free the port instead: `fuser -k 3111/tcp`.
- The server reads the **production** database. Everything here is read-only, but do not add a
  page interaction that writes.
- Auth is never weakened to make this work: `auth.ts` has one provider and no dev bypass, and
  nothing in `app/` changes. Keep it that way — a Credentials provider gated on an env var is the
  usual advice, and it puts an authentication bypass in the source of a site showing real money.
- Playwright's Chromium lives in `~/.cache/ms-playwright` and is not installed by `npm ci`. If
  the launch fails, run `npx playwright install chromium` once. CI never needs it: the browser is
  a local-only download and `playwright` is a devDependency whose npm package alone is small.
