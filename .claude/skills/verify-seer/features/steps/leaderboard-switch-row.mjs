// R2 (leaderboard-desktop-revamp phase 2): the go-live checklist's strategy switcher is one row at any
// count on desktop (below 1024px it is the unchanged loose row). Demo data has fewer than 7 research
// strategies, so after checking the real row this clones buttons in the live DOM up to 7 and 12, sets
// --n the way StrategySwitch would, and measures the real stylesheet. Run at each desktop width:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280
const SHEET_NAV = 'section:has(> div > nav[aria-label="Strategy"]) nav[aria-label="Strategy"]';

const measure = page => page.locator(SHEET_NAV).first().evaluate(nav => {
  const sheet = nav.closest('section');
  const pad = parseFloat(getComputedStyle(sheet).paddingRight);
  const contentRight = sheet.getBoundingClientRect().right - pad;
  const btns = [...nav.querySelectorAll(':scope > a')].map(a => {
    const r = a.getBoundingClientRect();
    const svg = a.querySelector('svg').getBoundingClientRect();
    return { top: Math.round(r.top), left: r.left, right: r.right, w: r.width, h: r.height, icon: svg.width,
      current: a.getAttribute('aria-current') === 'true', bg: getComputedStyle(a).backgroundColor };
  });
  return { n: btns.length, btns, contentRight, overflow: nav.scrollWidth - nav.clientWidth };
});

const check = (m, label) => {
  const rows = new Set(m.btns.map(b => b.top));
  if (rows.size !== 1) throw new Error(`${label}: ${m.n} buttons sit on ${rows.size} rows (tops ${[...rows].join(',')})`);
  if (m.overflow > 1) throw new Error(`${label}: row overflows its nav by ${m.overflow}px`);
  const last = m.btns[m.btns.length - 1];
  if (last.right > m.contentRight + 1) throw new Error(`${label}: last button ends ${last.right - m.contentRight}px past the sheet's padding`);
  for (const b of m.btns) {
    if (Math.abs(b.w - b.h) > 1) throw new Error(`${label}: a button is not round (${b.w}x${b.h})`);
    if (b.w < 20) throw new Error(`${label}: a button shrank to ${b.w}px`);
    if (b.w > 46.5) throw new Error(`${label}: a button grew past 46px (${b.w})`);
    if (b.icon > b.w - 4) throw new Error(`${label}: icon ${b.icon}px does not fit its ${b.w}px button`);
  }
  const widths = m.btns.map(b => b.w);
  if (Math.max(...widths) - Math.min(...widths) > 1) throw new Error(`${label}: unequal buttons ${widths.join(',')}`);
  const cur = m.btns.find(b => b.current);
  if (!cur || cur.bg === 'rgba(0, 0, 0, 0)') throw new Error(`${label}: the picked button lost its ink fill`);
  return `${label}: ${m.n} buttons, one row, ${widths[0].toFixed(1)}px each, icon ${m.btns[0].icon.toFixed(1)}px`;
};

const growTo = (page, n) => page.locator(SHEET_NAV).first().evaluate((nav, n) => {
  const proto = [...nav.querySelectorAll(':scope > a')].find(a => a.getAttribute('aria-current') !== 'true');
  while (nav.querySelectorAll(':scope > a').length < n) {
    const c = proto.cloneNode(true);
    const k = nav.querySelectorAll(':scope > a').length;
    c.setAttribute('aria-label', `Clone ${k}`); c.setAttribute('data-tip', `Clone ${k}`);
    nav.appendChild(c);
  }
  nav.style.setProperty('--n', String(n));
}, n);

export default async ({ page, base, shot, log }) => {
  if ((page.viewportSize()?.width ?? 0) < 1024) throw new Error('run at --width 1024, 1280 or 1440: the one-row fit is desktop only');
  await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
  await page.locator(SHEET_NAV).first().waitFor();

  log(check(await measure(page), 'real roster'));
  const first = page.locator(`${SHEET_NAV} > a`).first();
  const tip = await first.getAttribute('data-tip');
  await first.hover();
  await page.getByRole('tooltip').filter({ hasText: tip }).waitFor({ timeout: 5000 });
  log(`tooltip "${tip}" shows on hover`);
  await page.mouse.move(0, 0);

  for (const n of [7, 12]) {
    await growTo(page, n);
    log(check(await measure(page), `${n} strategies`));
    await page.locator(SHEET_NAV).first().scrollIntoViewIfNeeded();
    await shot(`switch-${n}`);
  }

  // Neighbour: positions keeps the default loose row (46px circles, flex-wrap), untouched by fit.
  await page.goto(base + '/positions', { waitUntil: 'networkidle' });
  const pos = await page.locator('nav[aria-label="Strategy"]').first().evaluate(nav => ({
    display: getComputedStyle(nav).display, wrap: getComputedStyle(nav).flexWrap, style: nav.getAttribute('style'),
    w: nav.querySelector('a').getBoundingClientRect().width,
  }));
  if (pos.display !== 'flex' || pos.wrap !== 'wrap' || pos.style !== null || Math.abs(pos.w - 46) > 0.5)
    throw new Error(`positions switcher changed: ${JSON.stringify(pos)}`);
  log('positions: default switcher unchanged (flex, wrap, 46px, no inline style)');
};
