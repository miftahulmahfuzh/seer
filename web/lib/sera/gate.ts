import { notFound, redirect } from 'next/navigation';
import { auth } from '@/auth';
import { isAllowed } from '@/lib/allow';
import { isSeraUser } from './access';

/**
 * The /sera gate (plan invariant 3). Signed out: sign-in, which returns to `next` afterwards.
 * Signed in as anyone but SERA_EMAIL (or outside ALLOWED_EMAIL): 404, so the section is not revealed.
 * Returns the signed-in Sera user.
 */
export async function requireSera(next = '/sera') {
  const session = await auth();
  const user = session?.user;
  if (!user) redirect(`/signin?next=${encodeURIComponent(next)}`);
  if (!isAllowed(user.email, process.env.ALLOWED_EMAIL) || !isSeraUser(user.email)) notFound();
  return user;
}
