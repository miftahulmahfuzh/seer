'use client';

import { CircleAlert, CircleCheck, CircleDashed, CopyCheck, ImagePlus, ListX, LoaderCircle, RotateCcw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { ZipError, readZip } from '@/lib/sean/unzip';
import { refreshPnl } from './actions';
import {
  CONCURRENCY, MAX_UPLOAD_BYTES, baseName, fitWithin, hex, kindOf, needsReencode, runPool, toBase64,
} from './upload';
import {
  NOT_A_PICTURE, OFFLINE, READING, SAME_AS_ANOTHER, TOO_LARGE_PICTURE, WAITING, ZIP_EMPTY, ZIP_UNREADABLE,
  batchSummary, progressLine, readResponse, type UploadItem, type UploadOutcome, type UploadState,
} from './view';
import s from './trades.module.css';

type Bytes = Uint8Array<ArrayBuffer>;
type Job = { key: string; name: string; bytes: Bytes };

const ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp,.zip,application/zip,application/x-zip-compressed';
const ADD_LABEL = 'Add Order Summary screenshots or a zip';
const RETRY_LABEL = 'Try the ones that failed again';
const CLEAR_LABEL = 'Clear this list';

/** Draws the picture onto a canvas and writes it back as a JPEG, long side at most MAX_SIDE_PX. */
async function reencode(bytes: Bytes, quality: number): Promise<Bytes> {
  const bitmap = await createImageBitmap(new Blob([bytes]));
  try {
    const { width, height } = fitWithin(bitmap.width, bitmap.height);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('no 2d canvas');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(bitmap, 0, 0, width, height);
    const blob = await new Promise<Blob | null>(done => canvas.toBlob(done, 'image/jpeg', quality));
    if (!blob) throw new Error('JPEG encode failed');
    return new Uint8Array(await blob.arrayBuffer());
  } finally {
    bitmap.close();
  }
}

/** A small JPEG goes as it is; anything else is re-encoded, a second time smaller if it must. */
async function prepare(bytes: Bytes): Promise<Bytes> {
  if (!needsReencode(bytes)) return bytes;
  const first = await reencode(bytes, 0.85);
  return first.length <= MAX_UPLOAD_BYTES ? first : reencode(bytes, 0.7);
}

async function send(image: string, sha256: string): Promise<UploadOutcome> {
  let res: Response;
  try {
    res = await fetch('/api/sean/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image, sha256 }),
    });
  } catch {
    return OFFLINE;
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  return readResponse(res.status, body);
}

/** One picture end to end. `seen` holds this batch's digests, so a picture picked twice is sent once. */
async function processJob(job: Job, seen: Set<string>): Promise<UploadOutcome> {
  let bytes: Bytes;
  try {
    bytes = await prepare(job.bytes);
  } catch {
    return NOT_A_PICTURE;
  }
  if (bytes.length > MAX_UPLOAD_BYTES) return TOO_LARGE_PICTURE;
  const sha = hex(await crypto.subtle.digest('SHA-256', bytes));
  if (seen.has(sha)) return SAME_AS_ANOTHER;
  seen.add(sha);
  return send(toBase64(bytes), sha);
}

const rejected = (key: string, name: string, o: UploadOutcome): UploadItem => ({ key, name, ...o });

/** Picked files -> pictures to read (zips opened in the browser) plus the files refused outright. */
async function expand(files: File[], batch: number): Promise<{ jobs: Job[]; rejects: UploadItem[] }> {
  const jobs: Job[] = [];
  const rejects: UploadItem[] = [];
  let n = 0;
  const key = () => `${batch}-${n++}`;
  for (const f of files) {
    const kind = kindOf(f.name, f.type);
    if (kind === 'image') {
      jobs.push({ key: key(), name: f.name, bytes: new Uint8Array(await f.arrayBuffer()) });
    } else if (kind === 'zip') {
      let pictures: Awaited<ReturnType<typeof readZip>>;
      try {
        // Phase 1's reader: skips folders and macOS litter, keeps only picture names, checks CRCs.
        pictures = await readZip(new Uint8Array(await f.arrayBuffer()), { accept: name => kindOf(name) === 'image' });
      } catch (e) {
        // ZipError messages are plain words ("This zip file is damaged."); anything else is generic.
        rejects.push(rejected(key(), f.name, e instanceof ZipError ? { ...ZIP_UNREADABLE, message: e.message } : ZIP_UNREADABLE));
        continue;
      }
      if (pictures.length === 0) rejects.push(rejected(key(), f.name, ZIP_EMPTY));
      for (const e of pictures) jobs.push({ key: key(), name: baseName(e.name), bytes: new Uint8Array(e.bytes) });
    } else {
      rejects.push(rejected(key(), f.name, NOT_A_PICTURE));
    }
  }
  return { jobs, rejects };
}

function StateIcon({ state }: { state: UploadState }) {
  switch (state) {
    case 'reading':
      return <LoaderCircle size={20} strokeWidth={1.75} className={s.spin} aria-hidden="true" />;
    case 'saved':
      return <CircleCheck size={20} strokeWidth={1.75} aria-hidden="true" />;
    case 'duplicate':
      return <CopyCheck size={20} strokeWidth={1.75} aria-hidden="true" />;
    case 'failed':
      return <CircleAlert size={20} strokeWidth={1.75} aria-hidden="true" />;
    default:
      return <CircleDashed size={20} strokeWidth={1.5} aria-hidden="true" />;
  }
}

/**
 * Trades' uploader: pick or drop Order Summary screenshots or the zip; three are read at a time,
 * each with its own status row. When a batch ends the page reloads its order list and the engine
 * is asked (best effort) to redo the daily profit and loss.
 */
export function Uploader() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const retryable = useRef(new Map<string, Job>());
  const batchNo = useRef(0);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [summary, setSummary] = useState('');

  // Leaving mid-batch drops the pictures not yet read: ask first.
  useEffect(() => {
    if (!busy) return;
    const hold = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', hold);
    return () => window.removeEventListener('beforeunload', hold);
  }, [busy]);

  const update = (key: string, patch: Partial<UploadItem>) =>
    setItems(prev => prev.map(it => (it.key === key ? { ...it, ...patch } : it)));

  async function run(jobs: Job[], refused: number) {
    const seen = new Set<string>();
    const tally = { saved: 0, duplicate: 0, failed: refused };
    await runPool(jobs, CONCURRENCY, async job => {
      update(job.key, { state: 'reading', message: READING, retry: false });
      let out: UploadOutcome;
      try {
        out = await processJob(job, seen);
      } catch {
        out = OFFLINE;
      }
      tally[out.state] += 1;
      if (out.state === 'failed' && out.retry) retryable.current.set(job.key, job);
      else retryable.current.delete(job.key);
      update(job.key, out);
    });
    setSummary(batchSummary(tally));
    setBusy(false);
    if (tally.saved > 0) {
      router.refresh();
      refreshPnl().catch(() => undefined);
    }
  }

  async function start(files: File[]) {
    if (busy || files.length === 0) return;
    setBusy(true);
    setSummary('');
    retryable.current.clear();
    batchNo.current += 1;
    try {
      const { jobs, rejects } = await expand(files, batchNo.current);
      setItems([
        ...jobs.map((j): UploadItem => ({ key: j.key, name: j.name, state: 'waiting', message: WAITING, retry: false })),
        ...rejects,
      ]);
      await run(jobs, rejects.length);
    } catch {
      setSummary("Those files couldn't be opened. Try picking them again.");
      setBusy(false);
    }
  }

  async function retry() {
    const jobs = [...retryable.current.values()];
    if (busy || jobs.length === 0) return;
    setBusy(true);
    setSummary('');
    for (const j of jobs) update(j.key, { state: 'waiting', message: WAITING, retry: false });
    await run(jobs, 0);
  }

  function clear() {
    retryable.current.clear();
    setItems([]);
    setSummary('');
  }

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = '';
    void start(files);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    void start(Array.from(e.dataTransfer.files));
  }

  const canRetry = !busy && items.some(i => i.state === 'failed' && i.retry);
  const status = busy ? progressLine(items) : summary;

  return (
    <div className={s.uploader}>
      <div
        className={`${s.drop} ${over ? s.dropOver : ''}`}
        onDragOver={e => { e.preventDefault(); if (!busy) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
      >
        <button type="button" className={`icon-btn ${s.add}`} disabled={busy}
          onClick={() => input.current?.click()} aria-label={ADD_LABEL} data-tip={ADD_LABEL}>
          {busy
            ? <LoaderCircle size={24} strokeWidth={1.75} className={s.spin} />
            : <ImagePlus size={24} strokeWidth={1.75} />}
        </button>
        <div className={s.dropText}>
          <p className={s.dropLead}>Drop the screenshots here, or the whole zip.</p>
          <p className={s.dropHint}>As many as you like. Sean reads each one, keeps the numbers and throws the picture away.</p>
        </div>
        <input ref={input} type="file" multiple accept={ACCEPT} className={s.sr}
          tabIndex={-1} aria-hidden="true" onChange={onPick} />
      </div>

      {(status || items.length > 0) && (
        <div className={s.bar}>
          <p className={s.progress} role="status" aria-live="polite">{status}</p>
          <div className={s.barActions}>
            {canRetry && (
              <button type="button" className="icon-btn sm" onClick={() => void retry()}
                aria-label={RETRY_LABEL} data-tip={RETRY_LABEL}>
                <RotateCcw size={18} strokeWidth={1.5} />
              </button>
            )}
            {!busy && items.length > 0 && (
              <button type="button" className="icon-btn sm" onClick={clear}
                aria-label={CLEAR_LABEL} data-tip={CLEAR_LABEL}>
                <ListX size={18} strokeWidth={1.5} />
              </button>
            )}
          </div>
        </div>
      )}

      {items.length > 0 && (
        <ul className={s.items}>
          {items.map(it => (
            <li key={it.key} className={`${s.item} ${it.state === 'failed' ? s.failed : ''}`}>
              <span className={s.itemIcon}><StateIcon state={it.state} /></span>
              <span className={s.itemName}>{it.name}</span>
              <span className={s.itemMsg}>{it.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
