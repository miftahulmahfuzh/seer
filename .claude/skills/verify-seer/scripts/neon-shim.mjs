// node neon-shim.mjs <web-dir> <listen-port> <pg-port> <db>
//
// Stands in for Neon in front of the run's local Postgres, so the web app and its seed scripts run
// unmodified against a throwaway database instead of production.
//
// Why a shim at all: web/ talks to Postgres only through @neondatabase/serverless, which speaks
// HTTP (`neon()`, POST https://api.<host>/sql) and WebSocket (`Pool`, wss://<host>/v2), never raw
// TCP. A local Postgres answers neither. This process answers both on one loopback port:
//   GET  /health   liveness, for verify.sh doctor
//   WS   /v2       a byte pipe to the run's Postgres (what Pool/Client expect of Neon's proxy)
//   POST /sql      Neon's HTTP query protocol, executed over our own /v2 pipe
// preload.mjs routes the app's fetch and the seeders' Pool here. The connection string in the
// request is ignored: this shim only ever reaches its own run's database.
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import net from 'node:net';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const [webDir, portArg, pgPortArg, db] = process.argv.slice(2);
if (!webDir || !portArg || !pgPortArg || !db) {
  console.error('usage: node neon-shim.mjs <web-dir> <listen-port> <pg-port> <db>');
  process.exit(2);
}
const port = Number(portArg);
const pgPort = Number(pgPortArg);
const require = createRequire(path.join(webDir, 'package.json'));
const WS = require('ws');
const neon = await import(pathToFileURL(path.join(webDir, 'node_modules/@neondatabase/serverless/index.mjs')).href);

neon.neonConfig.webSocketConstructor = WS;
neon.neonConfig.wsProxy = () => `127.0.0.1:${port}/v2`;
neon.neonConfig.useSecureWebSocket = false;
neon.neonConfig.pipelineConnect = false;
const pool = new neon.Pool({ connectionString: `postgresql://postgres@pg.seerverify.invalid/${db}`, max: 8 });

// Neon's HTTP protocol returns every value as text and lets the driver parse it by type oid, so
// the query runs with every parser replaced by the identity.
const RAW = { getTypeParser: () => (v) => v };
const ISO = { ReadUncommitted: 'READ UNCOMMITTED', ReadCommitted: 'READ COMMITTED', RepeatableRead: 'REPEATABLE READ', Serializable: 'SERIALIZABLE' };

const shape = (r) => ({
  command: r.command,
  rowCount: r.rowCount,
  rowAsArray: true,
  fields: (r.fields ?? []).map((f) => ({ name: f.name, dataTypeID: f.dataTypeID, tableID: f.tableID, columnID: f.columnID,
    dataTypeSize: f.dataTypeSize, dataTypeModifier: f.dataTypeModifier, format: 'text' })),
  rows: r.rows ?? [],
});
const run = (client, q) => client.query({ text: q.query, values: q.params ?? [], rowMode: 'array', types: RAW });
const brief = (s) => String(s).replace(/\s+/g, ' ').trim().slice(0, 160);

async function sql(req, body) {
  const client = await pool.connect();
  try {
    if (!Array.isArray(body.queries)) {
      console.log(`sql  ${brief(body.query)}`);
      return shape(await run(client, body));
    }
    const iso = ISO[req.headers['neon-batch-isolation-level']] ?? '';
    const ro = req.headers['neon-batch-read-only'] === 'true' ? ' READ ONLY' : '';
    console.log(`tx   ${body.queries.length} statement(s)${iso ? ' ' + iso : ''}${ro}`);
    await client.query(`BEGIN${iso ? ' ISOLATION LEVEL ' + iso : ''}${ro}`);
    try {
      const results = [];
      for (const q of body.queries) { console.log(`  sql ${brief(q.query)}`); results.push(shape(await run(client, q))); }
      await client.query('COMMIT');
      return { results };
    } catch (e) {
      await client.query('ROLLBACK').catch(() => {});
      throw e;
    }
  } finally {
    client.release();
  }
}

const server = createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'content-type': 'text/plain' }).end(`seer-verify-shim ok db=${db}\n`);
    return;
  }
  if (req.method !== 'POST' || !req.url.startsWith('/sql')) { res.writeHead(404).end(); return; }
  let raw = '';
  req.on('data', (c) => { raw += c; });
  req.on('end', async () => {
    try {
      const out = await sql(req, JSON.parse(raw));
      res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(out));
    } catch (e) {
      console.log(`err  ${e.code ?? ''} ${brief(e.message)}`);
      const fields = ['code', 'severity', 'detail', 'hint', 'position', 'schema', 'table', 'column', 'constraint', 'where'];
      const err = { message: e.message };
      for (const f of fields) if (e[f] !== undefined) err[f] = e[f];
      res.writeHead(400, { 'content-type': 'application/json' }).end(JSON.stringify(err));
    }
  });
});

const wss = new WS.WebSocketServer({ noServer: true });
server.on('upgrade', (req, socket, head) => {
  if (!req.url.startsWith('/v2')) { socket.destroy(); return; }
  wss.handleUpgrade(req, socket, head, (ws) => {
    const pg = net.connect(pgPort, '127.0.0.1');
    const pending = [];
    pg.on('connect', () => { for (const b of pending.splice(0)) pg.write(b); });
    ws.on('message', (data) => (pg.connecting ? pending.push(data) : pg.write(data)));
    pg.on('data', (data) => ws.readyState === ws.OPEN && ws.send(data));
    const close = () => { pg.destroy(); if (ws.readyState === ws.OPEN) ws.close(); };
    ws.on('close', close); ws.on('error', close); pg.on('close', close); pg.on('error', close);
  });
});

server.listen(port, '127.0.0.1', () => console.log(`seer-verify-shim listening on http://127.0.0.1:${port} -> 127.0.0.1:${pgPort}/${db}`));
