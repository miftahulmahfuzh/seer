import { ChevronRight, UserX } from 'lucide-react';
import { redirect } from 'next/navigation';
import { currentUser, signIn } from '@/auth';
import s from './signin.module.css';

const WORDS = ['Strategic', 'Econometric', 'Ensemble', 'Resolver', 'Patience', 'Discipline', 'Risk', 'Limits', 'Targets', 'Stops', 'Signal'];

export default async function SignIn({ searchParams }: { searchParams: Promise<{ denied?: string; error?: string }> }) {
  if (await currentUser()) redirect('/');
  const { denied, error } = await searchParams;
  const refused = denied !== undefined || error === 'AccessDenied';

  return (
    <main className={s.splash}>
      <div className={s.art} aria-hidden="true">
        <div className={s.words}>{WORDS.map(w => <span key={w}>{w}</span>)}</div>
        <svg viewBox="0 0 414 896" className={s.star}>
          <path d="M120 300 Q120 600 400 600 Q120 600 120 900 Q120 600 -160 600 Q120 600 120 300 Z" fill="var(--splash-star)" />
          <line x1="120" x2="120" y1="300" y2="896" stroke="var(--splash)" strokeWidth="1" />
          <line x1="0" x2="400" y1="600" y2="600" stroke="var(--splash)" strokeWidth="1" />
        </svg>
        <span className={s.mark}>Seer.</span>
      </div>
      <h1 className={s.srOnly}>Seer sign-in</h1>

      <div className={s.bottom}>
        {refused && (
          <div className={s.refused} role="alert">
            <span className={s.refusedIcon}><UserX size={20} /></span>
            <div className={s.refusedText}>
              <span className={s.refusedTitle}>This account isn’t allowed</span>
              {denied && <span className={s.refusedSub}>{denied}</span>}
              <span className={s.refusedSub}>Seer is private to one Google account. Try again with that one.</span>
            </div>
          </div>
        )}
        <form action={async () => { 'use server'; await signIn('google', { redirectTo: '/' }); }}>
          <button type="submit" className={s.google} data-tip="Sign in with Google" aria-label="Sign in with Google">
            <span className={s.gdot}>
              <svg width="26" height="26" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
                <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
                <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
              </svg>
            </span>
            <span className={s.chev}><ChevronRight size={24} /></span>
          </button>
        </form>
      </div>
    </main>
  );
}
