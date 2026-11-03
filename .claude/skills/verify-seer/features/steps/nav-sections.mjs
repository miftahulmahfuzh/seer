// Walk Seer's four sections through the bottom bar, then into Sera and Sean, as the owner would.
export default async ({ page, base, shot, log }) => {
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  for (const [label, text] of [['Positions', 'Unrealized P/L'], ['Leaderboard', 'Forward test'], ['History', 'Trades'], ['Today', 'US session']]) {
    await page.getByRole('link', { name: label, exact: true }).last().click();
    await page.getByText(text, { exact: false }).first().waitFor();
    log(`${label}: shows "${text}"`);
  }
  await page.getByRole('link', { name: 'Sera, the method lab' }).first().click();
  await page.getByRole('heading', { name: 'Overview' }).first().waitFor();
  log('Sera: Overview');
  await page.getByRole('link', { name: 'Back to Seer' }).first().click();
  await page.getByRole('link', { name: /^Sean, your real trades/ }).first().click();
  await page.getByText('Profit and loss').first().waitFor();
  await shot('sean');
  log('Sean: Profit and loss');
};
