// Seer Adversarial (phase 3): F4's Claude twin sits right after F4, in F4's colour with its own
// dash, labelled Paper; F1 and C keep their colours; the twin's checklist says its backtest can't
// be run. Run on `up` demo data: `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs`.
const TWIN = 'F4-MOM12-N20-TREND-CX';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;

export default async ({ page, base, shot, log }) => {
  await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
  const order = await page.locator('a[href^="/leaderboard?s="][data-status]').evaluateAll(
    els => els.map(e => decodeURIComponent(new URL(e.href).searchParams.get('s'))));
  const at = order.indexOf('F4-MOM12-N20-TREND');
  if (at < 0 || order[at + 1] !== TWIN) throw new Error(`twin is not right after F4: ${order.join(', ')}`);
  log(`card order: ${order.join(', ')}`);

  const cls = async id => (await page.locator(card(id)).first().getAttribute('class')) ?? '';
  const want = { 'F4-MOM12-N20-TREND': 'bg-sky', [TWIN]: 'bg-sky', 'F1-SPY-SMA200-M': 'bg-sage', C: 'bg-rose', A: 'bg-lav' };
  for (const [id, bg] of Object.entries(want)) {
    if (!(await cls(id)).split(/\s+/).includes(bg)) throw new Error(`${id} card is not ${bg}: ${await cls(id)}`);
  }
  log('colours: A lav, F4 sky, F4+Claude sky, F1 sage, C rose (F1 and C unchanged by the twin)');

  const sky = await page.locator('svg path[stroke="var(--sky-line)"]').evaluateAll(
    els => els.map(e => e.getAttribute('stroke-dasharray')));
  if (sky.length !== 2 || !sky.includes(null) || !sky.includes('3 3')) throw new Error(`sky lines: ${JSON.stringify(sky)}`);
  log('chart: two sky lines, F4 solid and its twin dashed 3 3');

  const chip = page.locator(card(TWIN)).getByText('Paper', { exact: true });
  await chip.first().waitFor();
  if ((await page.locator(card('F4-MOM12-N20-TREND')).getByText('Paper', { exact: true }).count()) !== 0)
    throw new Error('the original carries a Paper chip; only twins do');
  log('Paper chip on the twin card only');
  await shot('board');

  await page.locator(card(TWIN)).first().click();
  await page.waitForURL(u => u.searchParams.get('s') === TWIN);
  await page.getByText("Can't be run").first().waitFor();
  await page.getByText('Paper only. No backtest possible.').first().waitFor();
  await page.getByText('Claude knows how the past turned out').first().waitFor();
  await shot('twin-checklist');
  log("picking the twin: checklist rule 5 reads Backtest gate · Can't be run, with the reason");
};
