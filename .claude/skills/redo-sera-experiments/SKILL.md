---
name: redo-sera-experiments
description: Use when the owner wants one or more existing Seer lab methods redone the way he really trades — "/redo-sera-experiments M0022,M0020,M0019", "/redo-sera-experiments https://seertrade.site/sera/methods/M0007", "redo these methods with the real Gotrade fees", "redo my roster methods realistically", "re-run M0022,M0020,M0019 with real fees and the monthly top-up", "purge M0007 and run it again properly", "these results don't represent how I actually trade". Takes a comma-separated list of method ids or seertrade.site method URLs, mints one pre-registered variation twin per method at Gotrade's real fees in fractional shares on the owner's real monthly top-up, and reports the whole batch beside the parents.
---

# Redo Sera experiments, honestly

## What you get

You asked for your methods' results to represent how you really trade: Gotrade's real fees,
fractional shares, and the 5,000,000 rupiah you add every month. **That is what this skill
produces**, for one method or for a list of them. It runs each one again under all three, and shows
the new numbers next to the old ones so you can see exactly what the realism cost.

The one thing it does **not** do is delete the old experiments. Three plain reasons:

1. **The old numbers are not wrong — they are a record of a different question.** They answer "what
   would this idea have done paying a tenth of a percent a trade, buying whole shares, on money that
   never grew". That is a real answer to a question you no longer care about. Keeping it is what
   lets us say what the realism cost, which is the interesting part.
2. **Deleting experiments would make every other result look better than it is.** The lab discounts
   every method for how many ideas we have tried — try enough things and something looks good by
   luck alone. Throw away a past try and that discount shrinks, so every *other* method's score
   quietly goes up without anyone having learned anything. That is the exact trick on ourselves the
   whole scoring system exists to stop. Deleting the embarrassing one is how people end up believing
   a strategy that does not work.
3. **The database will not let us.** The trials and methods tables are append-only: deleting a row
   is blocked by the schema itself (`trials_no_delete`, `trials_no_update`, `methods_no_delete`).
   That is not a setting someone forgot to turn off; it is the point.

So instead of deleting, we add: a **twin** per method. A twin is a new method that is the old one
with the realism switched on, registered before it runs, and judged on its own. The lab's own cost
report says this in so many words — "the only way a real-fee configuration is judged is a new method
that pre-registers it" (`lab/real_costs.py`) — and `sera-the-explorer` already requires it: *promote
the twin, never the original*.

**And the twins barely move anyone else's score.** The discount counts *distinct ideas*, not
individual settings, so a batch of three adds **three** to the count — one per idea — not one for
every setting each twin tries. Your objection that redoing a method rearranges everyone else's luck
was correct about the old counting, and the counting was fixed; it is no longer a reason not to redo
a method, or a reason to redo them one timid batch at a time. Read the live count and the live bar
off `lab status` and quote those, never numbers typed from memory.

## Three iron rules

The same three the other lab skills carry. Breaking the letter of a rule breaks its spirit too.

1. **We never stop trying, we never give up.** A twin that loses is a result, and a good one: it
   tells you the idea only worked because the fees were pretend. Journal it and queue what to try
   next. **One method's failure never stops the batch** — journal it, record the skip, move to the
   next. A batch that queues nothing is the only real failure.
2. **No human in the loop.** Decide everything yourself. Never `AskUserQuestion`, never end a turn
   on a question, never wait for approval — not for which variant to twin, not for a failing check,
   not for a push. Write down what you assumed, in the analysis or the commit message. The only
   allowed stop is terminal (missing tooling you cannot build, a permission you do not have): report
   it and end, never hold a prompt open.
3. **We never fool ourselves.** Every twin is registered *before* it runs, by committing its file.
   Every trial counts. Nothing is deleted, nothing is edited, and no number is compared to a bar
   from a different day.

## Invocation

```
/redo-sera-experiments M0022,M0020,M0019
/redo-sera-experiments M0022, M0020, M0019
/redo-sera-experiments https://seertrade.site/sera/methods/M0007
/redo-sera-experiments M0022,https://seertrade.site/sera/methods/M0020,M0007-N20-RAW
/redo-sera-experiments M0007
```

A single method is just the one-item batch. There is no separate path for it, and nothing below
behaves differently.

**Parse per item, not across the whole string**, so a candidate id keeps its variant suffix:

```bash
ARGS="$*"
printf '%s' "$ARGS" | tr ',' '\n' | tr -s ' \t' '\n' | sed '/^$/d' > /tmp/redo-items.txt
```

For each line: the parent is the first `M` followed by exactly four digits; the pinned variant, if
any, is the longer candidate id in the same item.

```bash
MNNNN=$(printf '%s' "$ITEM"  | grep -oE 'M[0-9]{4}' | head -1)
VARIANT=$(printf '%s' "$ITEM" | grep -oE 'M[0-9]{4}-[A-Z0-9-]+' | head -1)   # may be empty
```

That one rule covers every form above — bare ids, full URLs, candidate ids, commas with or without
spaces, and any mix in one invocation. **Dedupe by parent id, keeping the first occurrence** (and
its variant) so `M0007,M0007-N20-RAW` is one item, not two.

**The URL is never fetched.** The site is behind the Sera gate and the repo holds everything the
page is built from — the same rule `update-stale-sera-methods-page` follows.

### Refuse per item, never per batch

A bad item must not discard the batch. Check each, record the reason, **continue**:

- `lab show $MNNNN` prints `no method …` → the lab has no such method. Skip it, with that reason.
- the id starts with `H-` → the P7a seed import has no method file, so `lab run` can never target
  it. There is nothing to redo. Skip it, with that reason.
- the item contains no `M` plus four digits → not a method id at all. Skip it, with that reason.

Print the resolved plan before doing any work — the parents you will twin, in order, and every item
you are skipping with its reason — then start. Never ask whether to proceed.

## Fixed facts

```
REPO=/home/miftah/seer                             # the main checkout: work here, not a worktree
PY=$REPO/engine/.venv/bin/python                   # the only venv
LAB="$PY -m seer_engine lab"
STORE=$REPO/engine/.research                       # the dev research store: NOT in any worktree
METHODS=$REPO/engine/src/seer_engine/lab/methods   # where each twin's file goes
MARKER="redo-sera-experiments:"                    # the source_ref prefix every twin carries
```

**One session, in the main checkout, one method at a time.** Do **not** fan out into worktrees the
way `sera-the-explorer` does. Four reasons, and each is on its own enough:

1. `lab run` needs the research store, and the store is gitignored and lives only here. There is
   nothing per-method to isolate: every twin reads the same store.
2. Only `lab stage` may commit the lab database, and it takes the write lock. A binary file written
   by two sessions is a conflict nobody can merge, which is exactly why Sera makes herself the only
   committer. Parallel twins would still have to funnel through one committer — this session — so the
   parallelism buys nothing and adds a lock to contend for. `lab run` serialises at the database
   anyway.
3. `lab run` refuses an uncommitted method file by running `git status` in the *method file's own
   directory*, and it finds that directory through whichever `seer_engine` is importable. Here the
   venv and the sources are the same tree, so the two always agree. In a worktree they agree only
   while `PYTHONPATH` is exported in every single shell, and one forgotten export means `lab run`
   either refuses a file you did commit or silently runs the main checkout's copy.
4. A redo is minutes per method, mechanical, with no research between items. Sera parallelises
   because each of her children is a full research session; these are not.

The isolation that matters here is **per item, not per process**: see The batch loop.

The checkout may still be shared with other sessions, so:

- **Commit by explicit pathspec.** Never `git add -A`. Never `git reset --hard`.
- **Never `git checkout`, `git restore` or `git stash` `lab/lab.sqlite`.** It is a binary another
  session may be mid-write in. Bringing the checkout back to clean is a `pull`, never a restore.
- **Only `lab stage` commits `lab/lab.sqlite`, and every such commit also includes
  `web/data/lab.json`.** CI fails a database commit without its snapshot, and the site redeploys
  from each push.
- **Every `lab` subcommand migrates the database on connect, so even a read dirties the file.** When
  you need a column no command prints, open the database read-only instead (see the report step).

## 0. Preflight, once for the batch

```bash
cd $REPO
git pull --rebase --autostash
$LAB status                         # the live count, the live luck bar, the test looks used
cd engine && $PY -m pytest -q tests/test_lab_*.py; cd $REPO
```

`tests/test_lab_snapshot.py` fails whenever `lab/lab.sqlite` has changed without a `lab stage` — for
example **after an earlier batch of this skill was interrupted before it published**. If that is the
only failure, run `lab stage`, commit `lab/lab.sqlite` and `web/data/lab.json`, push, and re-run the
tests. Always test *after* staging, never before. This is the repair step for an interrupted batch,
so do it before anything else rather than working on top of an unpublished database.

If `$STORE` is missing, build it (`$PY -m seer_engine research_store`, a few minutes) or pull it with
`/sync-research-store`. Never point `--store` into a worktree: there is no store there, and a rebuild
is half an hour for nothing.

## 1. Classify every item, once, before touching anything

For each parent on the list, find out where it already stands. This is both the dedupe the owner
asked for and the resume for an interrupted batch — the state *is* the database and git, so there is
no progress file to keep and none to go stale.

```bash
$PY - <<PY
import sqlite3
c = sqlite3.connect("file:$REPO/lab/lab.sqlite?mode=ro", uri=True); c.row_factory = sqlite3.Row
for parent in """$PARENTS""".split():
    tw = c.execute(
        "SELECT id, status FROM methods WHERE parent_id = ? AND source_kind = 'variation' "
        "AND source_ref LIKE '$MARKER%'", (parent,)).fetchone()
    if tw is None:
        print(parent, "S0-not-started"); continue
    n = c.execute("SELECT count(*) FROM trials WHERE method_id = ?", (tw["id"],)).fetchone()[0]
    print(parent, tw["id"], tw["status"], "trials", n)
PY
```

| State | What you see | What to do |
|---|---|---|
| **S0 not started** | no twin row for this parent | the whole cycle below |
| **S1 reserved, no file** | a twin row, status `idea`, and no method file for its id | reuse that id and its hypothesis; **skip the reservation**; write the file and carry on |
| **S2 file written, uncommitted** | the file exists but `git status --porcelain -- <file>` is non-empty | commit it — that is its pre-registration — and carry on |
| **S3 committed, not run** | the file is clean and tracked, and the twin has no trials | run it and carry on |
| **S4 done** | the twin's status is `rejected` or `dev-eligible` and it has trials | nothing. Report it as already done |

**The marker is what makes this correct.** Many parents already have variations that are *not* this
skill's twins — the lab holds two dozen methods with a parent — so matching on "is a variation of
this parent" alone would wrongly skip methods that have never been redone. Every twin this skill
mints carries the marker prefix in its `source_ref`, and only that prefix counts.

**Never re-mint a twin that is S4, and never delete and redo one.** A pre-registration deleted and
written again is a hypothesis written after seeing a number, which is the one thing the lab exists to
prevent. If a twin was run and the owner wants a *different* realistic configuration, that is a new
variation of the twin, with its own hypothesis — not a redo of the redo.

## 2. The batch loop — one method at a time, failures contained

Work through the list in the order given. **Wrap each item.** Any failure inside one item — a cost
report that says stop, a refused run, a contract test that will not pass, an exception — is caught,
journaled, recorded as a skipped row with its reason, and then the loop moves to the next item. Never
let one method end the batch, and never leave a half-written method file behind: if an item fails
before its commit, delete its file so the next invocation sees a clean S1 rather than a puzzling S2.

### 2a. Read the parent

```bash
$LAB show $MNNNN
```

Note its status, family, source and parent; **its best recorded dev trial by MAR** — that is the
variant to twin, unless the item pinned a candidate id, in which case twin that one; and that
trial's CAGR vs SPY TR, max drawdown, profit factor, trades, DSR, the `N=` it was scored at, and
which conditions it `failed`.

That `N=` is the count on the trial's **run date**, not today's. Never compare a recorded DSR to
today's bar; `lab luck` re-scores every recorded DSR at today's count and that is the only number
worth quoting beside a twin's. Then read the parent's `TradeRules` preset out of its method file in
`$METHODS`.

### 2b. Two per-item refusals, both final, both non-fatal to the batch

**a. The parent is already fractional and already at Gotrade's real fees.** Then the only thing a
twin would change is the monthly top-up — and the funding is **not** part of what makes a
configuration distinct, permanently and by design: a configuration's identity is its rules,
allocator and parameters, and old methods keep their digests so that dedupe against every recorded
trial keeps working. Funding is a property of the lab's era, not of a configuration. So a verbatim
re-run is *the same configuration* and `lab run` refuses it
(`<id> repeats <id>, which already ran on the dev window`).

Do **not** nudge a parameter to make the configuration look different: that is a new method wearing
a redo's clothes, and it spends a new idea on a question nobody asked. Instead: say plainly that this
method is already measured at real fees in fractional shares, quote where it stands under today's
counting from `lab status` / `lab luck`, journal that as an observation, record the skip, and go to
the next item.

No method in the lab trips this today — the fractional ones still pay the old flat fee, so both dials
still move. It becomes live the moment this skill has run, because a twin *is* fractional at
Gotrade's fees: the realistic case is someone pasting a twin's id into a later batch instead of its
parent's. Which is exactly why this is a skip, not an abort.

**b. The parent's edge does not survive real fees.** For a parent numbered **M0030 or earlier** —
every one of which was measured at the lab's old flat assumption of a tenth of a percent a trade —
run the cost report *before* reserving anything for it:

```bash
$LAB costs $MNNNN                   # add --candidate <the pinned variant> when the item named one
```

A report, never a trial: no row is written, the lab's count does not move, no test-window look is
spent, and it journals one observation by itself. It re-runs the parent's best dev variant twice — at
the flat cost and at Gotrade's real schedule — and prints both side by side. If the real fees take
the variant below SPY, or break a go-live condition it used to clear, **a twin is not worth
minting**: the idea only worked because the fees were pretend, which is itself the answer the owner
came for. Make sure the journal says that in plain words, record the skip with its reason, and go to
the next item. This mirrors the rule `sera-the-explorer` already applies before reserving a variation
of a near miss.

Reserving nothing until both checks pass is deliberate: there is then no idea row to drop and no id
burned on an item that was never going to run.

### 2c. Reserve this twin

Skip this if the item is **S1** — reuse the id and hypothesis already reserved.

```bash
$LAB idea \
  --name "<the parent's idea, in fractional shares at Gotrade's real fees, on the monthly top-up>" \
  --family "<the parent's family, verbatim>" \
  --source-kind variation \
  --parent $MNNNN \
  --source-ref "redo-sera-experiments: <the parent's best variant id> on monthly-hold-frac-gotrade, funded monthly" \
  --hypothesis "<see below>"
```

The flag is `--parent`, not `--parent-id`. The command prints the new id — call it `$TWIN`.
(`lab next-id` tells you the next free one, but `lab idea` assigns it; never type an id.)

**`source_ref` must begin with the marker** `redo-sera-experiments:`. That prefix is how a later
batch knows this parent has already been redone *by this skill*, as opposed to merely having some
variation. Get it wrong and the next invocation mints a duplicate twin.

**The hypothesis is the pre-registration, so it must state the realism explicitly**, in three parts
written before any result exists:

1. that it runs **fractional**, so every slot is actually bought rather than left in cash;
2. that it pays **Gotrade's real fee schedule** (`cost_model="gotrade"`) — the one fitted to the
   owner's own order receipts — not the lab's old flat assumption;
3. that it is judged on the **owner's real funding plan**, 5,000,000 IDR arriving on the 25th of
   every month on top of the opening book, against a SPY fed the identical dollars on the identical
   days.

Then say what you expect: which of the parent's numbers should survive the realism and which should
not, and why. Name the parent's recorded figures so the comparison is pinned before the run. Write a
fresh hypothesis per twin — do not paste one item's across the batch; the parents differ and so do
the reasons.

`expected_failure` goes in the method file next, and is written now, not after.

**Do not stage or commit the database here.** The batch publishes once, at the end.

### 2d. Write this twin's method file

```bash
cp $METHODS/m0029_blend_fractional.py $METHODS/m<twin digits>_<slug>.py
```

`m0029_blend_fractional.py` is the worked precedent and the shortest honest twin in the tree: it
imports its parent's params helper and the shared allocator, swaps only `rules`, and declares one
candidate. Copy it and change the parent it imports from. Only if the parent's allocator genuinely
cannot be reused do you start from
`.claude/skills/explore-and-experiment-new-method/method_template.py` instead.

Rules for the file:

- **The module number must equal `METHOD.id`** (`m0032_*.py` ↔ `id="M0032"`), or `discover()` raises
  — and it raises for the *whole lab*, which would break every later item in the batch. Get this
  right before running anything.
- `source_kind="variation"`, `parent_id=$MNNNN`, `family` = the parent's family verbatim, and
  `source_ref` = **the same marker-prefixed string you reserved with**.
- `hypothesis` = what you reserved. `expected_failure` = the way it most likely fails, written now.
- **`rules` must be a real-fee fractional preset**: `sim.rules.MONTHLY_HOLD_FRAC_GOTRADE`, or
  `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` when the parent reranks monthly and resizes weekly, or
  `replace(<the parent's book preset>, fractional=True, cost_model="gotrade")` for any other cadence.
  **This is enforced, not requested.** `lab/real_costs.py:real_cost_problem` refuses to run any
  method numbered M0031 or later with a variant that is not a `book` rule set at
  `cost_model="gotrade"`, and `runner.preflight` raises it before any data is loaded. Every twin you
  mint is numbered above that line, so a flat-fee twin cannot run at all.
  *A `replace(...)` preset runs fine on dev, but `lab promote` needs a preset with its own id — if
  such a twin wins, queue a `feature-wish` insight for one.*
- **As few variants as the question needs — ideally one.** The point of a twin is to isolate the
  realism, and one variant adds one trial. Changing a second dial makes the twin a different idea and
  you can no longer tell which change moved the number. In a batch this compounds: the owner wants to
  read one row per method, not a grid.
- `seen_keys` must be unique per twin (something like `concept:<the parent's concept>-frac-gotrade`),
  or the second twin in the batch collides with the first.
- Pure: no clock, no randomness, no files, no network, no printing. Reads only bars dated
  ≤ `data_date`.

Check it, then lint:

```bash
cd $REPO/engine && $PY -m pytest -q tests/test_lab_methods.py && $PY -m ruff check src tests
cd $REPO
```

The contract test covers **every** method file, so a green run here also proves this twin has not
broken any earlier item's file. If it fails, fix this method. **Never weaken the test.** If it cannot
be made to pass, delete this twin's file, record the skip with the reason, and move to the next item —
leaving a broken file in place would fail every later item too.

### 2e. Commit this twin's file — this is its pre-registration

```bash
git add -- engine/src/seer_engine/lab/methods/m<twin digits>_<slug>.py
git commit -m "lab: $TWIN, the real-fee fractional twin of $MNNNN (pre-registration)"
```

**`lab run` refuses an uncommitted, modified or untracked method file** and says so:
`Commit the method file first: the commit is its pre-registration`. It checks with `git status` in the
file's own directory, so a staged-but-uncommitted file is refused too. This is not a formality and
not optional: the commit is what makes the hypothesis unchangeable before the numbers exist. Do not
skip ahead, do not batch these commits together at the end, and never pass `require_commit=False`
from a script.

One commit per twin, not one for the batch. Each hypothesis is then frozen at its own timestamp,
before its own run, which is the audit record the lab is for. Push at the end of the batch, or now if
you prefer — either is fine for the method files; only the database commit has to be last.

### 2f. Run it

```bash
$LAB run $TWIN --store $STORE
```

Seconds to minutes. Use `run_in_background` and wait for it. It prints each variant's line and marks
an `ELIGIBLE` trial. One `lab run` per method, ever — a method runs once.

Because the runner funds the book, the trial is scored on the owner's real funding plan: the
money-weighted return of the book against the money-weighted return of a SPY fed the identical
dollars on the identical days. That is what "beats SPY" means for a funded trial, and it is the
number to lead with.

If the run fails, record the skip with the reason and move on. The method file stays committed and
the item is **S3** for the next invocation, which will simply run it — nothing to clean up.

### 2g. Write this twin's own analysis

Each twin gets its own note; the batch report later is a summary, not a substitute.

```bash
$LAB note $TWIN --file /tmp/twin-$TWIN.md \
  --verdict "<one or two sentences: what the realism cost, and where this twin stands under today's bars>"
```

The analysis is what the owner reads on that method's page, and he is not a trader or a statistician.
Short sentences, everyday words, every number with its meaning ("lost at most 13% from a peak, inside
the limit"), and a plain gloss on any term you cannot avoid. Cover:

- what the realism cost, as the headline: fees, fractional fills, and the top-up
- **the money-weighted result against the SPY fed the same deposits** — in plain words, "what your
  money actually earned, against putting the same deposits into the market instead". This leads,
  because it is the only like-for-like comparison a funded run has
- **a sentence saying the total and yearly figures are not returns here.** With deposits, they are
  the shape of the curve and mostly your own money arriving; the engine leaves them that way on
  purpose. Never quote them beside the parent's as if they were the same measurement — the same rule
  as the batch report, and it applies just as much on a single method's page
- which conditions it misses and by how much
- how likely the result is real rather than luck after this many distinct ideas, with the count and
  the bar as `lab status` prints them today — and, for a funded run, the caveat that this is worked
  out from day-to-day account changes and the deposit days look like big up days. If it comes out
  surprisingly strong, say so and journal a `risk` insight
- the worst year and when the worst fall happened, noting that deposits make a fall look shallower
- **why** — the mechanism, not just the numbers
- whether the hypothesis held and whether the expected failure happened
- a closing paragraph starting **`My opinion:`** that commits to a view on whether this direction
  deserves more trials. No hedging.

Then go to the next item.

## 3. Journal and queue

Once the loop is done:

```bash
# one per batch of two or more: this becomes the site's headline
$LAB insight --kind synthesis --title "<the batch's theme, in plain words>" --file /tmp/batch.md
# plus at least one next idea, drawn from what the batch taught
$LAB idea --name "…" --family "…" --source-kind variation --parent <the most promising twin> --hypothesis "…"
```

For a **single-method** invocation use `--kind observation --method $TWIN` instead: a synthesis is a
batch summary, and the explore skill reserves it for exactly that.

The newest synthesis is the headline of seertrade.site/sera — the first thing the owner reads — and
he is not a trader. So: everyday words; name methods by what they do ("the residual-momentum book"),
never by their ids; no code, file paths, column names, hashes or backticks; spell out jargon ("worst
fall", not "max DD"; "gains against losses", not "PF"); and a number earns its place only with its
meaning. Cover what the realism cost across the batch, which ideas survived it and which only ever
worked on pretend fees, what that says about where to search next, and what the deposits changed
about how the results read.

**In the synthesis, quote only what the money earned** — the money-weighted rate against a SPY fed
the same deposits. Never quote a funded twin's total or yearly figure here: with deposits those are
mostly the owner's own money arriving, and on the site's headline, stripped of the table's labels,
such a number reads as performance. One sentence explaining that the twins are measured on what the
money earned, because money kept going in, is worth more to him than any figure.

**State no bar and no limit as a number, anywhere in the synthesis** — not "the limit is 20%", not
"we require 0.90". A guard checks the newest synthesis against the live bars precisely because a
sentence like that was still the site's headline after the owner moved a bar. Say "inside the limit"
or "short of the bar" and let the page show the number.

Ids and mechanics belong in each twin's analysis, which is the audit record.

## 4. Publish — once, at the end

```bash
$LAB stage
git add -- lab/lab.sqlite web/data/lab.json
git commit -m "lab: <N> real-fee fractional twins of <the parents> — <one-line outcome>"
git -c rebase.autoStash=true pull --rebase origin main
git push
cd $REPO/engine && $PY -m pytest -q; cd $REPO
```

**Once for the batch, not once per method.** The site gets one coherent redeploy instead of several,
the owner reads a finished batch rather than watching it assemble, and the lab database is a binary —
one staged commit is one chance of colliding with a parallel session instead of several, and one blob
in history for one logical change.

**Do this on any orderly exit**: a completed batch, a batch where every item was skipped and only
refusals were journaled, or an early stop. It is the batch's last step in every case, never only the
happy one.

The cost of publishing once is that a **hard** kill before this point leaves the working-tree
database holding rows that are not published: the snapshot is stale and `tests/test_lab_snapshot.py`
is red until someone stages. That is repaired by this skill's own preflight, which stages before
doing anything else. It does not affect resuming: step 1 reads the **live** database file, which is
on disk whether or not it has been committed, so where the batch got to is never lost — only its
publication is deferred.

`lab stage` takes the database's write lock, regenerates `web/data/lab.json` and `git add`s both
files. Never `git add lab/lab.sqlite` by hand, and never commit it without the snapshot. Vercel
redeploys the site from the push, with no other step.

If any twin came out **dev-eligible**, do not promote it. Promotion spends the one counted
test-window look and belongs to `/explore-and-experiment-new-method`'s Promotion section, or to Sera:
say in the report which twins are eligible and name the command. Spending a look is not this skill's
job, and spending several in a batch is how a test window gets burned in an afternoon.

## 5. The batch report

Read everything back, then write one table.

```bash
$LAB luck --limit 0                 # read-only: every recorded DSR re-scored at today's count
for T in $TWINS; do $LAB show $T; done
```

`lab show` does not print the money-weighted numbers and neither does the published snapshot. Read
them for the whole batch in one **read-only** query, so the database is not migrated and dirtied by
the read:

```bash
$PY - <<PY
import sqlite3
c = sqlite3.connect("file:$REPO/lab/lab.sqlite?mode=ro", uri=True); c.row_factory = sqlite3.Row
for r in c.execute(
    "SELECT t.method_id, t.candidate_id, f.mwr, f.spy_tr_mwr, f.deposits_usd, f.deposits_n "
    "FROM trials t JOIN trial_funding f ON f.trial_n = t.n "
    "WHERE t.window = 'dev' ORDER BY t.n"):
    print(dict(r))
PY
```

A twin with no row there received no deposits — the normal, definite answer for every trial recorded
before the runner was funded, not a missing value. Say so rather than leaving a blank.

### The one thing you must not get wrong in this report

**A twin's return and its parent's return must never share a column.** They are not the same
measurement.

The twin got deposits; the parent did not. So the twin's "total return" counts the money you put in
as if it were money you made. This is not a rounding difference — on a real funded run the engine
reports a total return of **+1078%** and a true earned rate of **7.6%** for the *same* run. Almost
all of that +1078% is your own deposits piling up. The engine says so itself: with deposits, total
return and yearly return "are **not returns at all** — they are the recorded shape of the curve".

So:

- **Never** put the parent's return and the twin's return in one column.
- The twin's total return and yearly return go in **their own labelled cells**, and the parent's
  equivalent cells stay **blank**, with the one-word reason *unfunded*.
- **The headline for every twin is the like-for-like pair**: what the twin's money actually earned,
  against a SPY given the exact same deposits on the exact same days. Both sides got the same money
  at the same time, so that comparison is honest and it is the only one that is.

Say it to the owner in his own words, early in the report, something like:

> Two different questions. The twin's number answers *"what rate did my money actually earn, given I
> kept adding to it every month"*. The old number answers *"what would one lump sum have grown to"*.
> The first is the one that describes how you really trade — so that is the one in the big column,
> and it is measured against putting those same monthly deposits into the market instead.

Three more cells deserve care, for the same reason:

- **worst fall** — deposits keep topping the account up, so a fall looks shallower than it was.
  Report the twin's, say deposits soften it, and do not line it up against the parent's.
- **how likely it is real** (the luck score) — for a funded run this is worked out from day-to-day
  changes in the account, and the days you deposited look like enormous up days. Report what the lab
  recorded, never call it comparable to the parent's, and if a twin's luck score comes out
  surprisingly strong, say so plainly and journal it with `lab insight --kind risk`. A number that
  flatters us is the one to distrust first.
- **gains against losses** and **trades** are fair to compare, with one caveat worth a sentence: the
  book is bigger later on, so later trades count for more.

### The table

**One row per method**, like-for-like columns first, the deposit-inflated ones last and labelled:

| method (what it does) | twin | verdict | what your money earned | the same deposits into the market instead | gains against losses | trades | worst fall (deposits soften this) | how likely it is real | the shape of the curve, mostly deposits |
|---|---|---|---|---|---|---|---|---|---|
| the twin | | | **the headline** | **the honest comparison** | | | | recorded | total and yearly, labelled |
| its parent, at real fees (from the cost report) | — | — | *unfunded* | *unfunded* | | | | recorded | |
| its parent, as recorded on pretend fees | — | — | *unfunded* | *unfunded* | | | | re-scored by `lab luck` | |

Three rows per method, not two, for the *other* reason the comparison can go wrong: the parent's
recorded numbers paid a tenth of a percent a trade, so the twin is compared against the parent's
**cost-report** row, and the recorded row is shown only as history. **Never compare a twin's numbers
to a parent's recorded numbers as if the fees were the same.** Between the two traps — different
fees, and different measures — every cell in this table has to be one or the other, deliberately.

Then, below the table, **one line per skipped method with its reason** — "already measured at real
fees, so there is nothing to redo", "the real fees wipe out its edge, so a twin is not worth
running", "the lab has no such method". A skip is a result and the owner should see it, not have to
notice its absence.

Read the luck bar and the count from `lab status` or `lab luck` and quote those. **Never type a bar or
a count into this file, the report, a synthesis or an analysis** — they are the owner's dials, they
move, and a typed number goes stale the next time they do.

Write the report in everyday words: no backticks, no column names, no ids in the prose. Finish with
the count and the looks as `lab status` prints them, which twins are eligible and what command would
spend a look on one, and the next idea you queued. **No question at the end.**

## Never

| Temptation | Rule |
|---|---|
| "He said purge them, so purge them" | Never. The schema refuses it, and deleting a past try raises every other method's score for free — the exact self-deception the scoring exists to stop. Mint the twins and explain the refusal in his words, early, before he has to ask. |
| "One id in the list is bad, so stop and ask" | Never. Skip that item with its reason and run the rest. A bad id costs one row of the report, not the batch. |
| "This method's run failed, abandon the batch" | Never. Journal it, record the skip, go to the next. A failure never pauses the others. |
| "Fan the batch out into worktrees like Sera does" | No. The research store is not in worktrees, only one session may commit the database, and the commit check runs in the method file's own directory. Serial in the main checkout avoids all three. |
| "Commit all the method files together at the end" | Never. Each commit is that twin's pre-registration and `lab run` refuses an uncommitted file. One commit per twin, before its own run. |
| "`lab stage` after each method so the site keeps up" | No. Once at the end: one redeploy, one binary commit, one coherent story. Stage on any exit, not only on success. |
| "This parent already has a twin row, skip it" | Only if the row carries this skill's marker in its source reference. Two dozen methods have some variation; that is not the same as having been redone. |
| "Delete the twin and redo it, the first run was bad" | Never. A pre-registration deleted and rewritten is a hypothesis written after seeing a number. A different configuration is a new variation of the twin, with its own hypothesis. |
| "Re-run the parent under the new funding" | A method runs once, and funding is permanently not part of what makes a configuration distinct, so the re-run is the same configuration and is refused. If the parent is already fractional at real fees, there is nothing to redo: say so, skip it, continue. |
| "The digest collides; nudge a parameter so it doesn't" | Never. That is a different method pretending to be a redo, and it spends an idea on a question nobody asked. |
| "`lab costs` showed it survives real fees, so it is fine now" | `lab costs` is a report, not a trial. Only the twin can be judged at real fees. |
| "Compare a twin to its parent's recorded numbers" | Not as like for like. The recorded numbers paid a tenth of a percent a trade. Compare against the parent's cost-report row; show the recorded row as history. |
| "Simplify the report: one return column for twin and parent" | **Never.** The twin got deposits and the parent did not, so its total return counts money you paid in as money you made — measured, +1078% against a true earned rate of 7.6% on the same run. One shared column turns that into a lie the owner cannot see. Separate columns, the parent's cell blank and marked unfunded. |
| "The twin returned +1078%, lead with that" | That is not a return. With deposits, total and yearly figures are the shape of the curve — the engine says so and leaves them that way deliberately. Lead with what the money earned, against a SPY fed the same deposits. |
| "The twin's luck score beats its parent's" | You cannot say that. For a funded run the luck score comes from day-to-day account changes, and deposit days look like huge up days. Report it, never compare it, and journal a risk insight if it looks surprisingly strong. |
| "Its worst fall improved on the parent's" | Not necessarily. Deposits keep topping the account up, which makes a fall look shallower. Report it, say that, do not line it up against an unfunded parent's. |
| "Six variants each, to find the best realistic version" | A twin isolates the realism. One variant. More dials and you cannot tell which change moved the number — and the owner wants one row per method, not a grid. |
| "Build it on the plain fractional preset, the fees are close enough" | `lab run` refuses it outright above M0030. The owner pays real fees; a method that only wins at the old assumption does not win. |
| "Write the luck bar into this file so the reader knows it" | Never type a bar or a count anywhere — not in prose, not in a transcript, not in a synthesis. They are the owner's dials and they move. Read them from `lab status`. |
| "`git add -A`, it's quicker" | Never. The checkout is shared; you would commit another session's work in progress. |
| "`git add lab/lab.sqlite`" | Always `lab stage`. It is the only thing that keeps the published snapshot in sync, and CI fails a lab commit without it. |
| "The lab database looks dirty, restore it" | Never `checkout`, `restore` or `stash` it. It is a binary another session may be mid-write in. Come back to clean with a `pull`. |
| "Three twins are eligible — promote them" | Not here, and especially not three. Promotion spends the one counted look per method and belongs to the explore skill or to Sera. |
| "Ask which variant to twin" | You don't. Take each parent's best recorded dev trial by MAR, or the candidate id he pasted. Write the assumption down and continue. |
| "Nothing in the batch survived the fees, stop here" | That *is* the answer he came for, and for a whole batch it is a strong one. Journal it plainly, queue the next idea, report it as a finding. |

## Quick reference

```
lab show M0007                 # a parent, its trials, its verdict (method id only, not a candidate id)
lab status                     # the live count, the live bar, test looks used
lab luck --limit 0             # read-only: every recorded DSR re-scored at today's count
lab costs M0007 [--candidate M0007-N20-RAW]
                               # report only: flat fees vs Gotrade's real ones; journals it, nothing spent
lab idea --name … --family … --source-kind variation --parent M0007 \
         --source-ref "redo-sera-experiments: …" --hypothesis …        # prints the new id
lab run M0032 --store /home/miftah/seer/engine/.research               # needs a committed file
lab note M0032 --file /tmp/twin-M0032.md --verdict "…"
lab insight --kind synthesis --title … --file /tmp/batch.md            # a batch; observation for a single method
lab stage                      # once, at the end: writes the snapshot, git-adds it and the database
```
