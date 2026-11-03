export default async ({ page, base, shot, log }) => {
  await page.goto(base + '/sean/plan', { waitUntil: 'networkidle' });
  await page.getByText('3 things to do').waitFor();
  await shot('before');
  const first = page.getByRole('button', { name: /^Mark done:/ }).first();
  log(`clicking: ${await first.getAttribute('aria-label')}`);
  await first.click();
  await page.getByText('2 things to do').waitFor({ timeout: 30000 });
  await shot('after');
  log('marking one reminder done drops the plan from 3 to 2 things to do');
};
