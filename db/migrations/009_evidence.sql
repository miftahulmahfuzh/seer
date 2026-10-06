-- Seer schema v9: every paper entry keeps the evidence its method saw (why-this-pick pipeline).
-- Additive only: three nullable columns. No row is touched.
--
-- evidence: a JSON array of short plain-English strings (strategies.evidence, contract K1), the
-- numbers the method's formula read for that symbol on the decision night, already formatted for
-- a reader. Written by `paper` when it writes the row; NULL = no evidence (the idle instrument, a
-- symbol the method could not explain, an evidence function that failed that night, or any row
-- written before this migration). Display and explanation input only: nothing trades on it and
-- the replay (paper_check) never reads it.
ALTER TABLE orders        ADD COLUMN IF NOT EXISTS evidence jsonb;
ALTER TABLE book_targets  ADD COLUMN IF NOT EXISTS evidence jsonb;
ALTER TABLE book_previews ADD COLUMN IF NOT EXISTS evidence jsonb;
