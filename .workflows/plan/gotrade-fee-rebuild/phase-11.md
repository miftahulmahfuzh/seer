# Phase 11: One daily line: stepped, published, green, paused

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R8 (handover §8 Q8) — one line a day reaches the owner carrying four facts, so silence stops being the only signal
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `.github/workflows`, `docs/runbooks`

---

## Goal

After this phase a message arrives on the owner's phone every day at 21:23 WIB (14:23 UTC) whose
**first line** carries all four facts — session stepped y/n, picks published y/n, CI green y/n,
paper paused y/n — and whose body says, in plain words, why each fact reads the way it does. It
lives in its own workflow, so it can report *"the nightly did not run"*, which nothing inside
`nightly.yml` can. Today it will say `CHECK · stepped n/a · picks n/a · CI red · paper PAUSED`, and
every word of that is correct and deliberate.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `.github/workflows/watch.yml` (new file) — workflow `name: Daily watch`, concurrency group
  `seer-watch`, schedule `cron: '23 14 * * *'`, plus `workflow_dispatch`
- `docs/runbooks/monitoring.md` (new file)
- two **new repository secrets** the owner must configure: `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID` (see Step 3 and the runbook's Owner steps)

**Signature changes:** none
**Requires (from earlier phases):** none. This phase has no `depends_on` and compiles against the
tree exactly as it stands at `485d416`.

**Reads but never writes:**
- `.github/workflows/nightly.yml` — read with `sed` for the value of `PAPER_PAUSED` only. The file
  is **not edited**; phase 12 owns its comment.
- Neon, via `SELECT` only, through the existing `DATABASE_URL_UNPOOLED` secret. Tables read:
  `paper_state`, `runs`, `book_targets`. No `INSERT`, `UPDATE`, `DELETE` or `migrate`.
- The GitHub Actions API, via `gh run list` on `engine-ci.yml`, with `permissions: actions: read`.

**Leaves alone (owned by others):**
- `.github/workflows/nightly.yml` content (Phase 12)
- `.github/workflows/engine-ci.yml` (Phase 1) — this phase *reports* CI's colour, it does not fix it
- `docs/runbooks/paper-trading.md` (Phase 12), including its stale schedule line at `:76`
- every file under `engine/`, `web/`, `db/`, `lab/`
- `.github/workflows/backfill.yml`, `repick.yml`, `universe.yml`, `sean.yml`
- `docs/ROADMAP.md` (nobody owns it in this set — see Handoffs)

**Concurrency contract, stated because it is a shared resource:** `watch.yml` joins group
`seer-watch`, **not** `seer-db-writer`. `sean.yml:8-10` records the rule this obeys verbatim: *"a
pending Sean run queued in `seer-db-writer` would cancel a pending nightly retry (GitHub keeps one
pending run per group)"*. `nightly.yml`, `backfill.yml`, `repick.yml` and `universe.yml` are the four
members of `seer-db-writer`; this phase adds no fifth.

## Files

| File | Action | What changes |
|---|---|---|
| `.github/workflows/watch.yml` | create | the whole watcher: schedule, the four reads, the composed line, the send |
| `docs/runbooks/monitoring.md` | create | what the line means, the owner's one-time setup, and what to do per bad fact |

---

## Settled decisions

These are the five forks the phase brief said not to leave open. Each is settled here with the
evidence that settled it, so the implementer does not re-open them.

### W1. How the line reaches the owner — **Telegram**

**Chosen:** a Telegram bot, one `curl` to `api.telegram.org/bot<TOKEN>/sendMessage`.

**Why not reuse the GitHub red-run email the owner already gets.** That path exists today and is
measured to have failed at exactly this job: handover §8 Q8 records *"CI went red for ~9 hours
unnoticed"*. It also cannot carry a daily line — it fires only on failure, so on a good day it says
nothing, and "nothing" is precisely the signal this phase exists to replace. And it structurally
cannot say *"paper is paused on purpose"*, because a deliberate pause is not a failure.

**Why not SMTP email.** Needs an SMTP account and an app password configured, pulls in a third-party
marketplace action, and lands in the same inbox the GitHub run emails are already being lost in.
More to configure for a channel measured to be the one that failed.

**Why not a GitHub issue a day.** 365 issues a year, and it only emails the owner if he happens to
be subscribed to issue activity — the dashboard-nobody-opens pattern with extra steps.

**Why Telegram specifically.** It is the repo's own stated direction, not a channel invented here:
`docs/ROADMAP.md:122` already reads *"Notifications (e.g. Telegram) for picks and day-5 exits"*. It
is a push notification on a phone, which is the only delivery that does not require the owner to go
and look. It is one `curl`, no action dependency.

**What it costs.** The Telegram Bot API is free, with no account beyond a Telegram account the owner
already has. The GitHub Actions cost is one `ubuntu-latest` job a day, under 30 seconds of work;
GitHub bills whole minutes, so 1 minute/day = about 30 minutes a month, which is 1.5% of the 2,000
free minutes a month a private repo gets, and nothing at all if the repo is public.

**What it needs configured.** Exactly two repository secrets, once: `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`. The runbook's *Owner steps* gives the five commands.

**The fallback, which is the point of keeping the old path meaningful.** The watcher never turns red
because a *fact* is bad. It turns red only when it could not do its own job — could not read the
pause switch, could not reach Neon, could not reach the Actions API, or could not deliver the line
(including: the two secrets are not set). In every one of those cases the composed line is printed
into an `::error::` annotation and the job summary first, and GitHub's existing red-run email becomes
the carrier. So the channel the owner already has stays as the alarm for *"the watcher itself is
broken"*, and Telegram carries *"here is today"*.

### W2. When it fires — **14:23 UTC = 21:23 WIB, every day**

`cron: '23 14 * * *'`.

The arithmetic, from `nightly.yml:15-19` and `:40`:

| | UTC | WIB |
|---|---|---|
| nightly, first slot | 06:17 | 13:17 |
| nightly, retry 1 | 09:41 | 16:41 |
| nightly, **last retry** | 12:41 | 19:41 |
| last retry + `timeout-minutes: 45` | **13:26** | **20:26** |
| **watcher** | **14:23** | **21:23** |

14:23 UTC is 1 h 42 m after the last retry slot fires and 57 minutes after the latest moment an
on-time 45-minute run started in that slot could still be going. It is therefore in a slot that can
actually observe the nightly's outcome, which is the requirement. Minutes are off `:00` and `:30` on
purpose, following the convention `nightly.yml:11-12` already states: *"GitHub's scheduler runs hours
late on :00 and :30."*

It runs **all seven days** (`* * *`), not Tue–Sat. That is deliberate: on a day the nightly is not
scheduled the owner still gets a line, and the line says the nightly was not due — which is the
difference between "quiet because nothing was supposed to happen" and "quiet because it broke".
See W5.

14:23 UTC and 21:23 WIB are the same calendar day (WIB is UTC+7), so the line's date never
disagrees with itself.

### W3. Which concurrency group — **`seer-watch`, its own, `cancel-in-progress: false`**

It is a reader: three `SELECT`s, one `gh` call, one `grep`. It must not join `seer-db-writer`, for
the reason `sean.yml:8-10` already wrote down and which cost that workflow its own group: GitHub
keeps **one** pending run per group, so a watcher queued in `seer-db-writer` at 14:23 could cancel a
pending nightly retry. The whole point of this phase is to not break the thing it watches.

`cancel-in-progress: false` rather than `true`: the job is ~30 seconds, so a queue costs nothing, and
`true` would let a manual `workflow_dispatch` cancel the scheduled run and silently eat that day's
line.

### W4. What it says when paper is paused — **n/a, with the reason, and never `CHECK`**

Paused is the state today (`nightly.yml:70`, `PAPER_PAUSED: 'true'` since `d44fa78`). While paused,
`nightly.yml:114,128,138,149` skip Veto, Paper, Paper check and Explain, so `paper_state` cannot
advance and no new `book_targets` can appear. Reporting those two facts as `no` would be reporting a
deliberate decision as a failure, every day, which is how an alert gets ignored.

So while paused, facts 1 and 2 read `n/a`, their reason line reads *"paper is paused on purpose"*,
fact 4 reads `paper PAUSED`, and the headline's status word stays `OK` unless CI is red. The pause is
never, by itself, a reason to say `CHECK`. The owner still sees the word `PAUSED` in the headline
every single day, which is the other half of Q8: *"nothing will announce it if that is forgotten."*

The pause takes precedence over W5's not-scheduled reason, because it is the larger and
longer-lived fact.

### W5. What it says on a day the nightly is not scheduled — **n/a, naming the schedule**

`nightly.yml:15,18,19` are all `* * 2-6` — Tuesday to Saturday **UTC**, reading Monday to Friday's
session. On UTC Sunday and Monday there is no nightly at all.

The watcher computes `date -u '+%u'` (1 = Monday … 7 = Sunday) and treats `2..6` as scheduled, which
is the same numbering the cron uses for this range. When it is not scheduled, facts 1 and 2 read
`n/a` with the reason *"no nightly runs today — the nightly runs Tue-Sat UTC, 13:17 WIB"*, and the
status word stays `OK` unless CI is red.

### W6. The orphan trap — **the nightly's outcome is read from Neon, never from the Actions API**

Handover §6c: run `37655513074` has been `queued` since 2026-10-07T16:54:08Z with `jobs []`,
`run_attempt 1` and `updated_at` still equal to `created_at`. Anything reading `gh run list` naively
would call it "the nightly is running" forever.

Two independent defences, in order:

1. **Facts 1 and 2 never touch the Actions API.** They are read from `paper_state`, `runs` and
   `book_targets` — the *outcome*, not the *attempt*. A run that never created a job never wrote a
   row, so a permanently-queued orphan is invisible to them by construction. This also means the
   watcher correctly catches the case the brief names as structurally impossible from inside the
   nightly: if the nightly never starts at all, nothing advances and fact 1 reads `no`.
2. **Fact 3, which does touch the API, discards everything that is not finished.** The `gh` call
   takes the newest run whose `status == "completed"` out of the last 20 and reads its `conclusion`.
   A `queued` or `in_progress` run is never selected and never reported as a colour. The word
   "running" does not appear in any output of this workflow.

This phase spends no time on the orphan itself; §6c settled it.

---

## Implementation Steps

### Step 1: Create `.github/workflows/watch.yml`

**File:** `.github/workflows/watch.yml:1` (new file, whole contents)

**Change:** the watcher. One job, five steps: checkout (to read the pause switch), ensure `psql`,
gather the four facts and compose the line, publish it to the job summary, send it to Telegram.

**Code:**

```yaml
name: Daily watch

# One line a day, to the owner's phone. Four facts: session stepped, picks published, CI green,
# paper paused.
#
# WHY THIS IS NOT A STEP INSIDE nightly.yml. A step inside the nightly cannot report "the nightly
# did not run" -- if the nightly never starts, its own steps never run either. That is the single
# reason this is a separate workflow.
#
# WHY IT READS NEON AND NOT THE ACTIONS API FOR THE NIGHTLY. handover 2026-10-08 section 6c: run
# 37655513074 has been `queued` since 2026-10-07T16:54:08Z with no jobs, stuck before job creation.
# Anything reading `gh run list` naively would call it "running" forever. `paper_state`, `runs` and
# `book_targets` are the outcome, not the attempt: a run that created no job wrote no row. The one
# place this workflow does read the Actions API (CI's colour) takes only runs whose status is
# `completed`, so a queued orphan is never selected and the word "running" never appears in a line.
#
# TIMES. The owner reads WIB; every cron in this repo is UTC. WIB is UTC+7.

on:
  schedule:
    # 14:23 UTC = 21:23 WIB, every day.
    #
    # It must be able to observe the nightly's outcome, so it sits after the LAST retry slot, not
    # before. nightly.yml's slots are 06:17, 09:41 and 12:41 UTC (13:17, 16:41 and 19:41 WIB) with
    # timeout-minutes: 45, so the latest an on-time last-retry run can still be going is 13:26 UTC
    # (20:26 WIB). This is 57 minutes after that, and 1h42m after the slot itself.
    #
    # Minutes off :00 and :30 on purpose -- nightly.yml:11 records that GitHub's scheduler runs
    # hours late on those.
    #
    # Seven days a week, though the nightly is Tue-Sat UTC: on Sunday and Monday the line still
    # arrives and says the nightly was not due. Quiet-because-nothing-was-due and
    # quiet-because-it-broke must not look the same.
    - cron: '23 14 * * *'
  workflow_dispatch:

permissions:
  contents: read
  actions: read     # `gh run list` on engine-ci.yml

concurrency:
  # NOT seer-db-writer. This workflow only reads. sean.yml:8-10 records the rule: GitHub keeps one
  # pending run per group, so a watcher queued in seer-db-writer could cancel a pending nightly
  # retry. The four members of seer-db-writer stay four: nightly, backfill, repick, universe.
  #
  # cancel-in-progress: false -- the job is about 30 seconds, so queueing costs nothing, and `true`
  # would let a manual dispatch cancel the scheduled run and silently eat that day's line.
  group: seer-watch
  cancel-in-progress: false

jobs:
  watch:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      DATABASE_URL_UNPOOLED: ${{ secrets.DATABASE_URL_UNPOOLED }}
      GH_TOKEN: ${{ github.token }}
      # Deliberately NOT a failure when unset -- the compose step still runs and prints the line,
      # and the send step turns the run red with the line in the error annotation, so GitHub's
      # existing red-run email carries it. See docs/runbooks/monitoring.md (Owner steps).
      TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
      TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
      # Month and weekday abbreviations must not drift with the runner's locale.
      LC_ALL: C

    steps:
      - name: Check secrets
        run: |
          if [ -z "$DATABASE_URL_UNPOOLED" ]; then
            echo "::error::Repository secret DATABASE_URL_UNPOOLED is not set. See docs/runbooks/monitoring.md (Owner steps)."
            exit 1
          fi

      # Needed only to read PAPER_PAUSED out of .github/workflows/nightly.yml. This workflow never
      # writes that file; phase 12 of GOTRADE_FEE_REBUILD_PLAN.md owns its comment.
      - uses: actions/checkout@v4

      - name: Ensure psql
        run: |
          set -euo pipefail
          if ! command -v psql >/dev/null 2>&1; then
            sudo apt-get update -qq
            sudo apt-get install -y --no-install-recommends postgresql-client
          fi
          psql --version

      - name: Read the four facts and compose the line
        id: compose
        shell: bash
        run: |
          set -euo pipefail

          now_utc="$(date -u '+%Y-%m-%d %H:%M')"
          now_wib="$(TZ=Asia/Jakarta date '+%Y-%m-%d %H:%M')"
          day_wib="$(TZ=Asia/Jakarta date '+%a %d %b')"
          dow_utc="$(date -u '+%u')"          # 1 = Monday .. 7 = Sunday, UTC

          # ---------------------------------------------------------------- fact 4: paper paused
          # Read, never written. An unquoted, single- or double-quoted value all parse.
          pause_value="$(
            sed -n "s/^[[:space:]]*PAPER_PAUSED:[[:space:]]*['\"]\{0,1\}\([A-Za-z]*\)['\"]\{0,1\}[[:space:]]*\$/\1/p" \
              .github/workflows/nightly.yml | head -n 1
          )"
          if [ -z "$pause_value" ]; then
            echo "::error::PAPER_PAUSED was not found in .github/workflows/nightly.yml -- the watcher cannot read the pause switch, so it cannot tell a deliberate pause from a broken nightly."
            exit 1
          fi
          case "$pause_value" in
            true|True|TRUE) paused=yes ;;
            *)              paused=no  ;;
          esac

          # ------------------------------------------------------- facts 1 and 2: Neon, read-only
          # stepped_session : paper_state.last_session, the last session paper actually stepped.
          # latest_data     : runs.data_date of the newest successful real run -- the last session
          #                   whose prices the nightly used. paper/bracket.py:182 enforces
          #                   pf.last_session == data_date, so these two are directly comparable.
          # due_session     : the pending session that IS a decision session. NULL on the roughly
          #                   three weeks in four when a monthly book is only holding, and no picks
          #                   are due at all (003_paper.sql:25).
          # due_rows        : book_targets rows published for that due session.
          # last_ok_wib     : when the nightly last finished successfully, in WIB.
          read_sql="
            SELECT
              coalesce((SELECT max(last_session)::text FROM paper_state), ''),
              coalesce((SELECT max(data_date)::text FROM runs
                         WHERE status = 'success' AND NOT is_demo), ''),
              coalesce((SELECT max(pending_session)::text FROM paper_state
                         WHERE pending_decision), ''),
              (SELECT count(*) FROM book_targets
                WHERE session_date = (SELECT max(pending_session) FROM paper_state
                                       WHERE pending_decision)),
              coalesce((SELECT to_char(max(finished_at) AT TIME ZONE 'Asia/Jakarta',
                                       'YYYY-MM-DD HH24:MI')
                          FROM runs WHERE status = 'success' AND NOT is_demo), '')
          "
          row="$(psql "$DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -At -F '|' -c "$read_sql")"
          IFS='|' read -r stepped_session latest_data due_session due_rows last_ok_wib <<<"$row"
          due_rows="${due_rows:-0}"

          # ---------------------------------------------------------------------- fact 3: CI green
          # `select(.status == "completed")` is the orphan guard: a run stuck `queued` (handover
          # section 6c, run 37655513074) is never selected, so it can never be reported as a colour
          # and never as "running".
          ci_json="$(
            gh run list --workflow engine-ci.yml --branch main --limit 20 \
              --json status,conclusion,updatedAt,url \
              --jq '[.[] | select(.status == "completed")] | first' \
            || echo ''
          )"
          if [ -z "$ci_json" ] || [ "$ci_json" = "null" ]; then
            ci="?"
            ci_why="no completed run of engine-ci.yml on main in the last 20 runs"
          else
            ci_conclusion="$(jq -r '.conclusion' <<<"$ci_json")"
            ci_url="$(jq -r '.url' <<<"$ci_json")"
            ci_at="$(jq -r '.updatedAt' <<<"$ci_json")"
            ci_when="$(TZ=Asia/Jakarta date -d "$ci_at" '+%Y-%m-%d %H:%M')"
            case "$ci_conclusion" in
              success)
                ci="green"
                ci_why="the last finished run on main passed, $ci_when WIB"
                ;;
              cancelled|skipped)
                ci="?"
                ci_why="the last finished run on main was $ci_conclusion, $ci_when WIB -- $ci_url"
                ;;
              *)
                ci="RED"
                ci_why="the last finished run on main did not pass ($ci_conclusion), $ci_when WIB -- $ci_url"
                ;;
            esac
          fi

          # ------------------------------------------------------------------- facts 1 and 2: read
          if [ "$paused" = yes ]; then
            # The state today. A deliberate pause is not a failure, and must never read as one.
            stepped="n/a"
            stepped_why="paper is paused on purpose, so no session can be stepped (last stepped: ${stepped_session:-none})"
            picks="n/a"
            picks_why="paper is paused on purpose, so no picks can be published"
          elif [ "$dow_utc" -lt 2 ] || [ "$dow_utc" -gt 6 ]; then
            stepped="n/a"
            stepped_why="no nightly runs today -- the nightly runs Tue-Sat UTC, 06:17 UTC / 13:17 WIB, reading Mon-Fri's session"
            picks="n/a"
            picks_why="no nightly runs today, so nothing was due"
          else
            stepped="no"
            stepped_why="paper_state.last_session is ${stepped_session:-none}, behind the night's data at ${latest_data:-none}; the nightly last succeeded ${last_ok_wib:-never} WIB"
            if [ -n "$stepped_session" ] && [ -n "$latest_data" ]; then
              if [[ "$stepped_session" == "$latest_data" || "$stepped_session" > "$latest_data" ]]; then
                stepped="yes"
                stepped_why="paper_state.last_session is $stepped_session, level with the night's data; the nightly finished ${last_ok_wib:-unknown} WIB"
              fi
            fi

            if [ -z "$due_session" ]; then
              picks="none due"
              picks_why="no strategy has a decision session waiting -- a monthly book only decides on its own cadence, which is most days"
            elif [ "$due_rows" -gt 0 ]; then
              picks="yes"
              picks_why="$due_rows picks published for $due_session"
            else
              picks="NO"
              picks_why="a decision is due for $due_session and book_targets has no rows for it"
            fi
          fi

          if [ "$paused" = yes ]; then
            paper="PAUSED"
            paper_why="PAPER_PAUSED is 'true' in .github/workflows/nightly.yml -- deliberate, while the roster is rebuilt to pay Gotrade's real fees"
          else
            paper="live"
            paper_why="PAPER_PAUSED is '$pause_value' in .github/workflows/nightly.yml"
          fi

          # --------------------------------------------------------------- the headline, and only it
          # The first line is what a phone's lock screen shows without being unlocked, so the first
          # line carries all four facts. Everything below it is for when he opens the message.
          status="OK"
          if [ "$ci" != "green" ]; then status="CHECK"; fi
          if [ "$stepped" = "no" ];  then status="CHECK"; fi
          if [ "$picks" = "NO" ];    then status="CHECK"; fi

          headline="Seer $status | $day_wib | stepped $stepped | picks $picks | CI $ci | paper $paper"

          {
            printf '%s\n\n' "$headline"
            printf 'Session stepped: %s -- %s\n' "$stepped" "$stepped_why"
            printf 'Picks published: %s -- %s\n'  "$picks"   "$picks_why"
            printf 'CI on main: %s -- %s\n'       "$ci"      "$ci_why"
            printf 'Paper trading: %s -- %s\n'    "$paper"   "$paper_why"
            printf '\nChecked %s WIB (%s UTC). What to do: docs/runbooks/monitoring.md\n' \
              "$now_wib" "$now_utc"
          } > "$RUNNER_TEMP/body.txt"

          cat "$RUNNER_TEMP/body.txt"

          {
            echo '## Daily watch'
            echo
            echo '```'
            cat "$RUNNER_TEMP/body.txt"
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"

      - name: Send the line
        shell: bash
        run: |
          set -euo pipefail

          if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
            echo "::error::TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set, so today's line could not be delivered. Set them once -- docs/runbooks/monitoring.md (Owner steps). Today's line follows."
            cat "$RUNNER_TEMP/body.txt"
            exit 1
          fi

          # Plain text, no parse_mode: nothing in the body needs escaping and a stray character must
          # never cost the owner a day's line. --data-urlencode name@file reads the value from the
          # file, so newlines survive.
          curl -sS --fail-with-body \
            -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "disable_web_page_preview=true" \
            --data-urlencode "text@${RUNNER_TEMP}/body.txt" \
            -o "$RUNNER_TEMP/telegram.json"

          if ! jq -e '.ok == true' "$RUNNER_TEMP/telegram.json" >/dev/null; then
            echo "::error::Telegram rejected the message. Today's line follows."
            jq -r '.description // "no description"' "$RUNNER_TEMP/telegram.json"
            cat "$RUNNER_TEMP/body.txt"
            exit 1
          fi

          echo "Sent."
```

**Impact:** adds one scheduled workflow. It writes nothing anywhere — no database row, no file, no
repository state. It cannot affect the nightly: different concurrency group, read-only database
access, and it runs 1 h 42 m after the last nightly slot. Because `engine-ci.yml:10,17` triggers on
`.github/workflows/**`, committing this file will start a CI run; that run will be red for phases 1
and 2's reasons, not this one.

---

### Step 2: Create `docs/runbooks/monitoring.md`

**File:** `docs/runbooks/monitoring.md:1` (new file, whole contents)

**Change:** the runbook. What the line means, the owner's one-time setup, and what to do about each
bad fact.

**Code:**

```markdown
# Runbook — the daily line

Workflow: [`.github/workflows/watch.yml`](../../.github/workflows/watch.yml) ·
Plan: `GOTRADE_FEE_REBUILD_PLAN.md` phase 11 (R8) ·
Spec: [handover 2026-10-08](../handover/2026-10-08-sean-shipped-red-main-and-the-vanishing-picks.md) §8 Q8

One message a day, on Telegram, at **21:23 WIB (14:23 UTC)**, every day of the week.

Its **first line** carries all four facts, because that is what a phone shows on the lock screen
without being unlocked. Everything under it is for when you open the message.

```
Seer OK | Wed 08 Oct | stepped n/a | picks n/a | CI green | paper PAUSED
```

- `OK` — nothing needs you today.
- `CHECK` — one of the four facts needs you. Open the message; the reason is spelled out.

A deliberate pause is **never** `CHECK`. It is reported, every day, so you cannot forget it is on,
but it is not an alarm.

## The four facts

### 1. Session stepped

Did paper trading move forward to the night's session?

Read from Neon: `paper_state.last_session` (the last session paper actually stepped) against
`runs.data_date` of the newest successful real run (the last session the night's prices covered).
`paper/bracket.py:182` enforces that these two are the same number when paper has stepped, so
comparing them is exact and needs no market calendar.

| It says | It means |
|---|---|
| `yes` | paper is level with the night's data |
| `no` | paper is behind. Either the nightly did not run at all, or it ran and the Paper step failed. The detail line gives both dates and when the nightly last succeeded. |
| `n/a` | paper is paused, **or** no nightly was scheduled today (the nightly is Tue–Sat UTC). The detail line says which. |

### 2. Picks published

Were the picks for a waiting decision actually written?

Read from Neon: `paper_state.pending_session` where `pending_decision` is true (003_paper.sql:25 —
the flag that says this pending session *is* a decision session), and the count of `book_targets`
rows for it.

| It says | It means |
|---|---|
| `yes` | the picks are in the database, with the row count and the session |
| `none due` | **the common case.** A monthly book only decides on its own cadence; most days nothing is due. This is not a problem. |
| `NO` | a decision was due and no picks exist for it. This is the failure handover §8 Q8 describes as *"produced picks and nobody was told"*, caught from the other side. |
| `n/a` | paper is paused, or no nightly was scheduled today |

### 3. CI on main

Read from the GitHub Actions API: the newest **finished** run of `engine-ci.yml` on `main`, and its
conclusion.

"Finished" is load-bearing. Handover §6c records run `37655513074`, stuck `queued` since
2026-10-07 16:54 UTC with no jobs at all — permanently queued, before job creation. The watcher only
ever looks at runs whose status is `completed`, so a stuck run is skipped rather than reported. The
word "running" never appears in a line.

| It says | It means |
|---|---|
| `green` | the last finished run passed |
| `RED` | the last finished run failed. The link is in the detail line. |
| `?` | the last finished run was cancelled or skipped, or there is no finished run in the last 20 |

### 4. Paper trading

Read from `.github/workflows/nightly.yml`: the value of `PAPER_PAUSED`.

| It says | It means |
|---|---|
| `PAUSED` | paper is deliberately off. Facts 1 and 2 will read `n/a` and that is correct. |
| `live` | paper runs every scheduled night |

The watcher **reads** that file and never writes it. If the `PAPER_PAUSED` line ever disappears, the
watcher turns red rather than guessing — without it, it cannot tell a deliberate pause from a broken
nightly, which is the whole distinction this phase exists to make.

## Why it is its own workflow

A step inside `nightly.yml` cannot report *"the nightly did not run"*. If the nightly never starts,
its own steps never run either. That is the single reason this lives in `watch.yml`.

It also reads the **outcome** rather than the **attempt**: `paper_state`, `runs` and `book_targets`
are rows the night wrote, and a run that created no job wrote no rows. So a nightly that is disabled,
skipped by GitHub's scheduler, or stuck before job creation all show up the same honest way — fact 1
reads `no`.

## When it turns red

The watcher never turns red because a *fact* is bad. CI red, picks missing, paper behind — all of
those come through as a line that says so, in the `CHECK` state.

It turns red only when it could not do its own job:

- `PAPER_PAUSED` not found in `nightly.yml`
- `DATABASE_URL_UNPOOLED` not set, or Neon unreachable
- the Actions API unreachable
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` not set, or Telegram rejected the message

In every one of those cases the composed line is printed into the run log and into the job summary
first, and GitHub emails you about the red run. So your existing GitHub email stays meaningful: it
now means *"the watcher is broken"*, and Telegram means *"here is today"*.

## Owner steps (once)

1. In Telegram, open a chat with **@BotFather** and send `/newbot`. Give it any name, and a username
   ending in `bot`. BotFather replies with a token that looks like `123456789:AAH...`.
2. Send your new bot any message. A bot cannot start a conversation, so it must hear from you first.
3. Get your chat id:

       curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[-1].message.chat.id'

4. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**, twice:
   - `TELEGRAM_BOT_TOKEN` — the token from step 1
   - `TELEGRAM_CHAT_ID` — the number from step 3
5. **Actions → Daily watch → Run workflow**, and check the message arrives.

Until steps 1–4 are done the workflow fails every day on purpose and GitHub emails you. That
failure email carries the day's line in its run log, so you are not blind in the meantime — but it is
two taps to fix.

**Cost.** The Telegram Bot API is free. The workflow is one `ubuntu-latest` job a day, under 30
seconds; GitHub bills whole minutes, so about 30 minutes a month — 1.5% of the 2,000 free minutes a
month a private repo gets, and nothing at all on a public repo.

## When the line stops arriving at all

GitHub disables scheduled workflows in a repository with 60 days of no activity. That applies to
`watch.yml` exactly as it applies to `nightly.yml`. If the daily line goes quiet entirely, check
**Actions → Daily watch** for a banner offering to re-enable it.

## What to do about each bad fact

| Fact | What to do |
|---|---|
| `CI RED` | open the run link in the message; the failing job names itself |
| `stepped no` | **Actions → Nightly** — did it run? If it ran and went red, the Paper step's log says why. If it did not run, check the schedule is enabled. |
| `picks NO` | the night stepped but published nothing for a session that wanted a decision. The nightly run's Paper step log is where to start. |
| `paper PAUSED` | expected while the roster is rebuilt. The three resume conditions are written above the switch in `nightly.yml`. |

## Times

Every cron in this repository is UTC; you read WIB. WIB is UTC+7.

| | UTC | WIB |
|---|---|---|
| nightly, first slot | 06:17 Tue–Sat | 13:17 |
| nightly, retry | 09:41 Tue–Sat | 16:41 |
| nightly, last retry | 12:41 Tue–Sat | 19:41 |
| **daily line** | **14:23 every day** | **21:23** |

The watcher fires 1 h 42 m after the last retry slot and 57 minutes after the latest moment a
45-minute run started in that slot could still be going, so it always sees the night's final
outcome rather than a run in flight.
```

**Impact:** documentation only. Nothing reads this file programmatically.

---

## Verification

**Build (the workflow file parses as YAML):**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/watch.yml')); print('watch.yml parses')"
```

**Build (every embedded shell script is syntactically valid bash):**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
python3 - <<'PY'
import yaml, subprocess, tempfile, os, sys
wf = yaml.safe_load(open('.github/workflows/watch.yml'))
bad = 0
for step in wf['jobs']['watch']['steps']:
    script = step.get('run')
    if not script:
        continue
    with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as fh:
        fh.write(script)
        path = fh.name
    rc = subprocess.run(['bash', '-n', path]).returncode
    print(f"{step.get('name', '(unnamed)')}: {'ok' if rc == 0 else 'SYNTAX ERROR'}")
    bad |= rc
    os.unlink(path)
sys.exit(1 if bad else 0)
PY
```

**Tests (the tree is unchanged, so both suites must still be exactly as this phase found them):**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
cd web && npx vitest run && npx tsc --noEmit
```

This phase adds no Python and no TypeScript, so neither suite's result may move. `main` is red for
phases 1 and 2's two reasons (plan index, *Critical context*); those failures must be the **same**
failures before and after this commit. Note `PYTHONPATH` is required — without it pytest silently
tests the main checkout instead of this branch.

**Manual check 1 — run the composed script locally, against the real Neon and the real Actions API,
with Telegram deliberately unconfigured.** This exercises every read and prints the exact line that
would be sent:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
export RUNNER_TEMP="$(mktemp -d)"
export GITHUB_STEP_SUMMARY="$RUNNER_TEMP/summary.md"
export LC_ALL=C
export DATABASE_URL_UNPOOLED="<the Neon unpooled URL>"
export GH_TOKEN="$(gh auth token)"
python3 - <<'PY' > "$RUNNER_TEMP/compose.sh"
import yaml
wf = yaml.safe_load(open('.github/workflows/watch.yml'))
for step in wf['jobs']['watch']['steps']:
    if step.get('id') == 'compose':
        print(step['run'])
PY
bash "$RUNNER_TEMP/compose.sh"
```

Expected today (2026-10-08, paper paused, `main` red), with the dates read live:

```
Seer CHECK | Wed 08 Oct | stepped n/a | picks n/a | CI RED | paper PAUSED

Session stepped: n/a -- paper is paused on purpose, so no session can be stepped (last stepped: 2026-10-06)
Picks published: n/a -- paper is paused on purpose, so no picks can be published
CI on main: RED -- the last finished run on main did not pass (failure), <time> WIB -- <url>
Paper trading: PAUSED -- PAPER_PAUSED is 'true' in .github/workflows/nightly.yml -- deliberate, while the roster is rebuilt to pay Gotrade's real fees
```

`stepped n/a` with `last stepped: 2026-10-06` is the measured state the phase brief records
(`paper_state.last_session` = 2026-10-06, zero sessions stepped). `CI RED` is the watcher working:
phases 1 and 2 turn it green.

**Manual check 2 — the paused branch is not the only branch that works.** Re-run manual check 1 with
the pause switch temporarily flipped in a scratch copy, so the Tue–Sat branch is exercised. Do not
commit the flip (invariant 2):

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
cp .github/workflows/nightly.yml "$RUNNER_TEMP/nightly.yml.bak"
sed -i "s/^      PAPER_PAUSED: 'true'/      PAPER_PAUSED: 'false'/" .github/workflows/nightly.yml
bash "$RUNNER_TEMP/compose.sh"
cp "$RUNNER_TEMP/nightly.yml.bak" .github/workflows/nightly.yml
git diff --exit-code .github/workflows/nightly.yml && echo "nightly.yml restored, byte for byte"
```

The line must then read `stepped no` (because `paper_state.last_session` 2026-10-06 is behind the
night's data) on a Tue–Sat UTC day, and `stepped n/a -- no nightly runs today` on a Sunday or Monday
UTC. The final `git diff --exit-code` is the proof `nightly.yml` was not touched.

**Manual check 3 — the orphan does not fool it.** Confirm the CI read skips the permanently-queued
run:

```
gh run list --workflow engine-ci.yml --branch main --limit 20 \
  --json status,conclusion,updatedAt,url \
  --jq '[.[] | select(.status == "completed")] | first'
```

and, separately, that the stuck nightly run is invisible to every query the watcher makes:

```
gh run view 37655513074 --json status,conclusion,jobs --jq '{status, conclusion, jobs: (.jobs | length)}'
```

Expected: `status: "queued"`, `jobs: 0`. The watcher makes no call that would select it.

**Manual check 4 — after merge to `main` only.** A scheduled workflow only runs from the default
branch, and `workflow_dispatch` only appears in the UI once the file is on the default branch. So
after merge: **Actions → Daily watch → Run workflow**, and confirm the Telegram message arrives with
the headline on its first line. If the two secrets are not yet set, confirm instead that the run is
red and that its log contains the full line — that is the designed fallback, not a defect.

**Already exercised while planning — do not take these on trust, but they were measured, not
estimated.** The YAML parses, all four `run:` blocks pass `bash -n`, and the compose step was run
with `psql`, `gh` and `date` stubbed to drive every branch. Six cases, all producing correct plain
English:

| Case | Headline produced |
|---|---|
| A — paused (the real `nightly.yml`, today) | `Seer CHECK \| stepped n/a \| picks n/a \| CI RED \| paper PAUSED` |
| B — live, paper behind, 80 picks published | `Seer CHECK \| stepped no \| picks yes \| CI RED \| paper live` |
| C — live, level, no decision due | `Seer OK \| stepped yes \| picks none due \| CI green \| paper live` |
| D — live, decision due, zero picks (the Q8 failure) | `Seer CHECK \| stepped yes \| picks NO \| CI green \| paper live` |
| E — live, Sunday UTC, no nightly scheduled | `Seer OK \| stepped n/a \| picks n/a \| CI green \| paper live` |
| F — `PAPER_PAUSED` line deleted from `nightly.yml` | no line; `::error::` and exit 1, as designed |

In A, B and E the scratch copy of `nightly.yml` was restored and `git diff --exit-code` confirmed it
byte for byte. The headline is 73 characters in case A, which fits a phone lock screen without
truncation.

**Exit criteria:**

1. `.github/workflows/watch.yml` exists, parses as YAML, and every `run:` block passes `bash -n`.
2. Its `concurrency.group` is `seer-watch`, and `seer-db-writer` appears in the file only inside the
   comment that explains why it is not used:

       python3 -c "import yaml; print(yaml.safe_load(open('.github/workflows/watch.yml'))['concurrency'])"

   must print `{'group': 'seer-watch', 'cancel-in-progress': False}`.
3. Its schedule is `'23 14 * * *'`, and the file states 21:23 WIB beside 14:23 UTC.
4. Running the compose step locally prints a first line carrying all four facts, today reading
   `CHECK | stepped n/a | picks n/a | CI RED | paper PAUSED`.
5. `git diff --name-only` for this commit lists exactly two files: `.github/workflows/watch.yml` and
   `docs/runbooks/monitoring.md`.
6. `docs/runbooks/monitoring.md` gives the two secrets, the five setup steps, and the WIB/UTC table.
7. No query in the workflow can select a run whose `status` is not `completed`:
   `grep -c 'status == "completed"' .github/workflows/watch.yml` returns `1`. The only occurrences of
   the word "running" in the file are in the comment explaining why it is never emitted; no `printf`
   or `ci_why` string contains it.
8. Both suites report the same results as before the commit.

## Handoffs

- **Phase 1 (R6) — CI green.** This watcher *reports* CI's colour and fixes nothing. It will say
  `CI RED` every day until phases 1 and 2 land. That is the watcher working, not a defect in it.
- **Phase 12 (R1) — `nightly.yml` and `paper-trading.md`.** `docs/runbooks/paper-trading.md:76`
  states a schedule that no longer exists (`cron 23:00 UTC Mon-Fri (06:00 WIB)` against the real
  `17 6 * * 2-6` = 13:17 WIB) and is the documentary cause of one false alarm. **I did not fix it**;
  phase 12 owns that file. `docs/runbooks/monitoring.md` states the correct schedule independently
  and does not copy the stale line, so the two documents will disagree until phase 12 lands. Phase 12
  should also consider adding a one-line pointer from `paper-trading.md`'s *The night* section to
  `monitoring.md`.
- **Phase 9 (R5) — the same four facts on the site. SETTLED by the reconciler, 2026-10-08: keep
  `none due` and `PAUSED` exactly as chosen here.** Phase 9 reports stepped / published / failed /
  paused to the owner *on the site*; this phase pushes them to him *without him looking*. Both
  planners asked to be aligned with the other, so the reconciler read both and found they already
  agree on the two words that matter:

  | the fact | this phase's daily line | phase 9's panel |
  |---|---|---|
  | holding, nothing was due | `picks none due` | title *"Nothing was due for &lt;date&gt;"* |
  | paper is paused | `paper PAUSED` | banner *"Paper trading is paused"* |

  The registers differ on purpose — one line on a phone against a sentence on a page — and neither
  side's code depends on the other (different runtimes; a workflow cannot import TypeScript). The
  agreement that is enforced is the **words the owner reads** (invariant 7). If either surface is
  reworded later, reword both.
- **`PAPER_PAUSED`, four phases, checked compatible.** This phase `sed`s the value out of
  `nightly.yml`; **phase 9** mirrors it into `web/lib/decision.ts` and reads the same line back with
  `/^\s*PAPER_PAUSED: '(true|false)'/m` in a drift test; **phase 12** rewrites only the comment block
  **above** it (`:46-69`); and **no phase edits the `PAPER_PAUSED:` line itself** (invariant 2).
  Phase 12's plan now carries an explicit constraint that the line's exact text and indentation
  survive, because this phase's `sed` pattern and phase 9's regex both key on them. Case F of this
  phase's **Test matrix** (the line deleted from `nightly.yml`) is the guard on this phase's side.
- **`docs/ROADMAP.md:122`** reads *"Notifications (e.g. Telegram) for picks and day-5 exits"* under
  *Later (v0.2+)*. This phase delivers the Telegram channel, so that line is now half done. No phase
  in this set owns `ROADMAP.md`, so I left it alone rather than taking a drive-by edit; whoever
  updates the roadmap next should note that the transport exists and only the picks/exits payload
  remains.
- **Deliberately not built:** per-fact alerting thresholds, a history of past lines, retries on a
  Telegram outage, and a second channel. The user asked for one line a day explicitly in preference
  to a dashboard; each of those is the first step back toward one.

## Assumptions

- Nothing from `depends_on` — this phase has none, and quotes every file exactly as it stands at
  `485d416`.
- `psql`, `gh`, `jq` and `curl` are on `ubuntu-latest`. `gh`, `jq` and `curl` are guaranteed by
  GitHub's runner image; `psql` is normally present but the *Ensure psql* step installs
  `postgresql-client` if it is not, so the workflow does not depend on an assumption I cannot measure
  from here.
- `DATABASE_URL_UNPOOLED` is already a repository secret — every other workflow in this repo uses it
  (`nightly.yml:42`, `backfill.yml:39`, `repick.yml:27`, `universe.yml:21`, `sean.yml:31`), so this
  phase adds no database configuration, only the two Telegram secrets.
- The Neon connection string carries its own `sslmode`, as the engine's own `psycopg` connections
  rely on; `psql` honours the same URL.

## Rollback

`git revert` the single commit. Both files are new, so the revert deletes them and nothing else
changes — no database row, no migration, no engine or web code, no other workflow. The watcher
writes nothing anywhere, so there is no state to unwind.

After reverting, optionally delete the two repository secrets (**Settings → Secrets and variables →
Actions**) and, in Telegram, send `/deletebot` to @BotFather. Neither is required: an unused token is
inert.

This phase is independently revertible and is listed as such in the plan index's *Rollback* section.
