// Applies db/migrations/*.sql in name order, each once.
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';

neonConfig.webSocketConstructor = ws;

const dir = join(import.meta.dirname, '../../db/migrations');
const pool = new Pool({ connectionString: process.env.DATABASE_URL_UNPOOLED });

await pool.query(`CREATE TABLE IF NOT EXISTS schema_migrations (
  name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`);
const { rows } = await pool.query('SELECT name FROM schema_migrations');
const applied = new Set(rows.map(r => r.name));

for (const name of (await readdir(dir)).filter(f => f.endsWith('.sql')).sort()) {
  if (applied.has(name)) { console.log(`skip  ${name}`); continue; }
  const sql = await readFile(join(dir, name), 'utf8');
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query(sql);
    await client.query('INSERT INTO schema_migrations (name) VALUES ($1)', [name]);
    await client.query('COMMIT');
    console.log(`apply ${name}`);
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}
await pool.end();
