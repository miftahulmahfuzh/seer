-- Seer schema v26: MOM70-FR-GT leaves the roster (owner, 2026-11-01).
--
-- The owner's instruction, the same day 025 retired FULL50: "kick MOM70". No replacement was
-- named, so nothing is admitted here; the roster simply has one fewer active book.
--
-- WHAT IS LOST, SAID PLAINLY. 024 admitted MOM70 as the 70/30 momentum-beside-SPY blend: seventy
-- percent in the thirty strongest twelve-minus-one-month names, thirty percent in SPY, monthly,
-- no market switch. Its paper_start is 2026-11-02, so it has essentially no forward record, and
-- retiring it ends the only forward look at whether that momentum edge survives. RAW35 and COSK
-- stay.
--
-- RETIRED, NOT DELETED. It keeps every row it ever wrote and stays on the leaderboard; it only
-- stops trading. paper_end is its last stepped session, the same rule 024 and 025 used.
UPDATE strategies AS s SET
    status = 'retired',
    paper_end = (SELECT ps.last_session FROM paper_state ps WHERE ps.strategy_id = s.id)
WHERE s.id = 'MOM70-FR-GT' AND s.status = 'active';

UPDATE strategies SET sort = 25 WHERE id = 'MOM70-FR-GT';
