import { notFound, redirect } from 'next/navigation';
import { auth } from '@/auth';
import { isAllowed } from '@/lib/allow';
import { isSeraUser } from '@/lib/sera/access';

/**
 * The /sean gate (plan invariant 3): Sera's exact rule, because Sean shows the owner's real money.
 * Signed out: sign-in, which returns to `next` afterwards. Signed in as anyone but the owner (or
 * outside ALLOWED_EMAIL): 404, so the section is not revealed. Returns the signed-in owner.
 * Every /sean page calls this itself: layouts do not re-run on client navigation.
 */
export async function requireSean(next = '/sean') {
  const session = await auth();
  const user = session?.user;
  if (!user) redirect(`/signin?next=${encodeURIComponent(next)}`);
  if (!isAllowed(user.email, process.env.ALLOWED_EMAIL) || !isSeraUser(user.email)) notFound();
  return user;
}

/**
 * The same gate as a yes/no, for /api/sean/* routes and server actions, where redirect() and
 * notFound() are the wrong answer (a 307 to /signin would tell a stranger the section exists).
 */
export async function isSeanCaller(): Promise<boolean> {
  const session = await auth();
  const email = session?.user?.email;
  return isAllowed(email, process.env.ALLOWED_EMAIL) && isSeraUser(email);
}
