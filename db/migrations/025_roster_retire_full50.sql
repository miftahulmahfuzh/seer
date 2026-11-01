-- Seer schema v25: FULL50-FR-GT leaves the roster (owner, 2026-11-01).
--
-- The owner's instruction, after the Sera batch's calculate-assets runs and a re-rank of four
-- candidates against SQUALL: "let's just kick FULL50". No replacement was named, so nothing is
-- admitted here; the roster simply has one fewer active book.
--
-- WHAT IS LOST, SAID PLAINLY. 023 admitted FULL50 as the always-invested CONTROL, the complement
-- of C: it measures what never stepping aside costs or pays. Retiring it ends that forward
-- measurement. RAW35 and MOM70 are both unswitched too, so the question is still partly watched.
--
-- RETIRED, NOT DELETED. It keeps every row it ever wrote and stays on the leaderboard; it only
-- stops trading. paper_end is its last stepped session, the same rule 024 used for MOM-FR-GT.
UPDATE strategies AS s SET
    status = 'retired',
    paper_end = (SELECT ps.last_session FROM paper_state ps WHERE ps.strategy_id = s.id)
WHERE s.id = 'FULL50-FR-GT' AND s.status = 'active';

UPDATE strategies SET sort = 24 WHERE id = 'FULL50-FR-GT';
