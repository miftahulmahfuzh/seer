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
