import { describe, expect, it } from 'vitest';
import {
  MAX_UPLOAD_BYTES, MIN_SHORT_PX, REENCODE_OVER_BYTES, baseName, decodedLength, fitWithin, hex, isJpeg, kindOf,
  needsReencode, parseUploadBody, runPool, toBase64,
} from './upload';

const SHA = 'a'.repeat(64);
const jpeg = (n: number) => {
  const b = new Uint8Array(n);
  b[0] = 0xff; b[1] = 0xd8; b[2] = 0xff;
  return b;
};

describe('kindOf', () => {
  it('knows zips by name or type', () => {
    expect(kindOf('gotrade_order_summary_screenshots.zip')).toBe('zip');
    expect(kindOf('archive', 'application/x-zip-compressed')).toBe('zip');
  });
  it('knows pictures by name or type', () => {
    expect(kindOf('WhatsApp Image 2026-10-07 at 10.14.45 PM.jpeg')).toBe('image');
    expect(kindOf('shot.PNG')).toBe('image');
    expect(kindOf('blob', 'image/webp')).toBe('image');
  });
  it('refuses everything else, HEIC included', () => {
    expect(kindOf('IMG_0001.HEIC', 'image/heic')).toBe('other');
    expect(kindOf('notes.txt', 'text/plain')).toBe('other');
  });
});

describe('baseName', () => {
  it('drops the folders a zip keeps', () => {
    expect(baseName('gotrade/WhatsApp Image 1.jpeg')).toBe('WhatsApp Image 1.jpeg');
    expect(baseName('one.jpg')).toBe('one.jpg');
  });
});

describe('isJpeg / needsReencode', () => {
  it('sends a small JPEG as it is', () => {
    expect(isJpeg(jpeg(60_000))).toBe(true);
    expect(needsReencode(jpeg(60_000))).toBe(false);
  });
  it('re-encodes a big JPEG or anything that is not a JPEG', () => {
    expect(needsReencode(jpeg(REENCODE_OVER_BYTES + 1))).toBe(true);
    expect(needsReencode(new Uint8Array([0x89, 0x50, 0x4e, 0x47]))).toBe(true);
    expect(isJpeg(new Uint8Array([0xff, 0xd8]))).toBe(false);
  });
});

describe('fitWithin', () => {
  it('keeps a phone screenshot as it is', () => {
    expect(fitWithin(739, 1600)).toEqual({ width: 739, height: 1600 });
  });
  it('shrinks the long side to the limit', () => {
    expect(fitWithin(3000, 6000, 2400)).toEqual({ width: 1200, height: 2400 });
  });
  it('never takes the short side under 560 px, and never scales up', () => {
    expect(MIN_SHORT_PX).toBe(560);
    // a very tall capture: 2400 on the long side would leave 480 px; stop at 560 instead
    expect(fitWithin(600, 3000, 2400)).toEqual({ width: 560, height: 2800 });
    // already narrower than 560: left as it is
    expect(fitWithin(500, 3000, 2400)).toEqual({ width: 500, height: 3000 });
  });
});

describe('toBase64 / decodedLength / hex', () => {
  it('matches Node for bytes past one chunk', () => {
    const bytes = Uint8Array.from({ length: 70_000 }, (_, i) => (i * 31) % 256);
    const b64 = toBase64(bytes);
    expect(b64).toBe(Buffer.from(bytes).toString('base64'));
    expect(decodedLength(b64)).toBe(70_000);
  });
  it('counts padding', () => {
    expect(decodedLength('QQ==')).toBe(1);
    expect(decodedLength('QUI=')).toBe(2);
    expect(decodedLength('QUJD')).toBe(3);
  });
  it('writes digests as lower-case hex', () => {
    expect(hex(new Uint8Array([0, 15, 255]).buffer)).toBe('000fff');
  });
});

describe('runPool', () => {
  it('runs every item, never more than the limit at once', async () => {
    let live = 0;
    let peak = 0;
    const done: number[] = [];
    await runPool([1, 2, 3, 4, 5, 6, 7], 3, async n => {
      live += 1;
      peak = Math.max(peak, live);
      await new Promise(r => setTimeout(r, 5 + (n % 3)));
      done.push(n);
      live -= 1;
    });
    expect(peak).toBe(3);
    expect(done.sort()).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });
  it('is a no-op on nothing', async () => {
    let calls = 0;
    await runPool([], 3, async () => { calls += 1; });
    expect(calls).toBe(0);
  });
});

describe('parseUploadBody', () => {
  it('accepts a base64 picture and a hex digest, lower-casing the digest', () => {
    expect(parseUploadBody({ image: 'QUJD', sha256: SHA.toUpperCase() })).toEqual({ ok: true, image: 'QUJD', sha256: SHA });
  });
  it('refuses malformed bodies with 400', () => {
    expect(parseUploadBody(null)).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody([])).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'QUJD' })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'QUJD', sha256: 'abc' })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: '', sha256: SHA })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'data:image/jpeg;base64,QUJD', sha256: SHA })).toEqual({ ok: false, status: 400 });
    expect(parseUploadBody({ image: 'QU*D', sha256: SHA })).toEqual({ ok: false, status: 400 });
  });
  it('refuses a picture over 1.5 MB with 413', () => {
    const big = 'A'.repeat(Math.ceil(((MAX_UPLOAD_BYTES + 3) * 4) / 3 / 4) * 4);
    expect(parseUploadBody({ image: big, sha256: SHA })).toEqual({ ok: false, status: 413 });
  });
});
