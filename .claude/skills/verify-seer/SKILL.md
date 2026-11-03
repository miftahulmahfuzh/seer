---
name: verify-seer
description: Prove a Seer change works by driving a real, throwaway copy of it (the Next.js app signed in as the owner, the engine CLI, the lab CLI) against its own local Postgres, its own lab.sqlite copy and demo data, and capturing evidence. Use before reporting any web/, engine/ or lab change as done, when a plan's Proof section names feature-map entries, when a verifier must confirm another agent's work, or to reproduce a bug on main. Never touches Neon, seertrade.site, GitHub (workflow dispatches, the sean-receipts branch, pushes), Telegram, Vercel Blob, Gotrade, the committed lab/lab.sqlite or the test window.
---

# verify-seer

"Tests pass" is not proof. Proof is the code under test, running, doing what the owner does, with
the action and the resulting state saved as evidence a reviewer can open. Everything goes through
one script, run from the checkout (or worktree) being verified:

```sh
V=.claude/skills/verify-seer/scripts/verify.sh
$V            # usage
```

The script is bash (shebang), so the zsh the Bash tool may run does not matter. Never hand-write
launch sequences, and never `pkill node` or `pkill -f "next dev"`: the owner's own dev server and
other runs look the same.

## Launch

```sh
$V up                      # demo data, web on a free port: prints RUN= URL= EVIDENCE= MODE=   (~10 s)
$V up --champion=A         # demo data with Strategy A as champion: Today shows bracket tickets, not "no buys"
$V up --empty              # migrations only, no demo seed: what a fresh production DB looks like to the engine
$V up --no-web --empty     # engine and lab only, no Next server (fastest)
$V up --net                # engine may reach read-only public market data (Massive, Finnhub, yfinance, SEC, Frankfurter)
$V up --llm=2              # engine veto/explain may call the real LLM, at most 2 paid drives
```

What a run is:

- **Postgres**: its own database `v_<run>` in the Docker container `seer-pg-verify`
  (127.0.0.1:55437, postgres:16, created on first use, left running). `up` applies every
  `db/migrations/*.sql` with the engine's own `migrate`, then (unless `--empty`) runs
  `web/scripts/seed-demo.mjs` and `seed-demo-sean.mjs`: five paper strategies over 66 sessions,
  24 Sean orders, a plan following F4. The champion is SPY unless `--champion=ID`.
- **Neon shim**: web/ only speaks Neon's HTTP and WebSocket protocols, never TCP, so
  `scripts/neon-shim.mjs` answers both on a loopback port in front of the run's database, and
  `scripts/preload.mjs` (loaded into every Node process via `NODE_OPTIONS`) routes the app's
  `neon()` fetches and the seeders' `Pool` to it. No app code changes.
- **Web**: a snapshot of `web/` (rsync, with `node_modules` hard-linked) served by its own
  `next dev` on a free port. A snapshot because Next 16 locks `next dev` per project directory, so
  two runs, or the owner's dev server on 3111, could not share the checkout. `up` returns once `/`
  answers 200 signed in.
- **Session**: a cookie minted with `web/scripts/session.mjs` and the run's own random
  `AUTH_SECRET`, for the email `lib/sera/access.ts` admits (Sera admits exactly one), which
  `ALLOWED_EMAIL` is set to as well. Nothing in `auth.ts` is bypassed.
- **Lab**: a private copy of `lab/lab.sqlite` (copied read-only, so the committed file is never
  migrated or dirtied), exported as `SEER_LAB_DB`. The dev research store is read from the main
  checkout's `engine/.research` (`SEER_RESEARCH_STORE`).
- **Env**: every process starts from `env -i`, with only the run's own values. Engine processes
  get `SEER_ENV_FILE=<run>/engine.env`, so `.env.local` is never loaded. Harmful keys are blank
  whatever the flags (see Gotchas).

Runs are isolated: parallel verifiers each `up` their own. Measured: two runs up at once, a
dismissal written in one, `action_dismissals` empty in the other.

## Doctor

```sh
$V doctor RUN
```

Read-only. It checks that the shim answers, that `next` is alive, that the port belongs to this
run's process group, that `/` answers 200 with the minted cookie, the DB (migration and strategy
count), the lab copy, the mode and LLM budget, and the engine egress probe (it must NOT reach
api.github.com). It also lists any egress the web side tried and the preload blocked. Run it before the first drive and
after any surprise.

- `code WARN HEAD moved` / `working tree changed since up`: the web **snapshot** is stale (it was
  copied at `up`). `down` and `up` again before driving web. Engine and lab drives always run the
  live checkout (`PYTHONPATH=<checkout>/engine/src`), so they see your edits.
- `egress N BLOCKED POST https://api.github.com` is the preload doing its job. Report what was
  blocked if it matters to the change.

## Drive

| Surface | Command | Notes |
| --- | --- | --- |
| Web page (text) | `$V api RUN GET /path` | Signed in. HTML is saved whole; the visible text (with aria-labels as `[label]`) is printed. |
| HTTP route | `$V api RUN POST /api/... '{json}'` | Cookie + same-origin `Origin`. JSON in, status and body out. |
| Receipt upload | `$V upload RUN image.png` | The body `Uploader.tsx` sends (base64 + sha256) to `POST /api/sean/orders`. |
| Browser | `$V ui RUN steps.mjs [--width 390] [--theme light]` | Playwright, signed in. Video, screenshots, console errors. Default 1280px dark. |
| Screenshots | `$V shoot RUN [--theme dark] [--width 390] /path ...` | The repo's own `web/scripts/shoot.mjs` against this run: fails on HTTP >= 400, /signin, console error, horizontal scroll. |
| Engine | `$V engine RUN [--dry-run] COMMAND ...` | `python -m seer_engine` against the run's DB, lab copy, blanked keys. Prints the exit code. |
| Lab | `$V lab RUN SUBCOMMAND ...` | Same as `engine RUN lab ...`. |
| State | `$V sql RUN "select ..."` | Read-only transaction on the run's Postgres. Writes are refused. |
| Lab state | `$V labsql RUN "select ..."` | Read-only on the run's lab copy. |
| Log | `$V note RUN "what this proved"` | Appends to `evidence/LOG.md`. |

A steps file (the ones in `features/steps/` run as they are; put new ad-hoc ones in the scratchpad):

```js
export default async ({ page, base, shot, log }) => {
  await page.goto(base + '/sean/plan', { waitUntil: 'networkidle' });   // let it hydrate
  await page.getByText('3 things to do').waitFor();
  await page.getByRole('button', { name: /^Mark done:/ }).first().click();
  await page.getByText('2 things to do').waitFor({ timeout: 30000 });
  await shot('after');
  log('marking one reminder done drops the plan from 3 to 2 things to do');
};
```

Use roles and the aria-labels every button carries (CLAUDE.md: icon-only buttons, each with an
`aria-label`): `grep -rhoE 'aria-label="[^"]+"' web/app web/components | sort -u`. Labels that
interpolate data (`Mark done: Buy about $71.48 of KMI`) take a regex. Never coordinates. `ui`
fails the run on a console error, a page error, ending on `/signin`, or horizontal scroll.

Examples, one per surface:

```sh
$V api RUN GET /sean/plan                                   # "Following F4 ... 3 things to do"
$V api RUN POST /api/sera/journal/seen '{"ids":[891,890],"via":"click"}'   # 204
$V sql RUN "select insight_id, via from journal_seen"       # the two rows, via=click
$V ui RUN .claude/skills/verify-seer/features/steps/plan-mark-done.mjs --width 390
$V engine RUN compare                                       # ranks the demo strategies, SPY first
$V lab RUN status                                           # counts from the lab copy
```

## Targeted, not exhaustive

Pick the feature-map entries the change touches and drive those. Offline runs cost nothing.
The default budget for paid drives is 0. `--llm` sets it to 3 and `--llm=N` to N. Each
`engine RUN veto` or `engine RUN explain` spends one, and the script refuses rather than
overspends. `--net` has no budget: those APIs are free tiers, but Massive's free tier is
rate-limited per minute and shared with the production nightly (06:17 UTC, retries 09:41 and
12:41 UTC), so do not drive `--net` near those times.

## Evidence

Everything lands in `~/.local/state/seer-verify/<RUN>/evidence/`, numbered in drive order:
`NN-api-*.txt` (+ `.html`), `NN-engine-*.txt`, `NN-sql-*.txt`, `NN-labsql-*.txt`,
`NN-ui-*.{txt,png,webm}`, `NN-shoot-*/` (PNGs + page text), `LOG.md`, and after `down`,
`zz-next.log`, `zz-shim.log` (every SQL statement the app ran), `zz-seed.log`, `zz-meta`.

Proof standards:

- Drive the real user path: the page, button or route the owner uses, not a lib function or a
  test hook. Writes go through the app (server actions via `ui`, routes via `api`) or the engine
  CLI. `sql` only reads.
- Capture the action AND the resulting state. A 204 is not proof that a row exists: read it back
  with `sql`/`labsql`, and re-render the page that shows it.
- For a bug fix, show the failure first (a run from `main`, or before the fix), then the pass.
- **Read the PNGs.** A green `shoot`/`ui` exit only means nothing threw.
- A step you could not drive is `inconclusive` with its reason. Never weaken a journey to make it
  pass. A run with `MODE=offline` is not proof of anything that needs the network or the LLM.

The report you hand back lists the evidence files that prove each claim, one line each.

## Cleanup

```sh
$V down RUN       # kills exactly the process groups up started, drops v_<run>, deletes the snapshot and lab copy
$V down --all     # every run still up
$V ls             # runs, state, mode, evidence count
```

Evidence survives `down`. Run `down` after every run, failed ones included. The container
`seer-pg-verify` stays up for the next run. It holds nothing but `v_*` databases.

## Feature map

`features/README.md` indexes what Seer does and what proves each feature works, one file per
feature. A plan's **Proof** section names entries from it. A change that adds or alters a
user-facing feature updates its entry in the same change. A journey that fails because the app
is wrong is a product bug: report it, do not edit the entry to match.

## Gotchas

- **Never driven, no flag turns them on (harmful):**
  - Production Neon. The run's env never contains its URL.
  - `GITHUB_DISPATCH_TOKEN`, which would dispatch the production `repick.yml`/`sean.yml`
    workflows and commit receipts to the `sean-receipts` branch, the only copy of the owner's
    order screenshots.
  - `TELEGRAM_*` (messages the owner's phone), `VERCEL_*` and `BLOB_*` (shared deploys and the
    research-store backups), `EODHD_API_TOKEN` (paid personal licence), `OPENROUTER_API_KEY`.
    All of these are blank in every process.
  - Gotrade, the live broker account. Seer has no broker API. Orders are typed by the owner by
    hand, and no code here can place one.
  - Engine `research_store`, `survivorship_store`, `universe_store`, `shares`, `sectors`,
    `market_series`, `dividend_announcements`, `universe_probe`, `backtest*` and `promote`. They
    write shared stores, tracked repo files (backtest reports are frozen records) or the roster.
  - `lab test`, `promote`, `stage`, `export`, `export-json` and `seed`. `test` spends and peeks
    at the test window, which a verifier must never see. `stage` git-adds in the MAIN checkout
    even from a worktree. `--db` is refused too.
- **Off unless a flag opts in:** public market data (`--net`) and the engine's LLM (`--llm`).
  The vision LLM in Sean's upload is never enabled. An upload is saved only after its screenshot
  is committed to the `sean-receipts` branch, which is pinned off, so a successful receipt read
  cannot be produced locally, and paying for it would prove nothing. Offline, an upload answers
  502 "Sean's reader isn't set up yet. Nothing was saved." That is the expected end state.
- **Egress control is best effort.** Engine: a dead `HTTP(S)_PROXY` plus a `NO_PROXY` allowlist,
  which urllib, requests and curl honour. Web: Node's fetch ignores proxy env, so the preload
  wraps `globalThis.fetch` and refuses every non-loopback host except Google Fonts. Code that uses
  `node:http(s)` directly, or Turbopack's own Rust fetcher, is not covered. The web side has no
  dead proxy on purpose: behind one, Turbopack cannot fetch the Outfit font files and every page
  500s ("next/font/google queries have exactly one entry").
- **`paper_check` on demo data reports replay mismatches** (for example `A: replay mismatch (178
  differences)`; exit 1). That is correct: `seed-demo.mjs` writes a hand-made story of snapshots,
  orders and trades, not one the simulator produced, so a replay cannot match it. Drive the
  engine's roster commands on `up --empty`, where `paper_check` exits 0 over 23 roster strategies.
- **A real `nightly` cannot run here.** `--net` gets through config and DB, then stops at "no SPY
  bars stored; run `backfill` first", and `backfill` is a 10-year yfinance crawl. Offline,
  `nightly` exits 2 on the blank `MASSIVE_API_KEY`. Treat both as end states, not failures.
- The web snapshot does not follow your edits. `down` + `up` after changing web/.
- The first hit on each route compiles it, so a page can take 5-20 s once. Recipes pass
  `waitUntil: 'networkidle'` before a screenshot so it lands after hydration.
- The `Demo data` pill wraps onto two lines at 390 px. It is cosmetic, and only demo rows carry it.
- The run's session email is the owner's real address, read from `lib/sera/access.ts`. It sits
  only in a cookie signed with the run's throwaway secret and never leaves the machine.
