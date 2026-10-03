import type { Metadata, Viewport } from 'next';
import { Outfit } from 'next/font/google';
import { TooltipLayer } from '@/components/TooltipLayer';
import './globals.css';

const outfit = Outfit({ subsets: ['latin'], weight: ['300', '400', '500', '600'], variable: '--font-outfit' });

export const metadata: Metadata = {
  title: 'Seer',
  description: 'Strategic Econometric Ensemble Resolver: up to four US stock picks for the next session.',
  appleWebApp: { capable: true, title: 'Seer', statusBarStyle: 'black-translucent' },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#e6e2d6' },
    { media: '(prefers-color-scheme: dark)', color: '#141311' },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={outfit.variable}>
      <body>
        {children}
        <TooltipLayer />
      </body>
    </html>
  );
}
