# The journal content digest — how to recompute it

An integrity anchor nobody can reproduce is not an anchor. This records the exact recipe
behind the number quoted during the 2026-10-20 journal-versioning work, after a later
session tried about fifteen plausible variants and could not reproduce it.

## What it is for

`insights` is append-only, and since schema 8 one column (`supersedes`) can move, once,
from NULL. Every other field of every existing row must stay frozen. This digest is how a
change proves it froze them: compute before, compute after, compare.

## The recipe

```python
import sqlite3, hashlib

c = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)
rows = c.execute(
    "select id,kind,title,body,method_id,added from insights where id<=500 order by id"
).fetchall()

h = hashlib.sha256()
for r in rows:
    for f in r:
        h.update(b"\x00" if f is None else str(f).encode())   # NULL -> one 0x00 byte
        h.update(b"\x1f")                                     # unit separator after EVERY field
    h.update(b"\x1e")                                         # record separator after EVERY row
print(h.hexdigest())
```

Expected: `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed`

## The three details that make it irreproducible if guessed

1. **`str(f).encode()`, not a JSON dump and not a repr.** Integer ids become `"1"`, not `1`.
2. **A separator after EVERY field and EVERY row, including the last.** Not `join`.
3. **`id <= 500` is part of the recipe, not a detail.** The anchor was taken when the journal
   held 500 rows. Entries written since are legitimate additions, so a digest over *all*
   rows moves for innocent reasons and proves nothing. Always bound it at 500 — or re-anchor
   deliberately at a new bound and say so.

## Choosing your own witness instead

Perfectly fine, and a later session did exactly that rather than guess: compute any stable
digest over the same six fields before your change and again after, and quote both. The
value is the before/after pair, not the particular number. But if you quote a bare hash in
a report, **state the recipe beside it** or the next person cannot check your work — which
is the whole point of quoting it.
