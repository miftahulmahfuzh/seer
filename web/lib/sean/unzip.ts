/**
 * Read a .zip of screenshots in the browser, with no dependency: the owner can hand Sean the zip
 * WhatsApp gave him (gotrade_order_summary_screenshots.zip: 30 JPEGs, stored) as is.
 *
 * Reads the central directory (so entries written with a trailing data descriptor work), then
 * each entry: method 0 (stored) is copied, method 8 (deflate) goes through `inflateRaw`, which
 * defaults to the browser's DecompressionStream('deflate-raw'). Tests and the smoke script pass
 * node:zlib's inflateRawSync instead (Node 20.11 has no 'deflate-raw' DecompressionStream).
 * Every entry's size and CRC-32 are checked. Directories, __MACOSX/, AppleDouble "._" files and
 * .DS_Store are skipped. Zip64, encryption and other methods are refused in plain words.
 *
 * Pure: no imports.
 */

export class ZipError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ZipError';
  }
}

export type ZipEntry = { name: string; bytes: Uint8Array };
export type InflateRaw = (data: Uint8Array) => Promise<Uint8Array>;

/** Raw-deflate with the browser's own DecompressionStream. */
export const inflateRawWeb: InflateRaw = async data => {
  const stream = new Blob([data.slice()]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
};

/** Files Sean can read as a receipt. */
export const IMAGE_NAME = /\.(jpe?g|png|webp)$/i;

/** The file name without its folders: 'shots/a.jpeg' -> 'a.jpeg'. */
export function baseName(name: string): string {
  return name.slice(name.lastIndexOf('/') + 1);
}

/** Entries that are never content: folders and macOS litter. */
export function isJunkEntry(name: string): boolean {
  const base = baseName(name);
  return name.endsWith('/') || name.startsWith('__MACOSX/') || base.startsWith('._') || base === '.DS_Store';
}

let CRC_TABLE: Uint32Array | null = null;

/** CRC-32 (IEEE), as zip stores it. */
export function crc32(bytes: Uint8Array): number {
  if (CRC_TABLE === null) {
    CRC_TABLE = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c >>> 0;
    }
  }
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const SIG_EOCD = 0x06054b50;
const SIG_CENTRAL = 0x02014b50;
const SIG_LOCAL = 0x04034b50;
const DAMAGED = 'This zip file is damaged.';
const ZIP64 = 'This zip is too large to open here.';

function findEndOfCentralDirectory(view: DataView): number {
  const last = view.byteLength - 22;
  const first = Math.max(0, last - 0xffff);
  for (let i = last; i >= first; i--) {
    if (view.getUint32(i, true) === SIG_EOCD) return i;
  }
  throw new ZipError('This is not a zip file.');
}

/**
 * Every content entry `accept` keeps (all of them by default), in the zip's own order.
 * Throws ZipError with a plain-words message when the zip cannot be read.
 */
export async function readZip(
  input: ArrayBuffer | Uint8Array,
  opts: { inflateRaw?: InflateRaw; accept?: (name: string) => boolean } = {},
): Promise<ZipEntry[]> {
  const buf = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (buf.byteLength < 22) throw new ZipError('This is not a zip file.');
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const inflate = opts.inflateRaw ?? inflateRawWeb;
  const accept = opts.accept ?? (() => true);
  const utf8 = new TextDecoder('utf-8');

  const eocd = findEndOfCentralDirectory(view);
  const count = view.getUint16(eocd + 10, true);
  const dirSize = view.getUint32(eocd + 12, true);
  const dirOffset = view.getUint32(eocd + 16, true);
  if (count === 0xffff || dirSize === 0xffffffff || dirOffset === 0xffffffff) throw new ZipError(ZIP64);
  if (dirOffset + dirSize > eocd) throw new ZipError(DAMAGED);

  const out: ZipEntry[] = [];
  let p = dirOffset;
  for (let i = 0; i < count; i++) {
    if (p + 46 > eocd || view.getUint32(p, true) !== SIG_CENTRAL) throw new ZipError(DAMAGED);
    const flags = view.getUint16(p + 8, true);
    const method = view.getUint16(p + 10, true);
    const crc = view.getUint32(p + 16, true);
    const compressedSize = view.getUint32(p + 20, true);
    const size = view.getUint32(p + 24, true);
    const nameLength = view.getUint16(p + 28, true);
    const extraLength = view.getUint16(p + 30, true);
    const commentLength = view.getUint16(p + 32, true);
    const localOffset = view.getUint32(p + 42, true);
    const name = utf8.decode(buf.subarray(p + 46, p + 46 + nameLength));
    p += 46 + nameLength + extraLength + commentLength;

    if (isJunkEntry(name) || !accept(name)) continue;
    if (flags & 1) throw new ZipError(`${baseName(name)} is password-protected.`);
    if (compressedSize === 0xffffffff || size === 0xffffffff || localOffset === 0xffffffff) throw new ZipError(ZIP64);
    if (localOffset + 30 > buf.byteLength || view.getUint32(localOffset, true) !== SIG_LOCAL) {
      throw new ZipError(DAMAGED);
    }
    const start = localOffset + 30 + view.getUint16(localOffset + 26, true) + view.getUint16(localOffset + 28, true);
    const end = start + compressedSize;
    if (end > buf.byteLength) throw new ZipError(DAMAGED);
    const data = buf.subarray(start, end);

    let bytes: Uint8Array;
    if (method === 0) bytes = data.slice();
    else if (method === 8) {
      try {
        bytes = await inflate(data);
      } catch {
        throw new ZipError(`${baseName(name)} is damaged inside the zip.`);
      }
    } else throw new ZipError(`${baseName(name)} is packed in a way this page cannot open.`);

    if (bytes.length !== size || crc32(bytes) !== crc) throw new ZipError(`${baseName(name)} is damaged inside the zip.`);
    out.push({ name, bytes });
  }
  return out;
}
