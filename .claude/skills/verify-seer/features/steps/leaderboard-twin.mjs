// Seer Adversarial + R1 (leaderboard-desktop-revamp phase 1): F4's Claude twin sits right after F4
// in F4's PARTNER colour (sky -> teal) with the twin dash and an icon of its own (F4 gauge, the twin
// rocket), labelled Paper; A, F1 and C keep their colours; no two cards share a sheet and no two
// switch buttons share an icon; the twin's checklist says its backtest can't be run.
// Run on `up` demo data: `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs`.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;
const SHEETS = [
  'bg-sheet', 'bg-lav', 'bg-sky', 'bg-sage', 'bg-rose', 'bg-plum', 'bg-stone',
  'bg-amber', 'bg-orchid', 'bg-berry', 'bg-moss', 'bg-teal', 'bg-iris',
];

export default async ({ page, base, shot, log }) => {
  await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
  const order = await page.locator('a[href^="/leaderboard?s="][data-status]').evaluateAll(
    els => els.map(e => decodeURIComponent(new URL(e.href).searchParams.get('s'))));
  const at = order.indexOf(F4);
  if (at < 0 || order[at + 1] !== TWIN) throw new Error(`twin is not right after F4: ${order.join(', ')}`);
  log(`card order: ${order.join(', ')}`);

  const cls = async id => (await page.locator(card(id)).first().getAttribute('class')) ?? '';
  const want = { A: 'bg-lav', [F4]: 'bg-sky', [TWIN]: 'bg-teal', 'F1-SPY-SMA200-M': 'bg-sage', C: 'bg-rose' };
  for (const [id, bg] of Object.entries(want)) {
    if (!(await cls(id)).split(/\s+/).includes(bg)) throw new Error(`${id} card is not ${bg}: ${await cls(id)}`);
  }
  log('colours: A lav, F4 sky, F4+Claude teal (its partner), F1 sage, C rose (originals unchanged by the twin)');

  const sheets = await page.locator('a[data-status], article[data-status]').evaluateAll(
    (els, list) => els.map(e => [...e.classList].find(c => list.includes(c)) ?? '(none)'), SHEETS);
  if (new Set(sheets).size !== sheets.length) throw new Error(`two cards share a sheet: ${sheets.join(', ')}`);
  log(`every card its own sheet: ${sheets.join(', ')}`);

  const strokes = async v => page.locator(`svg path[stroke="var(--${v}-line)"]`).evaluateAll(
    els => els.map(e => e.getAttribute('stroke-dasharray')));
  const sky = await strokes('sky'), teal = await strokes('teal');
  if (sky.length !== 1 || sky[0] !== null) throw new Error(`sky lines: ${JSON.stringify(sky)}`);
  if (teal.length !== 1 || teal[0] !== '3 3') throw new Error(`teal lines: ${JSON.stringify(teal)}`);
  log('chart: F4 one solid sky line, its twin one teal line dashed 3 3');

  const icons = async sel => page.locator(sel).evaluateAll(els => els.map(e =>
    [...e.classList].find(c => c.startsWith('lucide-')) ?? '(none)'));
  const iconsOf = async id => icons(`${card(id)} svg`);
  const f4Icons = await iconsOf(F4), twinIcons = await iconsOf(TWIN);
  if (!f4Icons.includes('lucide-gauge') || f4Icons.includes('lucide-rocket')) throw new Error(`F4 card icons: ${f4Icons}`);
  if (!twinIcons.includes('lucide-rocket') || twinIcons.includes('lucide-gauge')) throw new Error(`twin card icons: ${twinIcons}`);
  log('cards: F4 draws a gauge, F4+Claude a rocket');

  const switchIcons = await icons('nav[aria-label="Strategy"] a svg');
  if (switchIcons.length < 2 || new Set(switchIcons).size !== switchIcons.length)
    throw new Error(`switch icons repeat: ${switchIcons.join(', ')}`);
  if ((await page.locator(`nav[aria-label="Strategy"] a[href="/leaderboard?s=${TWIN}"] svg.lucide-rocket`).count()) !== 1)
    throw new Error('the twin switch button does not draw a rocket');
  log(`switch: every button its own icon: ${switchIcons.join(', ')}`);

  const chip = page.locator(card(TWIN)).getByText('Paper', { exact: true });
  await chip.first().waitFor();
  if ((await page.locator(card(F4)).getByText('Paper', { exact: true }).count()) !== 0)
    throw new Error('the original carries a Paper chip; only twins do');
  log('Paper chip on the twin card only');
  await shot('board');

  // At desktop width F4 covers the twin's left 40% (the card spread), so click inside its uncovered
  // right part: its horizontal middle, near the top edge.
  const twinCard = page.locator(card(TWIN)).first();
  const twinBox = await twinCard.boundingBox();
  await twinCard.click((page.viewportSize()?.width ?? 0) >= 1024 && twinBox ? { position: { x: twinBox.width / 2, y: 3 } } : {});
  await page.waitForURL(u => u.searchParams.get('s') === TWIN);
  await page.getByText("Can't be run").first().waitFor();
  await page.getByText('Paper only. No backtest possible.').first().waitFor();
  await page.getByText('Claude knows how the past turned out').first().waitFor();
  await shot('twin-checklist');
  log("picking the twin: checklist rule 5 reads Backtest gate · Can't be run, with the reason");
};
