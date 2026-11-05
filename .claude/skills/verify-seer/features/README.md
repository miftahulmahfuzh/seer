# Seer feature map

What Seer does, from the owner's side, and what proves each feature works. One file per feature,
each with the same four sections: `Sub-features`, `How to get to it (user POV)`,
`Driving it with verify.sh`, `Gotchas`. A plan's **Proof** section cites entries by file name.
`V=.claude/skills/verify-seer/scripts/verify.sh` throughout. Every journey here is offline (no paid
call) unless the table says so.

| Feature | File | Surfaces | Paid calls |
| --- | --- | --- | --- |
| Today: tonight's order tickets, the no-buys state, the day-5 reminder | [today.md](today.md) | web, ui | none |
| Positions and History: each strategy's book, closed trades, activity | [positions-history.md](positions-history.md) | web, shoot | none |
| Leaderboard: equity vs SPY, go-live checklist, engine `compare` | [leaderboard.md](leaderboard.md) | web, engine | none |
| Sera: the lab site (overview, methods, journal unread badges) | [sera.md](sera.md) | web, api, sql | none |
| Sean: real-money P&L, trades, receipt upload, the plan's to-do list | [sean.md](sean.md) | web, ui, api, sql | none (the vision read is never enabled) |
| The night: migrate, nightly, paper (Claude twins included), paper_check | [engine-night.md](engine-night.md) | engine | `--net` opt-in (free tiers) |
| The lab CLI: status, show, next-id, idea, refusals | [lab-cli.md](lab-cli.md) | lab, labsql | none |

Add an entry when a change ships a new user-facing feature; fix an entry when the app's behavior
changed on purpose. A journey that fails because the app is broken is a product bug: report it,
do not edit the entry to match.
