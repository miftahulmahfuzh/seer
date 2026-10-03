import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';
import { isAllowed } from '@/lib/allow';

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: 'jwt' },
  pages: { signIn: '/signin', error: '/signin' },
  callbacks: {
    signIn({ user }) {
      if (isAllowed(user.email, process.env.ALLOWED_EMAIL)) return true;
      return `/signin?denied=${encodeURIComponent(user.email ?? '')}`;
    },
  },
});

/** The signed-in, allowlisted user, or null. */
export async function currentUser() {
  const session = await auth();
  const email = session?.user?.email;
  return isAllowed(email, process.env.ALLOWED_EMAIL) ? session!.user! : null;
}
