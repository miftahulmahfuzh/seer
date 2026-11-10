// Desktop card stacks (leaderboard-desktop-revamp phase 3). Run on `up` demo data at desktop width:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-stack.mjs --width 1440 --theme light
// Demo roster: SPY, A, F4 with its Claude twin, F1, C. With no ?s= the pick is A.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const MONTHS = 'section[aria-labelledby="months-title"]';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;
const settle = page => page.waitForTimeout(700); // the pop is a 0.32s transition

export default async ({ page, base, shot, log }) => {
  if ((page.viewportSize()?.width ?? 0) < 1024) throw new Error('run at --width 1280 or 1440: decks are desktop only');
  const box = async sel => {
    const b = await page.locator(sel).first().boundingBox();
    if (!b) throw new Error(`no box for ${sel}`);
    return b;
  };
  const hitAt = (x, y) => page.evaluate(([px, py]) =>
    document.elementFromPoint(px, py)?.closest('[data-status]')?.getAttribute('href') ?? null, [x, y]);
  const center = b => [b.x + b.width / 2, b.y + b.height / 2];

  await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
  await settle(page);

  // One deck per family, in board order.
  const decks = await page.locator('[data-deck]').evaluateAll(els => els.map(d =>
    [...d.querySelectorAll('[data-status]')].map(c =>
      c.getAttribute('href') ? decodeURIComponent(new URL(c.href).searchParams.get('s')) : 'SPY')));
  const want = [['SPY'], ['A'], [F4, TWIN], ['F1-SPY-SMA200-M'], ['C']];
  if (JSON.stringify(decks) !== JSON.stringify(want)) throw new Error(`decks: ${JSON.stringify(decks)}`);
  log(`decks: ${decks.map(d => d.join(' + ')).join(' | ')}`);

  const openAt = async () => page.locator('[data-deck][data-open]').evaluateAll(els => els.map(e => e.getAttribute('data-deck')));
  if (JSON.stringify(await openAt()) !== JSON.stringify(['A'])) throw new Error(`open decks with A picked: ${await openAt()}`);

  // Closed F4 deck: the twin is tucked behind F4, offset up and right, and F4 covers its face.
  const f4 = await box(card(F4)), tw = await box(card(TWIN));
  const dx = tw.x - f4.x, dy = f4.y - tw.y;
  if (!(dx >= 4 && dx <= 12 && dy >= 4 && dy <= 12)) throw new Error(`twin offset dx=${dx} dy=${dy}`);
  if ((await hitAt(...center(tw))) !== `/leaderboard?s=${F4}`) throw new Error('the twin is not tucked behind F4');
  if (!((await page.locator(card(TWIN)).getAttribute('aria-label')) ?? '').includes('+Claude'))
    throw new Error('the tucked twin has no name as its label');
  log(`closed: F4+Claude peeks ${dx.toFixed(1)}px right and ${dy.toFixed(1)}px up from behind F4`);

  // One-row legend, whole codes, chips inside their cards.
  const tops = await page.locator('[class*="legendItem"]').evaluateAll(els =>
    els.filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().top)));
  if (tops.length !== 6 || new Set(tops).size !== 1) throw new Error(`legend rows: ${JSON.stringify(tops)}`);
  const cut = await page.locator('[data-deck] [class*="nameText"]').evaluateAll(els =>
    els.filter(e => e.offsetParent !== null && e.scrollWidth > e.clientWidth + 1).map(e => e.textContent));
  if (cut.length) throw new Error(`codes cut off: ${cut.join(', ')}`);
  const spill = await page.locator('[data-deck] [data-status]').evaluateAll(cards => cards.flatMap(c => {
    const r = c.getBoundingClientRect();
    return [...c.querySelectorAll('[class*="chips"] > *')].filter(x => {
      const b = x.getBoundingClientRect();
      return b.width > 0 && (b.right > r.right + 0.5 || b.left < r.left - 0.5);
    }).map(x => x.textContent);
  }));
  if (spill.length) throw new Error(`chips outside their card: ${spill.join(', ')}`);
  log('legend on one row (6 items); every code whole; every chip inside its card');
  await shot('closed');

  // Pick the twin by its peeking edge: its deck opens, F4 and the twin side by side, both readable.
  await page.locator(card(TWIN)).first().click({ position: { x: tw.width / 2, y: 3 } });
  await page.waitForURL(u => u.searchParams.get('s') === TWIN);
  await settle(page);
  if (JSON.stringify(await openAt()) !== JSON.stringify([F4])) throw new Error(`open decks with the twin picked: ${await openAt()}`);
  const f4o = await box(card(F4)), two = await box(card(TWIN)), a = await box(card('A'));
  if (two.x < f4o.x + f4o.width) throw new Error('the twin is not fanned out beside F4');
  if ((await hitAt(...center(f4o))) !== `/leaderboard?s=${F4}` || (await hitAt(...center(two))) !== `/leaderboard?s=${TWIN}`)
    throw new Error('F4 and its twin are not both readable');
  if (!(f4o.y < a.y - 5)) throw new Error(`the open deck did not pop forward: F4 top ${f4o.y}, A top ${a.y}`);
  if ((await page.locator(card(TWIN)).getAttribute('aria-current')) !== 'true') throw new Error('the twin is not the current card');
  const m1 = await box(MONTHS);
  if (Math.abs(two.y + two.height - m1.y) > 1.5) throw new Error(`the tab does not meet the sheet: ${two.y + two.height} vs ${m1.y}`);
  log(`twin picked: F4 deck open (F4 | F4+Claude), raised ${(a.y - f4o.y).toFixed(1)}px; the twin's tab meets the month sheet`);
  await shot('twin-open');

  // The last deck's pick squares the sheet's top-right corner.
  await page.goto(base + '/leaderboard?s=C', { waitUntil: 'networkidle' });
  await settle(page);
  const tab = await page.locator(MONTHS).getAttribute('data-tab');
  const edge = await page.locator(card('C')).getAttribute('data-edge');
  if (tab !== 'last' || edge !== 'last') throw new Error(`C picked: data-tab=${tab} data-edge=${edge}`);
  const c = await box(card('C')), m2 = await box(MONTHS);
  if (Math.abs(c.y + c.height - m2.y) > 1.5) throw new Error('C\'s tab does not meet the sheet');
  log('C picked: months sheet data-tab=last, C carries data-edge=last');
  await shot('last-tab');

  // Motion only without reduced motion.
  const durations = () => page.locator(card('C')).evaluate(e => getComputedStyle(e).transitionDuration);
  const moving = d => d.split(',').some(x => parseFloat(x) > 0);
  if (!moving(await durations())) throw new Error('no transition on deck cards');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  if (moving(await durations())) throw new Error('cards still animate under prefers-reduced-motion');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  log('the pop is a transition, and none under prefers-reduced-motion');
};
