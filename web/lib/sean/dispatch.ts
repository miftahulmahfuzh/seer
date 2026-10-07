/**
 * Asks GitHub to run Sean's engine workflow (.github/workflows/sean.yml, Phase 4) now, so the
 * daily profit-and-loss series catches up with a new or deleted order before the nightly run.
 *
 * Best effort and never throws: no GITHUB_DISPATCH_TOKEN, a missing workflow (404, before Phase 4
 * lands), or any other failure only means the nightly run picks the change up. Returns whether
 * the dispatch was accepted.
 */
export async function dispatchSeanMarks(): Promise<boolean> {
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    console.log('sean dispatch skipped: GITHUB_DISPATCH_TOKEN is not set');
    return false;
  }
  try {
    const res = await fetch(
      'https://api.github.com/repos/miftahulmahfuzh/seer/actions/workflows/sean.yml/dispatches',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        body: JSON.stringify({ ref: 'main' }),
        signal: AbortSignal.timeout(8000),
      },
    );
    if (res.status === 404) {
      console.log('sean dispatch skipped: sean.yml is not on main yet');
      return false;
    }
    if (!res.ok) {
      console.error('sean dispatch failed', res.status, await res.text().catch(() => ''));
      return false;
    }
    return true;
  } catch (e) {
    console.error('sean dispatch failed', e);
    return false;
  }
}
