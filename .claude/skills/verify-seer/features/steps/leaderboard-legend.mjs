// Chart legend toggles (leaderboard-legend-toggles phase 1). The legend is its own row under the
// headline figures, its first swatch on the champion label's left edge, one row on desktop. Every
// item is a toggle (aria-pressed): pressed lines keep their colour, are 1px thicker and drawn last,
// every other line fades to 20%; nothing pressed is the chart as before. A card pick adds to the
// pressed set; un-pressing the pick keeps the card picked; a reload starts from the pick alone.
// Run on `up` demo data:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 1440 --theme light
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 1024
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-legend.mjs --width 390
// Demo roster in board order: SPY (champion, dotted, 1.75px), A, F4, F4's twin, F1, C (2px each,
// from view.ts looks()). With no ?s= the pick is A.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const F1 = 'F1-SPY-SMA200-M';
const IDS = ['SPY', 'A', F4, TWIN, F1, 'C'];
// buildChart's order: board order, champion (SPY) last.
const DRAW_ORDER = ['A', F4, TWIN, F1, 'C', 'SPY'];
const BASE = { SPY: 1.75, A: 2, [F4]: 2, [TWIN]: 2, [F1]: 2, C: 2 };
const CHART = 'svg[aria-label="Equity curves of each strategy against SPY"]';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;

export default async ({ page, base, shot, log }) => {
  const width = page.viewportSize()?.width ?? 0;
  const near = (a, b, tol) => Math.abs(a - b) <= tol;
  const same = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());

  // Settled opacities without waiting on the 0.15s fade; the fade itself is checked at the end.
  await page.emulateMedia({ reducedMotion: 'reduce' });

  const read = () => page.evaluate(sel => {
    const shown = el => el.getClientRects().length > 0;
    const svg = document.querySelector(sel);
    const sb = svg.getBoundingClientRect();
    const buttons = [...document.querySelectorAll('button[data-id][aria-pressed]')].filter(shown).map(b => {
      const r = b.getBoundingClientRect();
      return {
        id: b.dataset.id, pressed: b.getAttribute('aria-pressed') === 'true',
        top: Math.round(r.top), bottom: r.bottom,
        swatchLeft: b.firstElementChild.getBoundingClientRect().left,
        inHeadline: b.closest('[class*="headline"]') !== null,
        opacity: parseFloat(getComputedStyle(b).opacity),
      };
    });
    const paths = [...svg.querySelectorAll('path[data-line]')].map(p => ({
      id: p.dataset.line, on: p.hasAttribute('data-on'), stroke: p.getAttribute('stroke'),
      dash: p.getAttribute('stroke-dasharray'), width: parseFloat(p.getAttribute('stroke-width')),
      opacity: parseFloat(getComputedStyle(p).opacity),
    }));
    return { buttons, paths, focus: svg.hasAttribute('data-focus'), svgTop: sb.top, svgBottom: sb.bottom };
  }, CHART);
  const pressedIds = st => st.buttons.filter(b => b.pressed).map(b => b.id);
  const press = async id => {
    await page.locator(`button[data-id="${id}"]:visible`).click();
    await page.mouse.move(0, 0); // no hover tint, no tooltip
  };
  const expectPressed = (st, want, what) => {
    if (!same(pressedIds(st), want)) throw new Error(`${what}: pressed ${JSON.stringify(pressedIds(st))}, want ${JSON.stringify(want)}`);
  };
  let strokes = null; // each line's colour and dash as the server drew it, recorded on first read
  const checkLines = (st, litIds, what) => {
    const lit = new Set(litIds);
    if (st.paths.length !== IDS.length) throw new Error(`${what}: ${st.paths.length} lines, want ${IDS.length}`);
    for (const p of st.paths) {
      const b = BASE[p.id];
      if (strokes && (p.stroke !== strokes[p.id].stroke || p.dash !== strokes[p.id].dash))
        throw new Error(`${what}: ${p.id} changed colour or dash: ${p.stroke} ${p.dash}`);
      if (lit.has(p.id)) {
        if (!p.on || !near(p.width, b + 1, 0.001) || !near(p.opacity, 1, 0.01))
          throw new Error(`${what}: highlighted ${p.id} is width ${p.width} (want ${b + 1}), opacity ${p.opacity}, data-on ${p.on}`);
      } else if (lit.size) {
        if (p.on || !near(p.width, b, 0.001) || !near(p.opacity, 0.2, 0.02))
          throw new Error(`${what}: faded ${p.id} is width ${p.width} (want ${b}), opacity ${p.opacity} (want 0.2)`);
      } else if (p.on || p.width !== b || p.opacity !== 1) {
        throw new Error(`${what}: ${p.id} is width ${p.width} (want ${b}), opacity ${p.opacity} (want 1), data-on ${p.on}`);
      }
    }
    if (lit.size) {
      const tail = st.paths.slice(-lit.size).map(p => p.id);
      if (!same(tail, litIds)) throw new Error(`${what}: drawn last ${tail.join(', ')}, want the highlighted ${litIds.join(', ')}`);
    } else if (JSON.stringify(st.paths.map(p => p.id)) !== JSON.stringify(DRAW_ORDER)) {
      throw new Error(`${what}: draw order ${st.paths.map(p => p.id).join(', ')}, want ${DRAW_ORDER.join(', ')}`);
    }
    if (st.focus !== lit.size > 0) throw new Error(`${what}: svg data-focus ${st.focus} with ${lit.size} highlighted`);
  };
  const open = async path => {
    await page.goto(base + path, { waitUntil: 'networkidle' });
    await page.mouse.move(0, 0);
  };

  if (width < 1024) {
    // J9 (R2.1): on the phone the legend is the row under the axis, and its items are the same toggles.
    await open('/leaderboard');
    const st0 = await read();
    if (JSON.stringify(st0.buttons.map(b => b.id)) !== JSON.stringify(IDS)) throw new Error(`phone legend: ${st0.buttons.map(b => b.id).join(', ')}`);
    if (st0.buttons.some(b => b.top < st0.svgBottom)) throw new Error('the phone legend is not under the chart');
    expectPressed(st0, ['A'], 'phone, landed');
    await press(F1);
    const st1 = await read();
    expectPressed(st1, ['A', F1], 'phone, F1 pressed');
    checkLines(st1, ['A', F1], 'phone, F1 pressed');
    await shot('phone-two-lit');
    await press(F1);
    expectPressed(await read(), ['A'], 'phone, F1 released');
    log('J9 phone: the legend is the row under the axis; pressing F1 sets aria-pressed true and lights its line beside A; pressing again sets it false');
    return;
  }

  // J1 (R1.1, R1.2): the legend is its own row under the figures, on the champion label's edge, one row.
  await open('/leaderboard');
  const anchor = await page.evaluate(() => {
    const label = [...document.querySelectorAll('[class*="statLabel"]')]
      .find(e => e.getClientRects().length > 0 && e.textContent.includes('champion'));
    const stats = label.closest('[class*="stats"]');
    return { left: label.getBoundingClientRect().left, statsBottom: stats.getBoundingClientRect().bottom, text: label.textContent };
  });
  const st0 = await read();
  strokes = Object.fromEntries(st0.paths.map(p => [p.id, { stroke: p.stroke, dash: p.dash }]));
  if (JSON.stringify(st0.buttons.map(b => b.id)) !== JSON.stringify(IDS)) throw new Error(`legend: ${st0.buttons.map(b => b.id).join(', ')}`);
  const first = st0.buttons[0];
  if (!near(first.swatchLeft, anchor.left, 1)) throw new Error(`first swatch at x ${first.swatchLeft}, "${anchor.text}" at x ${anchor.left}`);
  if (st0.buttons.some(b => b.inHeadline)) throw new Error('the legend is still inside the headline');
  if (first.top < anchor.statsBottom || first.bottom > st0.svgTop) throw new Error(`legend row at ${first.top}, figures end ${anchor.statsBottom}, chart starts ${st0.svgTop}`);
  const tops = new Set(st0.buttons.map(b => b.top));
  if (tops.size !== 1) throw new Error(`legend wraps: tops ${JSON.stringify([...tops])}`);
  log(`J1 row at ${width}px: ${IDS.length} toggles in one row at y ${first.top}, under the figures (end ${anchor.statsBottom.toFixed(1)}) ` +
    `and above the chart; first swatch x ${first.swatchLeft.toFixed(2)}, "${anchor.text.trim()}" x ${anchor.left.toFixed(2)}`);

  // Landing: only the pick (A) is pressed.
  expectPressed(st0, ['A'], 'landed');
  checkLines(st0, ['A'], 'landed');
  await shot('landed');

  // J2 (R2.1): a click flips aria-pressed, both ways.
  await press(F1);
  const st2 = await read();
  if (!st2.buttons.find(b => b.id === F1).pressed) throw new Error('F1 did not turn pressed');
  await press(F1);
  const st2b = await read();
  if (st2b.buttons.find(b => b.id === F1).pressed) throw new Error('F1 did not turn back');
  log('J2 toggle: F1 aria-pressed false -> true -> false');

  // J3 (R2.2): two pressed (A, F4): both 1px thicker, own colour, drawn last; the rest at 20%.
  await press(F4);
  const st3 = await read();
  expectPressed(st3, ['A', F4], 'A and F4');
  checkLines(st3, ['A', F4], 'A and F4');
  const dim = st3.buttons.filter(b => !b.pressed);
  if (dim.some(b => b.opacity > 0.5)) throw new Error(`unpressed legend items not faded: ${dim.map(b => `${b.id} ${b.opacity}`).join(', ')}`);
  log(`J3 compare two: A and F4 at ${BASE.A + 1}px, full opacity, drawn last; SPY, ${TWIN}, ${F1}, C at their own width and opacity 0.2; unpressed items faded`);
  await shot('two-lit');

  // J4 (R2.4): every item pressed at once, SPY included.
  for (const id of IDS) if (!(await read()).buttons.find(b => b.id === id).pressed) await press(id);
  const st4 = await read();
  expectPressed(st4, IDS, 'all');
  checkLines(st4, IDS, 'all');
  log('J4 all six pressed, SPY included: every line 1px thicker at full opacity');
  await shot('all-lit');

  // J5 (R2.3): nothing pressed is today's chart: own colour and dash, SPY 1.75px, the rest 2px, full opacity, champion last.
  for (const id of IDS) await press(id);
  const st5 = await read();
  expectPressed(st5, [], 'none');
  checkLines(st5, [], 'none');
  if (st5.buttons.some(b => b.opacity !== 1 && b.id !== 'C')) throw new Error('legend items still faded with nothing pressed');
  log(`J5 none pressed: ${st5.paths.map(p => `${p.id} ${p.width}px`).join(', ')}, all opacity 1, no data-focus`);
  await shot('none-lit');

  // J6 (R3.1): picking a card adds it. Fresh load (A), press F1, then pick C by its card.
  await open('/leaderboard');
  await press(F1);
  expectPressed(await read(), ['A', F1], 'before the pick');
  const c = page.locator(card('C')).first();
  await c.scrollIntoViewIfNeeded();
  const cb = await c.boundingBox();
  await c.click({ position: { x: cb.width * 0.7, y: cb.height / 2 } }); // its right 60% is on top
  await page.waitForURL(u => u.searchParams.get('s') === 'C');
  await page.getByText(/Go-live checklist · C/).first().waitFor();
  await page.waitForFunction(() => document.querySelector('button[data-id="C"]')?.getAttribute('aria-pressed') === 'true');
  await page.mouse.move(0, 0);
  const st6 = await read();
  expectPressed(st6, ['A', F1, 'C'], 'after picking C');
  checkLines(st6, ['A', F1, 'C'], 'after picking C');
  if ((await c.getAttribute('aria-current')) !== 'true') throw new Error('C is not the picked card');
  log('J6 pick adds: A and F1 pressed, card C clicked -> ?s=C, C pressed and lit, A and F1 still pressed');
  await shot('pick-added');

  // J7 (R3.2): un-pressing the pick's item un-highlights its line; the card stays picked.
  const eyebrow = () => page.evaluate(() =>
    [...document.querySelectorAll('.eyebrow')].map(e => e.textContent).find(t => t.startsWith('Go-live checklist')));
  const before = await eyebrow();
  await press('C');
  const st7 = await read();
  expectPressed(st7, ['A', F1], 'C released');
  checkLines(st7, ['A', F1], 'C released');
  if (new URL(page.url()).searchParams.get('s') !== 'C') throw new Error(`URL moved: ${page.url()}`);
  if ((await c.getAttribute('aria-current')) !== 'true') throw new Error('C lost aria-current');
  if ((await eyebrow()) !== before) throw new Error(`checklist changed: "${before}" -> "${await eyebrow()}"`);
  log(`J7 C released: its line at 0.2 with the others, card C still aria-current, checklist still "${before}", URL still ?s=C`);

  // J8 (R3.3): a reload starts from the pick alone; nothing went to the URL or to storage.
  const url = new URL(page.url());
  if (url.pathname !== '/leaderboard' || url.search !== '?s=C') throw new Error(`state leaked into the URL: ${url.search}`);
  const stored = await page.evaluate(() =>
    JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)]));
  if (stored.includes(F1)) throw new Error(`a highlight leaked into browser storage: ${stored}`);
  await page.reload({ waitUntil: 'networkidle' });
  await page.mouse.move(0, 0);
  const st8 = await read();
  expectPressed(st8, ['C'], 'reloaded');
  checkLines(st8, ['C'], 'reloaded');
  log('J8 reload on ?s=C: only C pressed (A and F1 forgotten); URL carried only ?s=C, storage held no highlight');
  await shot('reloaded');

  // Motion: the fade animates, and snaps under reduced motion.
  const duration = () => page.locator(`${CHART} path[data-line]`).first().evaluate(p => getComputedStyle(p).transitionDuration);
  if (parseFloat(await duration()) !== 0) throw new Error('lines animate under prefers-reduced-motion');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  if (!(parseFloat(await duration()) > 0)) throw new Error('no fade on the chart lines');
  log('motion: line fades take 0.15s, none under prefers-reduced-motion');
};
