import { ImageResponse } from 'next/og';

export const size = { width: 180, height: 180 };
export const contentType = 'image/png';

// Home-screen icon: the splash's four-point star on coral. iOS rounds the corners itself.
export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', background: '#f47862' }}>
        <svg width="180" height="180" viewBox="0 0 100 100">
          <path d="M50 14 Q50 50 86 50 Q50 50 50 86 Q50 50 14 50 Q50 50 50 14 Z" fill="#f8d07f" />
        </svg>
      </div>
    ),
    size,
  );
}
