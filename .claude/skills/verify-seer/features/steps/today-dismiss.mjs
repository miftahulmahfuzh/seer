export default async ({ page, base, shot, log }) => {
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  await page.getByText('Action needed').waitFor();
  await page.getByRole('button', { name: 'Copy limit price' }).first().waitFor();
  await shot('before');
  await page.getByRole('button', { name: 'Mark as done' }).click();
  await page.getByText('Action needed').waitFor({ state: 'detached', timeout: 30000 });
  await shot('after');
  log('dismissing the day-5 reminder removes the Action needed banner; tickets stay');
  await page.getByRole('button', { name: 'Copy limit price' }).first().waitFor();
};
