// Loaded into every Node process a verify run starts (NODE_OPTIONS=--import <this file>): the
// Next dev server, its workers, and the seed scripts.
//
// Two jobs, both keyed off env that only verify.sh sets:
//
// 1. Route Neon to the run's shim. The run's DATABASE_URL names the host pg.seerverify.invalid, so
//    `neon()` POSTs to https://api.seerverify.invalid/sql; that one URL is rewritten to the shim.
//    The seeders use `Pool` over WebSocket instead, so when SEER_VERIFY_NEON_WS=1 this also points
//    the shared neonConfig at the shim's /v2 (ESM caches the module, so the seeder sees the same
//    instance). Next bundles its own copy of the driver, which is why the app path goes through
//    fetch and not through neonConfig.
//
// 2. Egress control. Node's fetch ignores HTTP(S)_PROXY, so the dead proxy verify.sh sets cannot
//    stop it. Any fetch to a host that is not loopback and not on SEER_VERIFY_ALLOW_HOSTS throws.
//    That is what keeps the GitHub workflow dispatches, the receipts branch writes and the vision
//    model from leaving the machine. Best effort: code on node:http/https directly, or Turbopack's
//    own Rust fetcher, is not covered by this hook (the proxy env covers the latter).
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const shim = process.env.SEER_VERIFY_SHIM;
const allow = new Set((process.env.SEER_VERIFY_ALLOW_HOSTS ?? '').split(',').map((h) => h.trim()).filter(Boolean));
const loopback = (h) => h === '127.0.0.1' || h === 'localhost' || h === '::1' || h === '[::1]';

if (shim) {
  const real = globalThis.fetch;
  globalThis.fetch = function verifyFetch(input, init) {
    const href = typeof input === 'string' ? input : input instanceof URL ? input.href : input?.url;
    let url;
    try { url = new URL(href); } catch { return real(input, init); }
    if (url.hostname === 'api.seerverify.invalid' && url.pathname === '/sql') return real(`${shim}/sql`, init);
    if (url.protocol === 'data:' || url.protocol === 'blob:' || loopback(url.hostname) || allow.has(url.hostname)) return real(input, init);
    console.error(`seer-verify: egress BLOCKED ${init?.method ?? 'GET'} ${url.origin}${url.pathname}`);
    return Promise.reject(new TypeError(`seer-verify: egress to ${url.host} is blocked in a verify run`));
  };

  if (process.env.SEER_VERIFY_NEON_WS === '1' && process.env.SEER_VERIFY_WEB) {
    const mod = path.join(process.env.SEER_VERIFY_WEB, 'node_modules/@neondatabase/serverless/index.mjs');
    const { neonConfig } = await import(pathToFileURL(mod).href);
    const port = new URL(shim).port;
    neonConfig.wsProxy = () => `127.0.0.1:${port}/v2`;
    neonConfig.useSecureWebSocket = false;
    neonConfig.pipelineConnect = false;
  }
}
