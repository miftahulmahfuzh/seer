#!/usr/bin/env node
// Run a command with the repo-root .env.local loaded, then exec it: `node scripts/with-env.mjs next dev -p 3111`.
//
// Why not `node --env-file=../.env.local node_modules/.bin/next dev`: Next's CLI re-execs itself
// and passes the parent's node flags through NODE_OPTIONS, where `--env-file` is refused --
// "--env-file= is not allowed in NODE_OPTIONS". Loading the file here and spawning a plain child
// puts nothing in NODE_OPTIONS.
//
// Why not a `web/.env.local` symlink, which Next would read on its own: the file holds the
// production database URL and every secret, and a symlink into the package directory is one
// careless `git add -f` away from committing it.
//
// zsh cannot `source` this file either -- DATABASE_URL contains an unquoted `&`. Parsing, not
// sourcing, is the rule everywhere in this repo.
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const file = process.env.SEER_ENV_FILE ?? join(root, '.env.local');

let loaded = 0;
try {
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('#')) continue;
    const i = t.indexOf('=');
    if (i < 1) continue;
    const key = t.slice(0, i).trim();
    let value = t.slice(i + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    // An exported variable wins, so `DATABASE_URL=... npm run dev:env` still points elsewhere.
    if (!(key in process.env)) { process.env[key] = value; loaded++; }
  }
} catch (e) {
  console.error(`with-env: cannot read ${file}: ${e.message}`);
  process.exit(1);
}

const [cmd, ...args] = process.argv.slice(2);
if (!cmd) {
  console.error('with-env: nothing to run. Usage: node scripts/with-env.mjs <command> [args...]');
  process.exit(2);
}
console.error(`with-env: ${loaded} variable(s) from ${file}`);

const child = spawn(cmd, args, { stdio: 'inherit', shell: false, cwd: process.cwd(),
  env: process.env, ...(cmd === 'next' ? { shell: true } : {}) });
child.on('exit', (code, signal) => process.exit(signal ? 1 : (code ?? 0)));
child.on('error', e => { console.error(`with-env: ${e.message}`); process.exit(1); });
