# Sean

## Sub-features

- Overview: real profit and loss after fees, split into realized and unrealized, fees paid.
- Trades: every Gotrade order read from an Order Summary screenshot. Upload (drop screenshots or a zip) goes to `POST /api/sean/orders`. Delete an order (server action, dispatches `sean.yml`).
- Plan: follows one roster method and turns its picks into a to-do list ("Buy about $71.48 of KMI"). "Mark done", claim shares as your own, plan settings.

## How to get to it (user POV)

The wallet icon in the rail ("Sean, your real trades · 3 to do"), then the Overview / Trades / Plan sections.

## Driving it with verify.sh

```sh
$V up
$V api RUN GET /sean            # "Up $200.04 since Jun 2025", "$5.84 Fees paid On 24 orders"
$V api RUN GET /sean/trades     # "24 orders", "17 buys and 7 sales between Jun 11, 2025 and Nov 3, 2026"
$V api RUN GET /sean/plan       # "Following F4", "3 things to do", "Buy about $71.48 of KMI ..."

$V upload RUN some.png          # HTTP 502 {"error":"Sean's reader isn't set up yet. Nothing was saved."}
$V sql RUN "select count(*) from sean_orders"        # still 24
# zz-next.log after down: "sean: LLM_API_KEY, LLM_VISION_BASE_URL or LLM_VISION_MODEL is not set"
#                         "sean: screenshot not kept <sha> GITHUB_DISPATCH_TOKEN is not set"

$V ui RUN .claude/skills/verify-seer/features/steps/plan-mark-done.mjs --width 390
                                # "clicking: Mark done: Buy about $71.48 of KMI", result: PASS (3 -> 2 things to do)
$V sql RUN "select symbol, action from sean_reminder_marks order by symbol"   # HBAN | buy (seeded), KMI | buy (yours)
```

## Gotchas

- **A successful upload cannot be produced locally, by design.** The route saves an order only after the screenshot is committed to the `sean-receipts` GitHub branch (the only copy of the owner's receipts), and that write is pinned off. The vision LLM is never enabled either: it would bill and still end in 502 "not kept". Prove upload changes with `npm test` (`lib/sean/*.test.ts`) plus the offline 502 end state above, and say so.
- Any PNG or JPEG works for the offline journey: the route refuses before the bytes matter. A body whose sha256 does not match answers 400.
- Delete and "Refresh P&L" dispatch `sean.yml`. Offline they log "sean dispatch skipped" and the row change is still provable.
