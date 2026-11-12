// Retired shelf on desktop (owner, 2026-11-12): the shelf is the live row's spread, `live.length`
// cards to a line, each retired card exactly under a live card (same x, same width, same 40%
// overlap, left covers right), opaque so no neighbour shows through. Demo data retires nothing, so
// retire some in the run's own throwaway database first (`$V sql` is read-only):
//   docker exec seer-pg-verify psql -U postgres -d v_${RUN//-/_} \
//     -c "update strategies set status='retired', paper_end='2026-10-30' where id in ('F1-SPY-SMA200-M','C')"
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-shelf.mjs --width 1440 --theme light
//   SHELF_PICK=C $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-shelf.mjs --width 1440 --theme dark
// Retire A and F4 as well for the wrap case (2 live, 4 retired: two lines of two).
export default async ({ page, base, shot, log }) => {
  const pick = process.env.SHELF_PICK;
  await page.goto(base + '/leaderboard' + (pick ? `?s=${encodeURIComponent(pick)}` : ''), { waitUntil: 'networkidle' });
  const btn = page.locator('button[aria-controls="retired-cards"]');
  if ((await btn.getAttribute('aria-expanded')) !== 'true') await btn.click();
  await page.locator('#retired-cards').evaluate(e => e.scrollIntoView({ block: 'center' }));
  await page.mouse.move(0, 0);
  await page.waitForTimeout(400);
  const r = await page.evaluate(() => {
    const box = e => { const b = e.getBoundingClientRect(); return { x: +b.x.toFixed(1), w: +b.width.toFixed(1), y: +b.y.toFixed(1), h: +b.height.toFixed(1) }; };
    const live = [...document.querySelector('article[data-status]').parentElement.children].map(box);
    const shelfEl = document.getElementById('retired-cards');
    const shelf = [...shelfEl.children].map(c => ({ ...box(c), id: decodeURIComponent(new URL(c.href).searchParams.get('s')), z: getComputedStyle(c).zIndex, shadow: getComputedStyle(c).boxShadow }));
    const sheet = box(shelfEl.closest('section'));
    const hit = (x, y) => { const c = document.elementFromPoint(x, y)?.closest('[data-status]'); return c?.href ? decodeURIComponent(new URL(c.href).searchParams.get('s')) : c ? 'SPY' : null; };
    const tops = shelf.slice(1).map(c => hit(c.x + c.w * 0.2, c.y + c.h / 2));
    const own = shelf.map(c => hit(c.x + c.w * 0.8, c.y + c.h / 2));
    return { live, shelf, sheet, tops, own, scroll: document.documentElement.scrollWidth - innerWidth };
  });
  const n = r.live.length;
  r.shelf.forEach((c, i) => {
    const l = r.live[i % n];
    if (Math.abs(c.x - l.x) > 0.75 || Math.abs(c.w - l.w) > 0.75) throw new Error(`${c.id} at x ${c.x} w ${c.w}; live card above at x ${l.x} w ${l.w}`);
    if (r.own[i] !== c.id && r.shelf[i + 1]?.id !== pick) throw new Error(`${c.id}'s right part is covered by ${r.own[i]}`);
  });
  if (r.scroll > 0) throw new Error(`horizontal scroll ${r.scroll}px`);
  const lastRight = Math.max(...r.shelf.map(c => c.x + c.w));
  log(`SHELF n=${n} live x/w: ${r.live.map(c => `${c.x}/${c.w}`).join(' ')}`);
  log(`SHELF cards: ${r.shelf.map(c => `${c.id} ${c.x}/${c.w} y${c.y} z${c.z}`).join(' | ')}; sheet ${r.sheet.x}–${r.sheet.x + r.sheet.w}, last card right ${lastRight.toFixed(1)}`);
  log(`SHELF on top in each overlap: ${r.tops.join(', ')}; right 60% owned: ${r.own.join(', ')}`);
  log(`SHELF picked shadow: ${r.shelf.filter(c => c.id === pick).map(c => c.shadow).join('') || 'none picked'}`);
  await shot('shelf');
};
