// Pure upload rules for /sean/trades, shared by the browser uploader (Uploader.tsx) and
// POST /api/sean/orders. No data access, no DOM: tested in upload.test.ts.

/** Shared contract C: the decoded picture may be at most 1.5 MB. */
export const MAX_UPLOAD_BYTES = 1.5 * 1024 * 1024;
/** A JPEG this size or smaller goes up as it is; anything bigger is re-encoded first. */
export const REENCODE_OVER_BYTES = 1_000_000;
/** How many pictures are read at once. Each takes 10-40 s at the model. */
export const CONCURRENCY = 3;
/** Re-encoding also shrinks the long side to at most this many pixels (a phone screenshot is ~1600). */
export const MAX_SIDE_PX = 2400;
/**
 * ...but never takes the short side below this (Phase 1 handoff: run-insights read 108/108 at a
 * 560 px short edge; smaller pictures push prompt_tokens toward the reader's token floor).
 */
export const MIN_SHORT_PX = 560;

export type FileKind = 'zip' | 'image' | 'other';

const IMAGE_NAME = /\.(jpe?g|png|webp)$/i;
const IMAGE_TYPE = /^image\/(jpeg|png|webp)$/;
const ZIP_TYPES = new Set(['application/zip', 'application/x-zip-compressed']);

/** What a picked file (or a zip entry, which has no type) is, by its name and MIME type. */
export function kindOf(name: string, type = ''): FileKind {
  if (/\.zip$/i.test(name) || ZIP_TYPES.has(type)) return 'zip';
  if (IMAGE_NAME.test(name) || IMAGE_TYPE.test(type)) return 'image';
  return 'other';
}

/** 'gotrade/WhatsApp Image 1.jpeg' -> 'WhatsApp Image 1.jpeg'. */
export function baseName(path: string): string {
  const parts = path.split('/').filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : path;
}

/** A JPEG starts with FF D8 FF. */
export function isJpeg(bytes: Uint8Array): boolean {
  return bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

/** The model is sent a JPEG: re-encode anything that is not one, or a JPEG over ~1 MB. */
export function needsReencode(bytes: Uint8Array): boolean {
  return !isJpeg(bytes) || bytes.length > REENCODE_OVER_BYTES;
}

/**
 * The size to draw at: unchanged when the long side fits, else scaled down toward `max` on the
 * long side -- but never so far that the short side drops under `minShort`, and never up.
 */
export function fitWithin(
  width: number,
  height: number,
  max = MAX_SIDE_PX,
  minShort = MIN_SHORT_PX,
): { width: number; height: number } {
  const long = Math.max(width, height);
  if (long <= max) return { width, height };
  const short = Math.min(width, height);
  const k = Math.min(1, Math.max(max / long, minShort / short));
  if (k >= 1) return { width, height };
  return { width: Math.max(1, Math.round(width * k)), height: Math.max(1, Math.round(height * k)) };
}

/** Bytes -> base64 (no data: prefix), in chunks so a large picture does not overflow the call stack. */
export function toBase64(bytes: Uint8Array): string {
  let bin = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

/** A digest as lower-case hex. */
export function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Runs `worker` over `items`, at most `limit` at a time, in order of start. Resolves when every
 * item is done; rejects if a worker throws (the uploader's worker never does).
 */
export async function runPool<T>(
  items: readonly T[],
  limit: number,
  worker: (item: T, index: number) => Promise<void>,
): Promise<void> {
  let next = 0;
  const lanes = Math.max(1, Math.min(Math.floor(limit), items.length));
  await Promise.all(
    Array.from({ length: lanes }, async () => {
      while (next < items.length) {
        const i = next++;
        await worker(items[i], i);
      }
    }),
  );
}

/** How many bytes a base64 string decodes to. */
export function decodedLength(b64: string): number {
  const pad = b64.endsWith('==') ? 2 : b64.endsWith('=') ? 1 : 0;
  return Math.floor((b64.length * 3) / 4) - pad;
}

const SHA256_HEX = /^[0-9a-f]{64}$/;
const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;

export type UploadBody =
  | { ok: true; image: string; sha256: string }
  | { ok: false; status: 400 | 413 };

/**
 * The route's request check (shared contract C): `{ image: base64 without a data: prefix,
 * sha256: hex }`. 413 when the picture is over MAX_UPLOAD_BYTES, 400 for anything malformed.
 * The size is checked before the character scan, so an oversized body is refused cheaply.
 */
export function parseUploadBody(body: unknown): UploadBody {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return { ok: false, status: 400 };
  const { image, sha256 } = body as { image?: unknown; sha256?: unknown };
  if (typeof image !== 'string' || typeof sha256 !== 'string') return { ok: false, status: 400 };
  const sha = sha256.trim().toLowerCase();
  if (!SHA256_HEX.test(sha)) return { ok: false, status: 400 };
  if (image.length === 0 || image.length % 4 !== 0) return { ok: false, status: 400 };
  if (decodedLength(image) > MAX_UPLOAD_BYTES) return { ok: false, status: 413 };
  if (!BASE64.test(image)) return { ok: false, status: 400 };
  return { ok: true, image, sha256: sha };
}
