---
name: sync-research-store
description: Use when the Seer research store must move between machines — "sync the research store", "pull the store on my GPD", "push the store from the Lenovo", "my other laptop has no store", "did the store change", "lab run says the store is missing", "do I need to rebuild the store here" — or before running `lab run` on a second machine. Copies `engine/.research/` through Vercel Blob, content-addressed on the manifest fingerprint, instead of rebuilding it from Neon (~30 min + a yfinance crawl).
---

# Sync the research store between machines

`engine/.research/` is the **train/eval input**: `lab run` reads it and never opens Neon. It is
gitignored, and rebuilding it costs ~30 minutes and a full yfinance crawl. On a second laptop,
copying it is strictly better than rebuilding — and a copy is *bit-identical*, which a rebuild
is not, because yfinance answers differently from one day to the next.

That last point is the real reason this skill exists. Two laptops that each rebuild their own
store get two different fingerprints, and the fingerprint is part of what a recorded lab trial
was measured against. Copying keeps one store, one fingerprint, one history.

```bash
S="$(git rev-parse --show-toplevel)/.claude/skills/sync-research-store/sync_store.py"
python3 $S status      # what is here, what is remote, are they the same
python3 $S push        # publish this machine's store
python3 $S pull        # install the remote store here
python3 $S list        # versions held remotely
python3 $S prune       # drop all but the newest 3
```

Run it from anywhere inside the repo; it resolves the main checkout itself with
`git rev-parse --git-common-dir`, so a worktree is fine.

## Setup, once per machine

The script travels with the repo, so a `git pull` is enough to get it. The **token does not**:
`.env.local` is gitignored (`.gitignore:2`), so each machine needs that one line copied by hand.
`.env.local-train` (`.gitignore:38`) is the same deal for the local train/eval database.

The script needs `BLOB_READ_WRITE_TOKEN`. Seer's `.env.local` does **not** carry one yet (the
token in the `reap-orphaned-blobs` skill belongs to a different project, so do not reuse it).

1. Create or pick a Blob store in the Vercel dashboard for the Seer project (Storage → Blob).
2. Copy its read-write token.
3. Append it to the repo-root `.env.local` on **both** laptops:

   ```
   BLOB_READ_WRITE_TOKEN=vercel_blob_rw_...
   ```

The script reads the environment first, then `.env.local`. **Never `source .env.local`** —
`DATABASE_URL` in that file contains an unquoted `&`.

## Why the fingerprint is the whole design

`manifest.json` carries a per-file sha256 map and a `fingerprint` over it, and
`research.load_store` verifies both before the lab will use a store. This skill makes that
identity the unit of transfer:

- **Blob key is the fingerprint** (`seer/research-store/<fingerprint>.tar.gz`), plus a small
  `LATEST.json` pointer saying which one is current, when it was pushed, and from which host.
- **`push` of an unchanged store is a no-op.** Same fingerprint as the pointer → skipped.
- **`pull` of a store you already have is a no-op.** Same reason.
- **A corrupt download cannot be installed.** Every file's sha256 is recomputed after
  extraction and the fingerprint must match the pointer, or nothing is written.

## The four refusals

Each is a real way to lose work rather than copy it:

| Refusal | Why |
|---|---|
| `push` when the local store fails verification | publishing a broken store would propagate it to the other laptop |
| `pull` when this machine holds a **different** store | it would be discarded silently. `push` yours first, or pass `--force` |
| `pull` when the download's fingerprint ≠ the pointer's | a truncated or tampered archive; nothing is installed |
| extracting an archive member with a path, symlink or hardlink | a tar that writes outside the staging directory |

`pull` is also **atomic**: it extracts to `.research.incoming-<pid>`, verifies *there*, and only
then swaps the directory into place, keeping the old one until the swap succeeds. A half-written
store is worse than no store, because `lab run` would happily read it.

## Typical two-laptop flow

On the machine that just built or refreshed the store:

```bash
python3 $S push
```

On the other one:

```bash
python3 $S status    # confirms the remote is ahead
python3 $S pull
```

Then `lab run` works there with no rebuild and no database access at all.

## Storage budget

A store is roughly 100–300 MB compressed, and `push` keeps the newest **3** versions by default
(`--keep N`, or `--keep 0` to never prune). Three versions of a 250 MB store is 750 MB, which is
most of a 1 GB Blob allowance — so prune rather than accumulate, and treat `list` as the thing
to check before wondering where the quota went.

## What this does NOT sync

- **Neon.** Production is untouched; this is machine-local train/eval state only.
- **`fundamental_facts` or `bars` in a database.** Only the store's CSVs travel. If you want a
  *fresher* store rather than the same one, rebuild it from the database on one laptop
  (`python -m seer_engine research_store --with-fundamentals`) and `push` that.
- **Recorded lab trials.** Those live in the repo and move by git, as they should.

## When a rebuild is the right answer instead

Pull when you want the *same* store. Rebuild when you want a *newer* one — after a
`fundamentals` or `nightly` run has added data worth picking up. The tell is
`status`: if both machines agree and you still want new data, the answer is a rebuild on one
machine followed by a `push`, not a `pull`.

**A rebuild that changes prices is refused by `lab run`** (trial-reproducibility, decision D10 in
`lab/hardgate.py`). `lab run` compares the store's *price* fingerprint — the four price files,
`fundamentals.csv` left out — with the one the lab's `REF-SPY-HOLD` benchmark trial recorded, and
refuses before any backtest when they differ. A fundamentals-only refresh
(`--refresh-fundamentals`) leaves the price files alone, so it is safe to push; a full rebuild
re-fetches prices and is not a way to bring newer data into the lab. Moving the lab's prices is a
change argued in git (a new benchmark trial and an edit to D10), not a store push.
