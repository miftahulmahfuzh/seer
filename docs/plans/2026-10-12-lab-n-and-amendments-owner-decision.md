# Two decisions for the owner — 2026-10-12

**Status:** open. Nothing in this document has been decided, and nothing in the code has been
changed because of it.
**Written by:** the brakes-and-gate plan set, as its last phase.
**Asks for:** two answers. They are independent — either can be answered without the other.

This memo carries the two things that work could not settle for itself.

The first is a number the lab has been printing to you incorrectly since 8 October. It is the
single number you use to judge whether a new idea is worth trying, and it is wrong by a factor
of about five.

The second is a rule the lab lived by until today and does not any more. It was changed on your
own instruction, and the change bought something real. It also gave something up, quietly, and
you have not yet been asked whether that is a trade you want.

Neither has been acted on beyond writing it down. The first is laid out with its options and no
recommendation. The second is laid out with its gap and a question.

---

## Decision A — the hurdle the lab prints is not the hurdle it applies

### What you see

Every lab command signs off with a line telling you how big the luck hurdle is. Today it says
**354**.

### What the lab actually does

It uses **74**.

The two numbers answer different questions. 354 is how many backtests the lab has ever run on
the development window. 74 is how many separate *ideas* those backtests came from. On 8 October
the hurdle was changed to count ideas instead of backtests — that was the right change and it is
in force. The printed line was not changed with it. It has been reporting the old number for
four days.

### Why it matters

The hurdle is the price of looking. Every new thing you try makes it harder for everything else
to clear the bar, and the size of that penalty is the whole reason the lab counts.

- A **brand-new idea** looks, from the printed line, like it adds roughly one part in three
  hundred and fifty. It actually adds one part in seventy-four. It is about five times more
  expensive than the screen says.
- A **new version of an idea the lab already holds** looks, from the printed line, like it costs
  exactly the same as a new idea. It costs **nothing at all**. The hurdle does not move.

So the screen has been telling you that exploring broadly is cheap and that refining what you
have is expensive, when the truth is the reverse. That is backwards in the exact direction that
costs the most: it encourages the one activity the lab's own evidence says is least likely to
find anything new.

### The three options

These are the three the previous session named. They are reproduced as it stated them, and this
document deliberately does not choose between them.

1. **Print both numbers.** The hurdle and the backtest count, side by side, labelled so the
   difference is visible. Nothing is hidden; the line gets longer and you read two numbers where
   you used to read one.
2. **Print the hurdle, and label the backtest count separately.** The prominent number becomes
   the one that is actually applied; the row count keeps a place but stops being called the
   hurdle.
3. **Leave the screen alone and fix only the wording in the documents.** The printed number keeps
   meaning what it has always meant, and the papers around it stop calling it the hurdle. This has
   already been done to the documents (see below); choosing this option means stopping there.

### Why nothing was changed

The previous session's stated reason, kept as written: altering what you read is a decision about
your own mental model, not a wording fix, and it touches a command surface that several runbooks
quote.

A check on 2026-10-12, run on this branch after this batch of work had written its own planning
notes, found the exact printed phrase in thirty-two files — but twenty-eight of those are the
lab's own working notes, which nobody reads and which go stale on purpose. The documents that
would actually have to be corrected are **four**: none of them in the runbooks folder, three
elsewhere in the documents folder, and one — the engine's own package notes, where the phrase
appears twice. So the "several runbooks" part is not right; the blast radius is smaller than it
was described as being. It is still more than one place, and it is still your call, which is why
this memo exists rather than a patch.

This plan set's own reason for not touching it is simpler: you said so. The instruction that
opened this work was "do not act on it — that is the owner's decision, not yours. Surface it, do
not fix it."

### What has already been corrected

Only documents, and only to stop them calling the backtest count "the lab's N". That landed on
12 October as a documents-only change. No command, no screen and no stored number moved.

### One command already prints it the clear way, so you can see what that reads like

This same batch of work added one new lab command — the one that prices the market switch across
the books. It is new, so it had no printed line to inherit, and rather than copy the wording this
decision is about, it signs off with two numbers under two labels: the hurdle called the hurdle,
and the backtest count called the backtest count.

That is **option 1 above, demonstrated once**, on a surface nothing else depends on. It is put
here as evidence, not as a recommendation: you can run that command, see the shape of the line,
and decide whether you want the other ten to read that way. **None of the ten was touched** — the
instruction that opened this work was to surface them, not to fix them, and they are exactly as
they were.

> **For the implementer.** The new command is `lab gate` (`_gate` in
> `engine/src/seer_engine/commands/lab.py`, lab-brakes-and-gate phase 2). Its closing `print`
> reads `Luck hurdle N: <store.gate(conn).n> (policy <...>)` and `Dev trial rows: <before> before,
> <after> after`. It deliberately contains no instance of the string `Lab N (dev trials)`, and
> phase 2's own test asserts that. `grep -c 'Lab N (dev trials)'` on that file still returns
> **10**, both at base commit `d3c1ec4` and after this whole plan set lands.

> **For the implementer — the technical detail behind Decision A.** This block exists so the
> change can be made without re-deriving anything. It is not part of the prose above.
>
> Ten printed lines in `engine/src/seer_engine/commands/lab.py` read
> `Lab N (dev trials) is now <count>` or `… is still <count>`:
>
> ```
> engine/src/seer_engine/commands/lab.py:1399, 1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287
> ```
>
> Those line numbers are at base commit `d3c1ec4`. The brakes-and-gate work shifts them (it adds a
> flag to one subparser and a whole new subcommand to the same file) without editing any of the
> ten; `grep -n` on whatever branch does the work gives the current positions, and `grep -c` still
> gives ten.
>
> The count is `store.dev_trial_count(conn)`. The gate's N is `store.gate(conn).n`, resolved by
> `npolicy.effective_n` under `store.DSR_POLICY = "methods"`.
>
> Measured 2026-10-12 on a copy of the committed `lab/lab.sqlite` (md5 `4a34ddb8…`; the original
> was not opened, because a lab command migrates the file on connect):
>
> ```
> store.gate(conn)                    -> Gate(n=74, policy='methods')
> store.dev_trial_count(conn)         -> 354 dev trial rows
> npolicy.dev_method_count(conn)      -> 74 distinct methods with a dev trial
> store.pending_gate(conn,'M0030',3)  -> Gate(n=74)    a variant of an existing method: free
> store.pending_gate(conn,'M9999',1)  -> Gate(n=75)    a new method id: +1, retroactively,
>                                                       for all 130 recorded method rows
> ```
>
> The documents-only correction is commit `e9715b2`: `lab/exposure.py`'s module docstring, and
> the exposure plan's invariant 3 and Reconciliation Log C8.
>
> Whoever acts on option 1 or 2 should expect to touch `engine/package_readme.md` (two hits) in
> the same change, and should not expect to touch `docs/runbooks/` (zero hits, verified
> 2026-10-12).

---

## Decision B — a method may now be amended, and nothing charges for it

### What changed

Until today a method in the lab ran **once**. Once it had a result, its file was frozen: if you
wanted to try a different setting of the same idea, you opened a new method, and the new method
cost you a point of hurdle.

As of this plan set, a method that has already run can be given a **new, separately dated block
of extra versions to try**, written down before they are run, and recorded against the method it
belongs to rather than against a new one. Everything else about pre-registration is unchanged:
the block is committed to the repository before anything runs, it carries its own hypothesis and
its own stated expected failure, and nothing that has already been recorded can be edited.

### Why it was done

Because of Decision A's number, read the other way round.

Under the hurdle the lab has applied since 8 October, a new method id costs **+1** — and that
penalty applies backwards, to every one of the 130 methods already on file, making each of them
very slightly harder to believe. A new version of a method that already exists costs **zero**.
Measured on 12 October: adding versions to the two methods this plan set is working on leaves the
hurdle at 74; opening one new method id would move it to 75.

You made that the hard constraint on this work — the new versions had to be versions of the
existing methods, not new methods. The old freeze made that impossible to express, so the freeze
had to grow a door.

It is worth saying plainly that the freeze was not written for the world it now lives in. When
"a change is a new method" was written down, the hurdle counted individual backtests, and a new
method with six versions cost six. Under today's hurdle it costs one. The rule was calibrated
against a price that no longer exists.

### What still guards it

Four things, and they are the reason this is a door rather than a hole.

1. **Nothing recorded is rewritten.** The original record of what a method was when it first ran
   is untouched and still enforced by the database itself. An amendment adds a row; it never
   edits one.
2. **Each amendment is pre-registered in its own right.** Its own date, its own written
   hypothesis, its own stated expected failure, committed before it runs. The commit is the
   pre-registration, exactly as before.
3. **Every version already on file still has to match what the lab holds for it, exactly.** If an
   amendment changed anything about an old version — even by accident — the check fails. This is
   a stronger test than the one it replaces, not a weaker one.
4. **Tuning after seeing a result is still forbidden.** The amendment must be written before the
   run, not after reading it. That rule did not move.

### The gap, stated plainly

The hurdle's own protection against one idea being pushed indefinitely is a floor: the hurdle can
never fall below how many genuinely independent results the lab's own curves show it has.

Measured on 12 October, that floor is **3**, against a hurdle of **74**.

It does not bind. It is nowhere near binding, and nothing else charges for an amendment. So the
honest statement is this: **a method could be amended again and again, indefinitely, and the
hurdle would stay at 74 the whole time.** Each amendment is free. There is no cap and no counter.

That is a real way to fool yourself, and it is the same shape as the thing this lab was built to
prevent — enough attempts at one idea will eventually produce a good-looking number, and if
nothing counts the attempts, nothing deflates the number.

This plan set did not invent a limit. Choosing "three amendments per method" or "six" or "the
hurdle counts amendments too" is picking a number that changes what every future result means,
and that is your call, not a planner's.

### The question

Pick one, or say something else:

- Should a method's amendments be **capped**, and if so at what — a lifetime limit on amendments,
  or a lifetime limit on total versions across all of them?
- Should the hurdle **count amendments as looks**, so that each one costs what it costs?
- Or is the floor described above the **intended and sufficient** answer — the lab already prices
  a family of versions of one idea at zero on purpose, and an amendment is simply another member
  of that family?

Until this is answered, the amendment door is open and uncounted. That is the state of things as
of 12 October, written down rather than left to be discovered.

> **For the implementer — the technical detail behind Decision B.** Not part of the prose above.
>
> The mechanism: a `Method` may carry one or more `Amendment` blocks, each with its own date,
> hypothesis, expected failure and 1..6 `Candidate`s; `lab run --amend MNNNN` executes an
> amendment's never-run digests and records the trials under the existing `method_id`.
> `methods.source_sha` is never rewritten and the trigger `methods_source_sha_once` stays in
> place; each amendment appends a row to the append-only `method_amendments` table carrying its
> own source hash, date and git sha. The freeze test becomes two checks — the file hashes to the
> latest recorded amendment's sha, **and** every recorded candidate still digests to the
> `config_digest` the lab holds.
>
> The refusal that was qualified is `runner.preflight`
> (`engine/src/seer_engine/lab/runner.py:174-178`):
> `"{method.id} is already {status}: a method runs once. A change is a new variation method
> (source_kind='variation', parent_id=...)"`.
>
> The gap, precisely: under `DSR_POLICY = "methods"`,
> `npolicy.effective_n` resolves `n = max(dev_method_count, ceil(participation_ratio))`.
> Measured 2026-10-12 on a copy of the committed database (md5 `4a34ddb8…`):
>
> ```
> dev_method_count      -> 74
> participation_ratio   -> 2.1946   -> ceil = 3
> n = max(74, 3)        -> 74       NCount.floored is False: the floor does not bind
> mean pairwise corr    -> 0.648 over 354 curves on 102 common month-ends
> ```
>
> `pending_gate(conn, '<an existing method>', k)` returns `Gate(74)` for every `k`, so no number
> of amendments moves N. This is the index's Decision D8.

---

## How every number here was measured

Every figure in this document is dated and says what it was measured on. That is deliberate: the
session before this one spent its time correcting measured numbers that had been written down as
permanent facts and then quietly went stale.

- All hurdle, backtest-count and method-count figures: **2026-10-12**, on a byte-identical copy of
  the committed lab database, with the original left unopened and unchanged.
- The ten printed lines and their positions: **2026-10-12**, on this plan set's base commit.
- The count of documents quoting the printed phrase: **2026-10-12**, a search across the whole
  repository, on this branch rather than on its base. That figure moves every time any batch of
  work writes a planning note, which is why the count of durable documents is the one quoted
  above; the same search at this work's base commit found twenty-one files.
- Nothing here was measured against the test window, and no test-window look was spent.

If you are reading this more than a few weeks after it was written, re-measure before acting on
any number in it.
