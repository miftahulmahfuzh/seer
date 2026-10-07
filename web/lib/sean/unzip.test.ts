import { deflateRawSync, inflateRawSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { IMAGE_NAME, ZipError, baseName, crc32, isJunkEntry, readZip, type InflateRaw } from './unzip';

// Node 20.11 has no DecompressionStream('deflate-raw'); the browser does. Tests inject zlib.
const inflateRaw: InflateRaw = async data => new Uint8Array(inflateRawSync(data));
const text = (b: Uint8Array) => new TextDecoder().decode(b);
const bytes = (s: string) => new TextEncoder().encode(s);

/**
 * Written by Python's zipfile (not by this file's own writer below, so reader and writer cannot
 * share a mistake): a folder entry, receipts/a.jpeg (deflate, 'JPEG-ONE ' x 40), receipts/b.png
 * (stored, 'PNG-TWO'), __MACOSX/receipts/._a.jpeg, .DS_Store, notes.txt (deflate, 'hello').
 */
const PYTHON_ZIP = Uint8Array.from(
  atob(
    'UEsDBBQAAAAAAAAAIQAAAAAAAAAAAAAAAAAJAAAAcmVjZWlwdHMvUEsDBBQAAAAIADa2R11VJYDKEAAAAGgBAAAPAAAAcmVjZWlwdHMvYS5qcGVn8wpwddf193NV8Bpl0JIBAFBLAwQUAAAAAAA2tkddkb9MSwcAAAAHAAAADgAAAHJlY2VpcHRzL2IucG5nUE5HLVRXT1BLAwQUAAAAAAA2tkddOZz7BgQAAAAEAAAAGgAAAF9fTUFDT1NYL3JlY2VpcHRzLy5fYS5qcGVnanVua1BLAwQUAAAAAAA2tkddOZz7BgQAAAAEAAAACQAAAC5EU19TdG9yZWp1bmtQSwMEFAAAAAgANrZHXYamEDYHAAAABQAAAAkAAABub3Rlcy50eHTLSM3JyQcAUEsBAhQDFAAAAAAAAAAhAAAAAAAAAAAAAAAAAAkAAAAAAAAAAAAAAIABAAAAAHJlY2VpcHRzL1BLAQIUAxQAAAAIADa2R11VJYDKEAAAAGgBAAAPAAAAAAAAAAAAAACAAScAAAByZWNlaXB0cy9hLmpwZWdQSwECFAMUAAAAAAA2tkddkb9MSwcAAAAHAAAADgAAAAAAAAAAAAAAgAFkAAAAcmVjZWlwdHMvYi5wbmdQSwECFAMUAAAAAAA2tkddOZz7BgQAAAAEAAAAGgAAAAAAAAAAAAAAgAGXAAAAX19NQUNPU1gvcmVjZWlwdHMvLl9hLmpwZWdQSwECFAMUAAAAAAA2tkddOZz7BgQAAAAEAAAACQAAAAAAAAAAAAAAgAHTAAAALkRTX1N0b3JlUEsBAhQDFAAAAAgANrZHXYamEDYHAAAABQAAAAkAAAAAAAAAAAAAAIAB/gAAAG5vdGVzLnR4dFBLBQYAAAAABgAGAGYBAAAsAQAAAAA=',
  ),
  c => c.charCodeAt(0),
);

type Spec = { name: string; data: Uint8Array; method: 0 | 8; descriptor?: boolean; flags?: number };

/** A minimal zip writer for the edge cases Python will not produce on demand. */
function makeZip(files: Spec[]): Uint8Array {
  const chunks: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;
  for (const f of files) {
    const name = bytes(f.name);
    const packed = f.method === 8 ? new Uint8Array(deflateRawSync(f.data)) : f.data;
    const crc = crc32(f.data);
    const flags = (f.flags ?? 0) | (f.descriptor ? 8 : 0);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true);
    local.setUint16(6, flags, true);
    local.setUint16(8, f.method, true);
    local.setUint32(14, f.descriptor ? 0 : crc, true);
    local.setUint32(18, f.descriptor ? 0 : packed.length, true);
    local.setUint32(22, f.descriptor ? 0 : f.data.length, true);
    local.setUint16(26, name.length, true);
    const head = new Uint8Array(local.buffer);
    const descriptor = new DataView(new ArrayBuffer(f.descriptor ? 16 : 0));
    if (f.descriptor) {
      descriptor.setUint32(0, 0x08074b50, true);
      descriptor.setUint32(4, crc, true);
      descriptor.setUint32(8, packed.length, true);
      descriptor.setUint32(12, f.data.length, true);
    }
    const cen = new DataView(new ArrayBuffer(46));
    cen.setUint32(0, 0x02014b50, true);
    cen.setUint16(4, 20, true);
    cen.setUint16(6, 20, true);
    cen.setUint16(8, flags, true);
    cen.setUint16(10, f.method, true);
    cen.setUint32(16, crc, true);
    cen.setUint32(20, packed.length, true);
    cen.setUint32(24, f.data.length, true);
    cen.setUint16(28, name.length, true);
    cen.setUint32(42, offset, true);
    central.push(new Uint8Array(cen.buffer), name);
    for (const c of [head, name, packed, new Uint8Array(descriptor.buffer)]) {
      chunks.push(c);
      offset += c.length;
    }
  }
  const dirSize = central.reduce((n, c) => n + c.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(8, files.length, true);
  end.setUint16(10, files.length, true);
  end.setUint32(12, dirSize, true);
  end.setUint32(16, offset, true);
  const all = [...chunks, ...central, new Uint8Array(end.buffer)];
  const out = new Uint8Array(all.reduce((n, c) => n + c.length, 0));
  let p = 0;
  for (const c of all) {
    out.set(c, p);
    p += c.length;
  }
  return out;
}

describe('readZip', () => {
  it('reads a zip written by a real tool, skipping folders and macOS litter', async () => {
    const entries = await readZip(PYTHON_ZIP, { inflateRaw });
    expect(entries.map(e => e.name)).toEqual(['receipts/a.jpeg', 'receipts/b.png', 'notes.txt']);
    expect(text(entries[0].bytes)).toBe('JPEG-ONE '.repeat(40));
    expect(text(entries[1].bytes)).toBe('PNG-TWO');
    expect(text(entries[2].bytes)).toBe('hello');
  });

  it('keeps only what `accept` keeps', async () => {
    const entries = await readZip(PYTHON_ZIP.buffer, { inflateRaw, accept: n => IMAGE_NAME.test(n) });
    expect(entries.map(e => baseName(e.name))).toEqual(['a.jpeg', 'b.png']);
  });

  it('reads entries whose sizes live in a trailing data descriptor', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('x'.repeat(500)), method: 8, descriptor: true }]);
    const [entry] = await readZip(zip, { inflateRaw });
    expect(text(entry.bytes)).toBe('x'.repeat(500));
  });

  it('refuses a corrupted entry by its CRC', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('receipt'), method: 0 }]);
    zip[30 + 'r.jpg'.length] ^= 0xff;
    await expect(readZip(zip, { inflateRaw })).rejects.toThrow('r.jpg is damaged inside the zip.');
  });

  it('refuses a deflate stream that does not inflate', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('receipt receipt'), method: 8 }]);
    zip.fill(0xff, 30 + 5, 30 + 5 + 4);
    await expect(readZip(zip, { inflateRaw })).rejects.toThrow(ZipError);
  });

  it('refuses password-protected entries and unknown methods in plain words', async () => {
    const locked = makeZip([{ name: 'r.jpg', data: bytes('a'), method: 0, flags: 1 }]);
    await expect(readZip(locked, { inflateRaw })).rejects.toThrow('r.jpg is password-protected.');
    const odd = makeZip([{ name: 'r.jpg', data: bytes('a'), method: 0 }]);
    new DataView(odd.buffer).setUint16(odd.length - 22 - 46 - 5 + 10, 12, true);
    await expect(readZip(odd, { inflateRaw })).rejects.toThrow('r.jpg is packed in a way this page cannot open.');
  });

  it('refuses something that is not a zip', async () => {
    await expect(readZip(bytes('just a jpeg, honestly'), { inflateRaw })).rejects.toThrow('This is not a zip file.');
    await expect(readZip(new Uint8Array(4), { inflateRaw })).rejects.toThrow('This is not a zip file.');
  });

  it('refuses a truncated zip', async () => {
    const zip = makeZip([{ name: 'r.jpg', data: bytes('receipt'), method: 0 }]);
    const cut = zip.slice(10);
    await expect(readZip(cut, { inflateRaw })).rejects.toThrow(ZipError);
  });
});

describe('helpers', () => {
  it('computes the standard CRC-32', () => {
    expect(crc32(bytes('123456789'))).toBe(0xcbf43926);
    expect(crc32(new Uint8Array(0))).toBe(0);
  });
  it('knows junk entries and image names', () => {
    expect(['a/', '__MACOSX/a.jpg', 'x/._a.jpg', '.DS_Store', 'x/.DS_Store'].every(isJunkEntry)).toBe(true);
    expect(isJunkEntry('shots/WhatsApp Image 2026-10-07 at 10.14.45 PM.jpeg')).toBe(false);
    expect(['a.jpg', 'a.JPEG', 'a.png', 'a.webp'].every(n => IMAGE_NAME.test(n))).toBe(true);
    expect(IMAGE_NAME.test('a.txt')).toBe(false);
  });
});
