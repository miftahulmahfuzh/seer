// Live check of Sean's screenshot reader against real Gotrade Order Summary screenshots.
//
// NOT run in CI: it calls glm-4.6v (spends tokens) and needs the reader's keys. It runs the very
// modules the upload route runs (lib/sean/readOrder.ts and friends), through vite-node, which
// ships with vitest and understands TypeScript and the extensionless imports Node 20 cannot.
//
// From web/:
//   npx vite-node scripts/sean-vision-smoke.mjs -- <zip | folder | image ...> \
//       [--truth ../.workflows/plan/sean-gotrade-tracker/screenshots_truth.json] \
//       [--env .env.local] [--limit N]
//
// Example, the owner's 30 receipts:
//   npx vite-node scripts/sean-vision-smoke.mjs -- ../../gotrade_order_summary_screenshots.zip \
//       --truth ../.workflows/plan/sean-gotrade-tracker/screenshots_truth.json
//
// Prints one line per picture (what was read, prompt tokens against the floor, tries, seconds),
// then a summary. With --truth it compares symbol, side, date/time, shares, amount, the three
// fees and total to the hand-checked transcription. Exits 1 on any failure or mismatch.
import { readFile, readdir, stat } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';
import { inflateRawSync } from 'node:zlib';
import { readOrder, visionDeps } from '../lib/sean/readOrder.ts';
import { IMAGE_NAME, baseName, readZip } from '../lib/sean/unzip.ts';
import { visionConfigFromEnv } from '../lib/sean/vision.ts';

const CONCURRENCY = 3;

function parseArgs(argv) {
  const out = { inputs: [], truth: null, env: '.env.local', limit: Infinity };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--') continue;
    else if (a === '--truth') out.truth = argv[++i];
    else if (a === '--env') out.env = argv[++i];
    else if (a === '--limit') out.limit = Number(argv[++i]);
    else out.inputs.push(a);
  }
  return out;
}

/** KEY=value lines into process.env, without overriding what is already set. */
async function loadEnvFile(path) {
  let text;
  try {
    text = await readFile(path, 'utf8');
  } catch {
    return;
  }
  for (const line of text.split(/\r?\n/)) {
    const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/.exec(line);
    if (!m || line.trimStart().startsWith('#')) continue;
    const value = m[2].replace(/^(['"])(.*)\1$/, '$2');
    if (process.env[m[1]] === undefined) process.env[m[1]] = value;
  }
}

/** Every picture named by the arguments, as { name, bytes }. */
async function collect(inputs) {
  const pictures = [];
  for (const input of inputs) {
    const path = resolve(input);
    const info = await stat(path);
    if (info.isDirectory()) {
      for (const name of (await readdir(path)).sort()) {
        if (IMAGE_NAME.test(name)) pictures.push({ name, bytes: new Uint8Array(await readFile(join(path, name))) });
      }
    } else if (path.toLowerCase().endsWith('.zip')) {
      const entries = await readZip(new Uint8Array(await readFile(path)), {
        inflateRaw: async data => new Uint8Array(inflateRawSync(data)),
        accept: name => IMAGE_NAME.test(name),
      });
      for (const e of entries) pictures.push({ name: baseName(e.name), bytes: e.bytes });
    } else {
      pictures.push({ name: basename(path), bytes: new Uint8Array(await readFile(path)) });
    }
  }
  return pictures;
}

const near = (a, b, tol) => typeof a === 'number' && typeof b === 'number' && Math.abs(a - b) <= tol;

/** Differences between what was read and the hand-checked row. */
function compare(order, t) {
  const diffs = [];
  const want = {
    symbol: t.ticker,
    side: t.side,
    executedAt: `${t.date}T${t.time_hhmm}:00+07:00`,
  };
  for (const [k, v] of Object.entries(want)) if (order[k] !== v) diffs.push(`${k} ${order[k]} != ${v}`);
  const nums = [
    ['shares', order.shares, t.shares_num, 1e-9],
    ['price', order.price, t.price_num, 1e-6],
    ['amountUsd', order.amountUsd, t.amount_num, 0.001],
    ['tradingFeeUsd', order.tradingFeeUsd, Math.abs(t.trading_fee_num), 0.001],
    ['regulatoryFeeUsd', order.regulatoryFeeUsd, Math.abs(t.regulatory_fee_num), 0.001],
    ['ppnUsd', order.ppnUsd, Math.abs(t.ppn_num), 0.001],
    ['totalUsd', order.totalUsd, t.total_num, 0.001],
  ];
  for (const [k, got, exp, tol] of nums) if (!near(got, exp, tol)) diffs.push(`${k} ${got} != ${exp}`);
  if ((order.netProfitUsd ?? null) !== (t.net_profit_num ?? null)) diffs.push(`netProfitUsd ${order.netProfitUsd} != ${t.net_profit_num}`);
  if (order.fills.length !== t.partial_fills.length) diffs.push(`fills ${order.fills.length} != ${t.partial_fills.length}`);
  return diffs;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.inputs.length === 0) {
    console.error('usage: npx vite-node scripts/sean-vision-smoke.mjs -- <zip|folder|image...> [--truth file] [--env file] [--limit N]');
    process.exit(2);
  }
  await loadEnvFile(resolve(args.env));
  const cfg = visionConfigFromEnv(process.env);
  if (cfg === null) {
    console.error('LLM_API_KEY, LLM_VISION_BASE_URL and LLM_VISION_MODEL must be set (and not the /api/anthropic URL).');
    process.exit(2);
  }
  const truth = args.truth ? new Map(JSON.parse(await readFile(resolve(args.truth), 'utf8')).map(r => [r.filename, r])) : null;
  const pictures = (await collect(args.inputs)).slice(0, args.limit);
  console.log(`${pictures.length} picture(s), model ${cfg.model}, ${CONCURRENCY} at a time`);

  const deps = visionDeps(cfg);
  const results = new Array(pictures.length);
  let next = 0;
  async function worker() {
    while (next < pictures.length) {
      const i = next++;
      const p = pictures[i];
      const started = Date.now();
      const out = await readOrder(deps, Buffer.from(p.bytes).toString('base64'));
      const seconds = ((Date.now() - started) / 1000).toFixed(1);
      const tokens = out.promptTokens === null ? 'tokens ?' : `tokens ${out.promptTokens} (floor ${out.floor})`;
      let diffs = [];
      if (out.ok && truth) {
        const t = truth.get(p.name);
        diffs = t ? compare(out.order, t) : ['no truth row for this file'];
      }
      results[i] = { ok: out.ok && diffs.length === 0, out };
      if (out.ok) {
        const o = out.order;
        console.log(
          `${diffs.length ? 'DIFF' : 'ok  '} ${o.symbol.padEnd(5)} ${o.side.padEnd(4)} ${String(o.shares).padEnd(12)} ` +
            `total $${o.totalUsd.toFixed(2).padStart(9)}  ${tokens}  ${out.attempts} try  ${seconds}s  ${p.name}`,
        );
        for (const d of diffs) console.log(`       ${d}`);
      } else {
        console.log(`FAIL ${out.code.padEnd(11)} ${tokens}  ${out.attempts} try  ${seconds}s  ${p.name}`);
        console.log(`       ${out.message}`);
        if (out.detail) console.log(`       ${out.detail}`);
        for (const issue of out.issues.slice(1)) console.log(`       ${issue}`);
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  const good = results.filter(r => r.ok).length;
  const repaired = results.filter(r => r.out.ok && r.out.attempts === 2).length;
  const margins = results.filter(r => r.out.ok).map(r => r.out.promptTokens - r.out.floor);
  console.log(
    `\n${good}/${results.length} read${truth ? ' and matched' : ''}; ${repaired} needed the repair; ` +
      (margins.length ? `smallest margin over the token floor: ${Math.min(...margins)} tokens` : 'no token margins'),
  );
  process.exit(good === results.length ? 0 : 1);
}

await main();
