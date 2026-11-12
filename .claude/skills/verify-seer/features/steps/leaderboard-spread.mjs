// Desktop card spread (leaderboard-card-spread phase 1): the live cards are one flat row, each card
// laid over the left 40% of the card to its right, SPY always on top, a picked card raised in its
// own place, a Claude twin an ordinary card. Below 1024px: the unchanged column.
// Run on `up` demo data, at both desktop widths and at a phone width:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1440 --theme light
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1280
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 390
// Demo roster in board order: SPY, A, F4, F4's Claude twin, F1, C. With no ?s= the pick is A.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const F1 = 'F1-SPY-SMA200-M';
const ORDER = ['SPY', 'A', F4, TWIN, F1, 'C'];
const MONTHS = 'section[aria-labelledby="months-title"]';
const SPY = 'article[data-status]';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;
const OVERLAP = 0.4;

// Every live card in DOM order (the row is SPY's parent). Positions are also taken relative to the
// row: the checklist above can change height with the pick and move the whole row down, and R3.2
// is about the cards within the row.
const readRow = page => page.locator(SPY).first().evaluate(spy => {
  const row = spy.parentElement;
  const rb = row.getBoundingClientRect();
  const idOf = c => (c.getAttribute('href') ? decodeURIComponent(new URL(c.href).searchParams.get('s')) : 'SPY');
  const boxOf = el => {
    const b = el.getBoundingClientRect();
    return { x: b.x, y: b.y, w: b.width, h: b.height, right: b.right, bottom: b.bottom };
  };
  const cards = [...row.children].map(c => {
    const cs = getComputedStyle(c);
    const visible = sel => [...c.querySelectorAll(sel)].find(e => e.offsetParent !== null) ?? null;
    const code = visible('[class*="nameText"]');
    const ret = visible('[class*="metrics"] > :first-child .num');
    const box = boxOf(c);
    return {
      id: idOf(c), ...box, relX: box.x - rb.x, relY: box.y - rb.y,
      z: cs.zIndex, shadow: cs.boxShadow, transform: cs.transform, marginLeft: cs.marginLeft,
      outline: cs.outlineStyle,
      current: c.getAttribute('aria-current') === 'true', active: c.className.includes('cardActive'),
      ariaLabel: c.getAttribute('aria-label'),
      code: code && { ...boxOf(code), text: code.textContent, cut: code.scrollWidth > code.clientWidth + 1 },
      ret: ret && { ...boxOf(ret), text: ret.textContent },
    };
  });
  const rs = getComputedStyle(row);
  return { x: rb.x, right: rb.right, display: rs.display, flexDir: rs.flexDirection, cards };
});

export default async ({ page, base, shot, log }) => {
  const width = page.viewportSize()?.width ?? 0;
  const near = (a, b, tol = 0.5) => Math.abs(a - b) <= tol;
  const byId = row => Object.fromEntries(row.cards.map(c => [c.id, c]));
  // The card that is on top at a viewport point (the page's real hit testing, not a class name).
  const hit = (x, y) => page.evaluate(([px, py]) => {
    const c = document.elementFromPoint(px, py)?.closest('[data-status]');
    if (!c) return null;
    return c.getAttribute('href') ? decodeURIComponent(new URL(c.href).searchParams.get('s')) : 'SPY';
  }, [x, y]);
  const centre = async sel => {
    await page.locator(sel).first().evaluate(e => e.scrollIntoView({ block: 'center' }));
    await page.mouse.move(0, 0); // no hover state, no tooltip over a hit point
    await page.waitForTimeout(400); // the front shadow fades in over 0.18s
  };
  const open = async path => {
    await page.goto(base + path, { waitUntil: 'networkidle' });
    await centre(SPY);
  };
  const noDecks = async () => {
    const n = await page.locator('[data-deck], [class*="peek"]').count();
    if (n) throw new Error(`${n} deck wrappers or peek strips are still rendered`);
  };
  // For each neighbouring pair (i-1, i), the card on top inside card i's left 40%, where they overlap.
  const overlapTops = async row => {
    const out = [];
    for (let i = 1; i < row.cards.length; i++) {
      const c = row.cards[i];
      out.push(await hit(c.x + c.w * OVERLAP / 2, c.y + c.h / 2));
    }
    return out;
  };
  const spyWhole = async row => {
    const sp = row.cards.find(c => c.id === 'SPY');
    for (const fx of [0.15, 0.5, 0.85, 0.98]) for (const fy of [0.15, 0.5, 0.85]) {
      const top = await hit(sp.x + sp.w * fx, sp.y + sp.h * fy);
      if (top !== 'SPY') throw new Error(`SPY is covered by ${top} at (${fx}, ${fy}) of its box`);
    }
  };

  if (width < 1024) {
    // J6 (R1.2): the phone column, exactly as before.
    await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
    await noDecks();
    const r = await readRow(page);
    const ids = r.cards.map(c => c.id);
    if (JSON.stringify(ids) !== JSON.stringify(ORDER)) throw new Error(`column: ${ids.join(', ')}`);
    if (r.display !== 'contents') throw new Error(`the live row is a ${r.display} box below 1024px; want display: contents`);
    const [c0] = r.cards;
    for (const c of r.cards) {
      if (!near(c.x, c0.x) || !near(c.w, c0.w)) throw new Error(`${c.id} is out of the column: x ${c.x} w ${c.w}, want x ${c0.x} w ${c0.w}`);
      if (c.z !== 'auto' || c.transform !== 'none' || c.marginLeft !== '0px')
        throw new Error(`${c.id} carries desktop spread styles: z-index ${c.z}, transform ${c.transform}, margin-left ${c.marginLeft}`);
    }
    for (let i = 1; i < r.cards.length; i++) {
      const tuck = r.cards[i].y - r.cards[i - 1].bottom;
      if (!near(tuck, -40, 1)) throw new Error(`${r.cards[i].id} starts ${tuck}px from ${r.cards[i - 1].id}'s foot; the column tucks each sheet 40px`);
    }
    await centre(card(TWIN));
    const rc = await readRow(page);
    const f4 = rc.cards[2], tw = rc.cards[3];
    if ((await hit(tw.x + tw.w / 2, f4.bottom - 20)) !== TWIN) throw new Error("the twin's sheet does not lie over F4's foot");
    log(`J6 phone: one column ${ids.join(' | ')}, every card at x ${c0.x.toFixed(1)} and ${c0.w.toFixed(1)}px wide; ` +
      'no z-index, no transform, no sideways margin; each sheet tucks 40px under the next, the later sheet on top');
    await shot('phone');
    return;
  }

  // J1 (R1.1, R4.2): one flat row in board order, equal widths, 40% overlap, filling the row.
  await open('/leaderboard');
  await noDecks();
  const r0 = await readRow(page);
  const ids = r0.cards.map(c => c.id);
  if (JSON.stringify(ids) !== JSON.stringify(ORDER)) throw new Error(`row: ${ids.join(', ')}`);
  if (r0.display !== 'flex' || r0.flexDir !== 'row') throw new Error(`the live row is ${r0.display} ${r0.flexDir}`);
  const w = r0.cards[0].w;
  for (const c of r0.cards) {
    if (!near(c.w, w)) throw new Error(`${c.id} is ${c.w}px wide, SPY ${w}px`);
    if (!near(c.relY, 0)) throw new Error(`${c.id} sits ${c.relY}px below the row's top`);
    if (c.transform !== 'none') throw new Error(`${c.id} is transformed: ${c.transform}`);
    if (c.ariaLabel) throw new Error(`${c.id} still carries a tucked-card label: ${c.ariaLabel}`);
  }
  for (let i = 1; i < r0.cards.length; i++) {
    const step = r0.cards[i].x - r0.cards[i - 1].x;
    if (!near(step, w * (1 - OVERLAP), 0.75)) throw new Error(`${r0.cards[i].id} starts ${step}px after ${r0.cards[i - 1].id}; want ${w * (1 - OVERLAP)}`);
  }
  if (!near(r0.cards[0].x, r0.x) || !near(r0.cards.at(-1).right, r0.right, 0.75))
    throw new Error(`the row does not fill its width: cards ${r0.cards[0].x}–${r0.cards.at(-1).right}, row ${r0.x}–${r0.right}`);
  log(`J1 row: ${ids.join(' | ')} as one flat row; every card ${w.toFixed(1)}px wide, each next one ` +
    `${(w * (1 - OVERLAP)).toFixed(1)}px on (40% overlap); the cards span the row's ${(r0.right - r0.x).toFixed(1)}px exactly; no deck, no peek strip`);

  // J2 (R2.1, R2.2): left covers right; SPY whole and above the pick (A, right next to it).
  const tops0 = await overlapTops(r0);
  if (JSON.stringify(tops0) !== JSON.stringify(ORDER.slice(0, -1))) throw new Error(`on top where cards overlap: ${tops0.join(', ')}`);
  await spyWhole(r0);
  if (!byId(r0).A.current) throw new Error('A is not the default pick');
  log(`J2 stacking, A picked: every overlap shows its left card (${tops0.join(', ')}); SPY is on top at 12 points of its box, its right edge above the picked A`);

  // J3 (R1.3): each card's code and total return lie in its uncovered right 60% and are on top there.
  for (const c of r0.cards) {
    const free = c.x + c.w * OVERLAP;
    for (const [what, b] of [['code', c.code], ['total return', c.ret]]) {
      if (!b) throw new Error(`${c.id}: no ${what} on the card`);
      if (b.x < free - 0.5 || b.right > c.right + 0.5)
        throw new Error(`${c.id}'s ${what} spans ${b.x.toFixed(1)}–${b.right.toFixed(1)}, outside its uncovered ${free.toFixed(1)}–${c.right.toFixed(1)}`);
      if ((await hit(b.x + b.w / 2, b.y + b.h / 2)) !== c.id) throw new Error(`${c.id}'s ${what} is covered`);
    }
    if (c.code.cut) throw new Error(`${c.id}'s code is cut off: ${c.code.text}`);
  }
  log(`J3 readable: every card's code and total return sit in its uncovered right 60%, whole: ${r0.cards.map(c => `${c.code.text} ${c.ret.text}`).join(' · ')}`);

  // Legend stays one row (the earlier revamp's promise; not this phase's criterion).
  const legendTops = await page.locator('[class*="legendItem"]').evaluateAll(els =>
    els.filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().top)));
  if (legendTops.length !== ORDER.length || new Set(legendTops).size !== 1) throw new Error(`legend rows: ${JSON.stringify(legendTops)}`);
  await shot('spread');

  // Keyboard: a focused card rises just under the pick, so its focus ring shows.
  let focused = null;
  for (let k = 0; k < 80 && focused !== F1; k++) {
    await page.keyboard.press('Tab');
    focused = await page.evaluate(() => {
      const a = document.activeElement;
      return a?.hasAttribute('data-status') && a.getAttribute('href') ? decodeURIComponent(new URL(a.href).searchParams.get('s')) : null;
    });
  }
  if (focused !== F1) throw new Error('Tab never reached the F1 card');
  await page.waitForTimeout(100);
  const rf = await readRow(page);
  const f1 = byId(rf)[F1];
  if ((await hit(f1.x + f1.w * OVERLAP / 2, f1.y + f1.h / 2)) !== F1) throw new Error('the focused F1 card did not rise over its left neighbour');
  if (f1.outline !== 'solid') throw new Error(`the focused F1 card has no focus ring (${f1.outline})`);
  log('focus: Tab onto F1 raises it over the twin on its left, focus ring drawn');
  await page.evaluate(() => document.activeElement?.blur());

  // J4 (R3.1, R3.2, R4.1): pick the twin by its uncovered part. It rises in place with the front
  // shadow; nothing moves or resizes; F4, its original, is exactly as it was.
  await centre(SPY);
  const before = byId(await readRow(page));
  const tw = before[TWIN];
  await page.locator(card(TWIN)).first().click({ position: { x: tw.w * 0.7, y: tw.h / 2 } });
  await page.waitForURL(u => u.searchParams.get('s') === TWIN);
  await page.getByText("Can't be run").first().waitFor();
  await centre(SPY);
  const r2 = await readRow(page);
  const after = byId(r2);
  if (r2.cards.length !== ORDER.length) throw new Error(`the row has ${r2.cards.length} cards after the pick`);
  if (!after[TWIN].current || !after[TWIN].active) throw new Error('the twin is not the current, active card');
  const tops2 = await overlapTops(r2);
  const want2 = ['SPY', 'A', TWIN, TWIN, F1];
  if (JSON.stringify(tops2) !== JSON.stringify(want2)) throw new Error(`on top where cards overlap, twin picked: ${tops2.join(', ')}`);
  await spyWhole(r2);
  if (after[TWIN].shadow !== before.A.shadow || after[TWIN].shadow === before[TWIN].shadow)
    throw new Error(`the twin did not take the front card's shadow: ${after[TWIN].shadow}`);
  if (after.A.shadow !== before[F1].shadow) throw new Error('A kept the front shadow after the pick moved on');
  for (const id of ORDER) {
    const b = before[id], a = after[id];
    if (!near(a.relX, b.relX) || !near(a.relY, b.relY) || !near(a.w, b.w))
      throw new Error(`${id} moved or resized on the pick: x ${b.relX}->${a.relX}, y ${b.relY}->${a.relY}, w ${b.w}->${a.w}`);
    if (a.transform !== 'none') throw new Error(`${id} is transformed after the pick: ${a.transform}`);
    if (id !== 'A' && id !== TWIN && !near(a.h, b.h)) throw new Error(`${id} changed height on the pick: ${b.h}->${a.h}`);
  }
  // Only the tab is taller, by the 12px it reaches over the gap onto the month sheet.
  if (!near(before.A.h - before[F1].h, 12) || !near(after[TWIN].h - after[F1].h, 12))
    throw new Error(`tab heights: A +${before.A.h - before[F1].h}, twin +${after[TWIN].h - after[F1].h}; want +12`);
  const f4b = before[F4], f4a = after[F4];
  if (f4a.z !== f4b.z || f4a.shadow !== f4b.shadow || f4a.current || f4a.active || !near(f4a.h, f4b.h))
    throw new Error(`F4 changed when its twin was picked: z ${f4b.z}->${f4a.z}, shadow ${f4b.shadow}->${f4a.shadow}`);
  log(`J4 twin picked: ?s=${TWIN}; it now covers F4 where they overlap (${tops2.join(', ')}), front shadow on it, SPY still whole; ` +
    `every card's x, y and width unchanged, no transform, only the tab 12px taller; F4 untouched (same place, size, z ${f4a.z}, shadow)`);
  await shot('twin-picked');

  // J5 (R3.3): the pick still drives the checklist and the month sheet, and is the tab into it.
  const months = await page.locator(MONTHS).boundingBox();
  if (!near(after[TWIN].bottom, months.y, 1.5)) throw new Error(`the twin's tab ends at ${after[TWIN].bottom}, the month sheet starts at ${months.y}`);
  // textContent, not innerText: the eyebrow is upper-cased by CSS, and innerText applies that.
  const monthsTitle = (await page.locator('#months-title').textContent()) ?? '';
  const monthsCls = (await page.locator(MONTHS).getAttribute('class')) ?? '';
  if (!monthsTitle.includes('F4+Claude') || !monthsCls.split(/\s+/).includes('bg-teal'))
    throw new Error(`month sheet: "${monthsTitle}" in ${monthsCls}`);
  await page.getByText(/Go-live checklist · F4\+Claude/).first().waitFor();
  if ((await page.locator(MONTHS).getAttribute('data-tab')) !== null) throw new Error('a mid-row tab squared a sheet corner');
  await open('/leaderboard?s=C');
  const r3 = await readRow(page);
  const c = byId(r3).C;
  const tab = await page.locator(MONTHS).getAttribute('data-tab');
  const edge = await page.locator(card('C')).getAttribute('data-edge');
  const m3 = await page.locator(MONTHS).boundingBox();
  if (tab !== 'last' || edge !== 'last' || !near(c.bottom, m3.y, 1.5)) throw new Error(`C picked: data-tab=${tab} data-edge=${edge}, tab ${c.bottom} vs sheet ${m3.y}`);
  const tops3 = await overlapTops(r3);
  if (JSON.stringify(tops3) !== JSON.stringify(['SPY', 'A', F4, TWIN, 'C'])) throw new Error(`on top, C picked: ${tops3.join(', ')}`);
  for (const id of ORDER) {
    const b = before[id], a = byId(r3)[id];
    if (!near(a.relX, b.relX) || !near(a.w, b.w)) throw new Error(`${id} moved when C was picked`);
  }
  log('J5 panels: twin picked -> month sheet "' + monthsTitle.replace(/\s+/g, ' ') + '" in teal, checklist on F4+Claude, ' +
    'its tab meets the sheet; C picked -> data-tab=last, data-edge=last, its tab meets the sheet, C covers F1 where they overlap');
  await shot('last-tab');

  // Motion only without reduced motion.
  const durations = () => page.locator(card('C')).evaluate(e => getComputedStyle(e).transitionDuration);
  const moving = d => d.split(',').some(x => parseFloat(x) > 0);
  if (!moving(await durations())) throw new Error('no shadow transition on the spread cards');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  if (moving(await durations())) throw new Error('cards still animate under prefers-reduced-motion');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  log('motion: the front shadow fades in, and snaps under prefers-reduced-motion');
};
