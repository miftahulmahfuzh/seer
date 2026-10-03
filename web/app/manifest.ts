import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Seer',
    short_name: 'Seer',
    description: 'Up to four US stock picks for the next session, with limit, take-profit and stop-loss.',
    start_url: '/',
    display: 'standalone',
    background_color: '#f47862',
    theme_color: '#e6e2d6',
    icons: [
      { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' },
      { src: '/apple-icon', sizes: '180x180', type: 'image/png' },
    ],
  };
}
