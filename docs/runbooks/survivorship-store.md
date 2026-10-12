# Runbook — the survivorship-check store

The dev store (`engine/.research`) can price only about half of the companies that were ever in
the index, and the ones it misses are mostly the ones that died. The **survivorship-check store**
(`engine/.research-sv`) is the dev store plus EODHD prices for most of those missing members.
`lab survivorship MNNNN` re-runs a method's recorded dev variants on both stores and prints them
side by side. It is a cross-check, not a gate: `lab run`, `lab test` and `lab remeasure` refuse
the store, and `lab promote` never reads it.

Both stores and the EODHD cache are gitignored and live **only in the main checkout**:

| what | path | variable that points a worktree at it |
|---|---|---|
| dev store | `/home/miftah/seer/engine/.research` | `SEER_RESEARCH_STORE` |
| survivorship-check store | `/home/miftah/seer/engine/.research-sv` | `SEER_SV_STORE` |
| EODHD cache | `/home/miftah/seer/engine/.cache/eodhd` | `SEER_EODHD_CACHE` |
| lab database | `/home/miftah/seer/lab/lab.sqlite` | `SEER_LAB_DB` |
| EODHD token | `/home/miftah/seer/.env.local` (`EODHD_API_TOKEN`) | `SEER_ENV_FILE` |

## Run the check from a worktree

```bash
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
       SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
       SEER_SV_STORE=/home/miftah/seer/engine/.research-sv
engine/.venv/bin/python -m seer_engine lab survivorship M0117 --no-journal   # report only, writes nothing
engine/.venv/bin/python -m seer_engine lab survivorship M0117                # also journals one observation
```

Without `SEER_SV_STORE`, a worktree's default points at its own missing `engine/.research-sv`,
and the command refuses with exit 2 and names the variable.

## Rebuild the store (offline)

Rebuild after the dev store's **prices** change: a new `research_store` build that moves its price
fingerprint, or new alias data. A change to `fundamentals.csv` or `market_series.csv` alone does
not move the price fingerprint. The build copies those files from the source byte for byte, so
rebuild after such a change too if the two stores' files should match.

```bash
PY=engine/.venv/bin/python   # from any checkout with its own venv
$PY -m seer_engine survivorship_store --report --out /home/miftah/seer/engine/.research-sv   # coverage now
$PY -m seer_engine survivorship_store \
    --out /home/miftah/seer/engine/.research-sv \
    --source /home/miftah/seer/engine/.research \
    --cache /home/miftah/seer/engine/.cache/eodhd           # preview: prints coverage, writes nothing
$PY -m seer_engine survivorship_store --build \
    --out /home/miftah/seer/engine/.research-sv \
    --source /home/miftah/seer/engine/.research \
    --cache /home/miftah/seer/engine/.cache/eodhd           # writes <out>.tmp, swaps it in whole
```

Use absolute paths and never a symlink for `--out`, because the swap would replace the
directory the link names. The build refuses an `--out` that is the source, the dev store or the
test store, or that holds a store with another purpose. On any failure the store on disk is left
exactly as it was. Backups go **outside** the repo (`/home/miftah/seer-backups/`), since only
`.research-sv/`, `.research-sv.tmp/` and `.research-sv.old/` are gitignored.

## Top up from EODHD (network) — before 2026-11-10

The EODHD key is valid until **2026-11-10**. After that date nothing new can be fetched, and the
cache on this PC is the only copy. Copy `engine/.cache/eodhd/` by hand to any other machine that
needs to build the store (see the `sync-research-store` skill).

```bash
export SEER_ENV_FILE=/home/miftah/seer/.env.local     # EODHD_API_TOKEN
$PY -m seer_engine --dry-run survivorship_store --fetch-aliases \
    --source /home/miftah/seer/engine/.research --cache /home/miftah/seer/engine/.cache/eodhd   # counts codes, fetches nothing
$PY -m seer_engine survivorship_store --fetch-aliases \
    --source /home/miftah/seer/engine/.research --cache /home/miftah/seer/engine/.cache/eodhd   # resumable; exit 1 = rerun
```

`--fetch-aliases` is the command's only network path. For every unserved member, it probes up to
four other EODHD codes the company may have traded under, using the delisted and live symbol
lists. It writes only under `<cache>/alias/` and skips codes already cached unless `--refetch`
is passed. Then rebuild (above).

**Nothing else is worth fetching for the members still unserved.** The primary `eod/` cache
already holds a file for every one of the 522 symbols the dev store cannot price. The rest fall
into three groups:
- EODHD has no series under any code we can match. The alias probe already searched for these.
- The ticker was reused by a later company, and no alias fits. Better matching here would be a
  change to the resolver in `survivorship_alias.py`, not more data.
- The dev store has bars but none on a member day. That is a dev-store question.

Re-fetching delisted history returns the same frozen bars.

## Coverage record

| when | symbols served | member-days covered 1996-2015 | aliases accepted / targeted | source price fingerprint |
|---|---|---|---|---|
| 2026-10-10 build | 989 / 1061 | 58.6% -> 89.0% | 128 / 200 | `5451195f…` |
| 2026-10-12 top-up + rebuild | 989 / 1061 | 58.6% -> 89.0% | 128 / 200 | `5451195f…` |

2026-10-12 alias fetch: 0 calls, 0 members accepted, 128 already cached, 0 failed (the dry run
found 0 codes left to probe). The rebuild reproduced the 2026-10-10 store exactly: same manifest
fingerprint (`9de54476…`), same files, same coverage, and `market_series.csv` (with the 5,722
`T13W` rows the cash-interest lever reads) byte-identical to the dev store's.
Backup of the 2026-10-10 store: `/home/miftah/seer-backups/research-sv.bak-20261012`.
