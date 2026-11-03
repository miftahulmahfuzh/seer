#!/usr/bin/env bash
# verify.sh: launch, drive and tear down a throwaway Seer (web app + engine + lab) for verification.
#
# Every run gets its own Postgres database (in one shared Docker container), a Neon shim in front
# of it, a snapshot of web/ served by its own `next dev` on a free port, a copy of lab.sqlite and a
# minted session cookie. Nothing touches Neon, the live site, GitHub, Telegram, Vercel, the
# committed lab.sqlite or the shared research stores (read only). Evidence lives under
# $VERIFY_HOME/<run>/evidence and survives `down`.
#
#   verify.sh up [--no-web] [--empty] [--champion=ID] [--net] [--llm[=N]]
#                                        start a run from the current checkout; prints RUN= URL= EVIDENCE=
#   verify.sh doctor RUN                 is this run worth driving? (read-only)
#   verify.sh api RUN METHOD PATH [JSON] signed-in HTTP call; request + response saved as evidence
#   verify.sh upload RUN IMAGE.jpg       POST a receipt to /api/sean/orders the way the uploader does
#   verify.sh ui RUN STEPS.mjs [--width N] [--theme light|dark]
#                                        drive the app with Playwright, signed in (video + screenshots)
#   verify.sh shoot RUN [shoot.mjs flags] PATH...   the repo's own screenshot harness, against this run
#   verify.sh engine RUN ARGS...         python -m seer_engine ARGS against the run's DB and lab copy
#   verify.sh lab RUN ARGS...            shorthand for: engine RUN lab ARGS
#   verify.sh sql RUN "SELECT ..."       read the run's Postgres (read-only transaction)
#   verify.sh labsql RUN "SELECT ..."    read the run's lab.sqlite copy (read-only)
#   verify.sh note RUN "TEXT"            append a line to evidence/LOG.md (what you proved)
#   verify.sh down RUN|--all             stop what `up` started, drop its DB; evidence stays
#   verify.sh ls                         runs with state, mode and evidence count
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_HOME="${VERIFY_HOME:-$HOME/.local/state/seer-verify}"
PG_CONTAINER=seer-pg-verify
PG_IMAGE=postgres:16
PG_PORT=55437
DEAD_PROXY=http://127.0.0.1:9
# Read-only public market data an --net run may reach (engine only). EODHD is deliberately absent:
# its token is a paid personal licence and nothing a verify journey needs.
NET_HOSTS=api.massive.com,finnhub.io,data.sec.gov,www.sec.gov,api.frankfurter.dev,query1.finance.yahoo.com,query2.finance.yahoo.com,fc.yahoo.com,guce.yahoo.com
# next/font/google downloads Outfit while compiling; a public font CDN, nothing else.
FONT_HOSTS=fonts.googleapis.com,fonts.gstatic.com
# Every secret .env.local holds that could message someone, write somewhere shared, or dispatch a
# production workflow. Blanked in every process a run starts, whatever the flags.
HARMFUL_BLANK=(GITHUB_DISPATCH_TOKEN= TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= VERCEL_TOKEN= VERCEL_ORG_ID=
  VERCEL_PROJECT_ID= BLOB_STORE_ID= BLOB_READ_WRITE_TOKEN= EODHD_API_TOKEN= OPENROUTER_API_KEY=)
# Engine commands that write outside the run (research stores, tracked repo files such as the frozen
# backtest reports, the roster) or spend the test window. Refused, no flag.
ENGINE_DENY=" research_store survivorship_store universe_store shares sectors market_series dividend_announcements universe_probe backtest backtest_b backtest_dev backtest_wf promote "
# lab: test spends (and peeks at) the test window; promote writes a pre-registration file into the
# checkout; stage git-adds in the MAIN checkout; export/export-json write tracked files; seed is one-time.
LAB_DENY=" test promote stage export export-json seed "
LLM_PAID=" veto explain "

die() { echo "verify: $*" >&2; exit 1; }
repo_root() { git rev-parse --show-toplevel 2>/dev/null || die "run from inside a seer checkout"; }
# The main checkout: where .env.local, the shared venv and the research stores live (never in a worktree).
main_root() { (cd "$(git -C "$1" rev-parse --path-format=absolute --git-common-dir)/.." && pwd); }

run_dir() {
  local run=${1:-}
  [ -n "$run" ] || die "missing RUN id (see: verify.sh ls)"
  [ -d "$VERIFY_HOME/$run" ] || die "no run $run under $VERIFY_HOME"
  echo "$VERIFY_HOME/$run"
}
meta() { sed -n "s/^$2=//p" "$1/meta" | head -1; }
free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }
slug() { printf %s "$1" | tr -c 'a-zA-Z0-9_.-' '_' | cut -c1-40; }

# Numbered evidence: evidence/NN-<kind>-<slug>.<ext>, counting only the primary .txt files.
next_evidence() {
  local dir=$1/evidence n
  n=$(find "$dir" -maxdepth 1 -type f -name '[0-9][0-9]-*.txt' | wc -l)
  printf '%s/%02d-%s-%s.%s' "$dir" $((n + 1)) "$2" "$(slug "$3")" "$4"
}

# What the code under test is: HEAD plus a digest of uncommitted changes to the app's own paths.
# .workflows/ and docs/ are excluded so a peer's orchestration bookkeeping does not read as drift.
tree_digest() {
  { git -C "$1" diff HEAD -- web engine db lab .claude/skills/verify-seer
    git -C "$1" ls-files --others --exclude-standard -- web engine db lab | sort | while read -r f; do sha1sum "$1/$f"; done
  } 2>/dev/null | sha1sum | cut -c1-12
}

ensure_pg() {
  command -v docker >/dev/null || die "docker is not on PATH"
  local state
  state="$(docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null)" || state=missing
  case "$state" in
    true) ;;
    false) docker start "$PG_CONTAINER" >/dev/null ;;
    # trust auth: bound to 127.0.0.1 only, holds nothing but throwaway v_* databases.
    *) docker run -d --name "$PG_CONTAINER" -e POSTGRES_HOST_AUTH_METHOD=trust \
         -p "127.0.0.1:$PG_PORT:5432" "$PG_IMAGE" >/dev/null ;;
  esac
  for _ in $(seq 1 60); do
    docker exec "$PG_CONTAINER" pg_isready -q -h 127.0.0.1 -U postgres >/dev/null 2>&1 && return 0
    sleep 1
  done
  die "$PG_CONTAINER did not become ready in 60s"
}
psql_run() { docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -X -q -U postgres "$@"; }

# One value from the main checkout's .env.local, parsed (never sourced: DATABASE_URL has a bare &).
env_value() { sed -n "s/^$2=//p" "$1/.env.local" 2>/dev/null | head -1 | sed -E 's/^"(.*)"$/\1/'; }

python_for() {
  local root=$1 main=$2
  if [ -x "$root/engine/.venv/bin/python" ]; then echo "$root/engine/.venv/bin/python"
  elif [ -x "$main/engine/.venv/bin/python" ]; then echo "$main/engine/.venv/bin/python"
  else die "no engine/.venv in $root or $main (python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')"; fi
}

# The environment of every engine process: nothing inherited but PATH/HOME/locale, so no secret in
# the caller's shell leaks in. SEER_ENV_FILE points at the run's own file, so .env.local is never read.
engine_env() {
  local dir=$1
  printf '%s\n' "PATH=$PATH" "HOME=$HOME" "LANG=${LANG:-C.UTF-8}" "TERM=dumb" \
    "SEER_ENV_FILE=$dir/engine.env" "SEER_LAB_DB=$dir/lab.sqlite" \
    "SEER_RESEARCH_STORE=$(meta "$dir" main)/engine/.research" "PYTHONPATH=$(meta "$dir" repo)/engine/src" \
    "HTTP_PROXY=$DEAD_PROXY" "HTTPS_PROXY=$DEAD_PROXY" "http_proxy=$DEAD_PROXY" "https_proxy=$DEAD_PROXY" \
    "ALL_PROXY=$DEAD_PROXY" "NO_PROXY=$(meta "$dir" no_proxy)" "no_proxy=$(meta "$dir" no_proxy)"
  cat "$dir/engine.env"
}

web_env() {
  local dir=$1
  printf '%s\n' "PATH=$PATH" "HOME=$HOME" "LANG=${LANG:-C.UTF-8}" \
    "DATABASE_URL=$(meta "$dir" neon_url)" "DATABASE_URL_UNPOOLED=$(meta "$dir" neon_url)" \
    "AUTH_SECRET=$(cat "$dir/auth_secret")" "AUTH_TRUST_HOST=true" "ALLOWED_EMAIL=$(cat "$dir/owner")" \
    "AUTH_GOOGLE_ID=seer-verify-unused" "AUTH_GOOGLE_SECRET=seer-verify-unused" \
    "LLM_API_KEY=" "LLM_VISION_BASE_URL=" "LLM_VISION_MODEL=" "LLM_BASE_URL=" "LLM_MODEL=" \
    "NEXT_TELEMETRY_DISABLED=1" "NODE_OPTIONS=--import=file://$HERE/preload.mjs" \
    "SEER_VERIFY_SHIM=http://127.0.0.1:$(cat "$dir/shim_port")" "SEER_VERIFY_WEB=$dir/web" \
    "SEER_VERIFY_ALLOW_HOSTS=$FONT_HOSTS" "${HARMFUL_BLANK[@]}"
  # No dead proxy here, unlike the engine: Turbopack fetches the Google font files in Rust and
  # fails the whole layout behind one, NO_PROXY or not. Node's fetch ignores proxy env anyway, so
  # the web side's egress control is preload.mjs's fetch guard.
}

# Run a command under an env file (one VAR=value per line), with nothing else inherited.
with_env() { local file=$1; shift; local -a e=(); mapfile -t e <"$file"; env -i "${e[@]}" "$@"; }

cmd_up() {
  local web=1 seed=1 champion="" net=0 llm=0
  for a in "$@"; do
    case "$a" in
      --no-web) web=0 ;;
      --empty) seed=0 ;;
      --champion=*) champion=${a#--champion=} ;;
      --net) net=1 ;;
      --llm) llm=3 ;;
      --llm=*) llm=${a#--llm=}; [[ $llm =~ ^[0-9]+$ ]] || die "--llm=N takes a number" ;;
      *) die "up: unknown flag $a (champion is --champion=ID)" ;;
    esac
  done
  local root main run dir db py
  root="$(repo_root)"
  [ -f "$root/engine/src/seer_engine/cli.py" ] && [ -f "$root/web/package.json" ] || die "$root is not a seer checkout"
  main="$(main_root "$root")"
  py="$(python_for "$root" "$main")"
  [ "$web" = 0 ] || [ -d "$root/web/node_modules/next" ] || die "no web/node_modules in $root (cd web && npm ci)"
  [ "$llm" = 0 ] || [ -n "$(env_value "$main" LLM_API_KEY)" ] || die "--llm: LLM_API_KEY is not in $main/.env.local"

  run="$(date +%m%d-%H%M%S)-$$"
  dir="$VERIFY_HOME/$run"
  db="v_$(echo "$run" | tr -- '-' '_')"
  mkdir -p "$dir/evidence"
  : >"$dir/pgids"

  local no_proxy=127.0.0.1,localhost llm_host=""
  [ "$net" = 1 ] && no_proxy="$no_proxy,$NET_HOSTS"
  if [ "$llm" != 0 ]; then
    llm_host="$(env_value "$main" LLM_BASE_URL | sed -E 's#^[a-z]+://([^/:]+).*#\1#')"
    no_proxy="$no_proxy,$llm_host"
  fi
  {
    echo "repo=$root"; echo "main=$main"; echo "python=$py"
    echo "head=$(git -C "$root" rev-parse --short HEAD)"; echo "tree=$(tree_digest "$root")"
    echo "db=$db"; echo "web=$web"; echo "seed=$([ "$seed" = 1 ] && echo demo || echo empty)"
    echo "champion=${champion:-default}"; echo "net=$net"; echo "llm=$llm${llm_host:+ ($llm_host)}"
    echo "mode=$([ "$net$llm" = 00 ] && echo offline || echo "real-external(net=$net llm=$llm)")"
    echo "no_proxy=$no_proxy"
    echo "neon_url=postgresql://postgres:verify@pg.seerverify.invalid/$db"
    echo "started=$(date -Iseconds)"
  } >"$dir/meta"
  echo "$llm" >"$dir/llm_budget"

  # The engine's dotenv file: the run's DB, harmful keys blank, data/LLM keys only when opted in.
  {
    echo "DATABASE_URL=postgresql://postgres@127.0.0.1:$PG_PORT/$db"
    echo "DATABASE_URL_UNPOOLED=postgresql://postgres@127.0.0.1:$PG_PORT/$db"
    printf '%s\n' "${HARMFUL_BLANK[@]}"
    if [ "$net" = 1 ]; then
      for k in MASSIVE_API_KEY FINNHUB_API_KEY SEC_CONTACT_EMAIL; do echo "$k=$(env_value "$main" $k)"; done
    else
      echo "MASSIVE_API_KEY="; echo "FINNHUB_API_KEY="; echo "SEC_CONTACT_EMAIL=verify@seer-verify.invalid"
    fi
    if [ "$llm" != 0 ]; then
      for k in LLM_API_KEY LLM_BASE_URL LLM_MODEL; do echo "$k=$(env_value "$main" $k)"; done
    else
      echo "LLM_API_KEY="; echo "LLM_BASE_URL="; echo "LLM_MODEL="
    fi
  } >"$dir/engine.env"
  chmod 600 "$dir/engine.env"

  # The lab: a private copy, opened read-only at the source (a read-write open migrates and dirties it).
  "$py" -c 'import sqlite3,sys; s=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d)' \
    "$root/lab/lab.sqlite" "$dir/lab.sqlite" || die "could not copy lab/lab.sqlite"

  ensure_pg
  psql_run -c "create database $db" >/dev/null
  engine_env "$dir" >"$dir/engine.envv"
  (cd "$root" && with_env "$dir/engine.envv" "$py" -m seer_engine migrate) >"$dir/migrate.log" 2>&1 \
    || { tail -20 "$dir/migrate.log" >&2; die "migrate failed (verify.sh down $run)"; }

  if [ "$web" = 1 ] || [ "$seed" = 1 ]; then
    # web/ is served from a snapshot: `next dev` locks per project directory, so two runs (or the
    # owner's own dev server) cannot share the checkout's web/. node_modules is hard-linked (a
    # symlink breaks Turbopack). Edits after `up` are not picked up: doctor warns, down + up again.
    rsync -a --exclude node_modules --exclude .next --exclude .shots --exclude .auth --exclude tsconfig.tsbuildinfo \
      "$root/web/" "$dir/web/"
    cp -al "$root/web/node_modules" "$dir/web/node_modules"
    free_port >"$dir/shim_port"
    head -c 32 /dev/urandom | base64 >"$dir/auth_secret"
    # The owner the session signs in as. /sera admits exactly SERA_EMAIL (lib/sera/access.ts), so
    # take it from the code under test; it only ever sits in a cookie signed with this run's secret.
    sed -nE "s/.*SERA_EMAIL = '([^']+)'.*/\1/p" "$root/web/lib/sera/access.ts" >"$dir/owner"
    [ -s "$dir/owner" ] || die "could not read SERA_EMAIL from web/lib/sera/access.ts"
    cd "$dir/web"
    setsid node "$HERE/neon-shim.mjs" "$dir/web" "$(cat "$dir/shim_port")" "$PG_PORT" "$db" </dev/null >"$dir/shim.log" 2>&1 &
    echo "shim $!" >>"$dir/pgids"
    for _ in $(seq 1 40); do curl -fsS -m 2 "http://127.0.0.1:$(cat "$dir/shim_port")/health" >/dev/null 2>&1 && break; sleep 0.25; done
    curl -fsS -m 2 "http://127.0.0.1:$(cat "$dir/shim_port")/health" >/dev/null || { cat "$dir/shim.log" >&2; die "shim did not start (verify.sh down $run)"; }
    web_env "$dir" >"$dir/web.env"
    chmod 600 "$dir/web.env"
  fi

  if [ "$seed" = 1 ]; then
    { echo "SEER_VERIFY_NEON_WS=1"; cat "$dir/web.env"; } >"$dir/seed.env"
    (with_env "$dir/seed.env" node scripts/seed-demo.mjs && with_env "$dir/seed.env" node scripts/seed-demo-sean.mjs) >"$dir/seed.log" 2>&1 \
      || { tail -20 "$dir/seed.log" >&2; die "demo seed failed (verify.sh down $run)"; }
    if [ -n "$champion" ]; then
      [ "$(psql_run -d "$db" -tAc "select count(*) from strategies where id = '$(slug "$champion")'")" = 1 ] || die "--champion: no strategy $champion in the demo data"
      psql_run -d "$db" -c "update strategies set is_champion = (id = '$(slug "$champion")')" >/dev/null
    fi
  fi

  if [ "$web" = 1 ]; then
    local port; port="$(free_port)"; echo "$port" >"$dir/port"
    # Mint the owner's session the way web/scripts/session.mjs does, with this run's secret.
    with_env "$dir/web.env" node --input-type=module -e "
      import { mint } from './scripts/session.mjs';
      process.stdout.write(await mint({ name: 'Owner', email: '$(cat "$dir/owner")', sub: 'seer-verify' }, 60 * 60 * 24 * 7));
    " >"$dir/cookie" || die "could not mint a session"
    # setsid: own process group (down kills exactly this tree); every fd redirected so no caller's
    # pipe stays open behind the server.
    mapfile -t _webenv <"$dir/web.env"
    setsid env -i "${_webenv[@]}" node node_modules/next/dist/bin/next dev -p "$port" -H 127.0.0.1 </dev/null >"$dir/next.log" 2>&1 &
    echo "next $!" >>"$dir/pgids"
    local url="http://127.0.0.1:$port" code="" fails=0
    for _ in $(seq 1 240); do
      code="$(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Cookie: authjs.session-token=$(cat "$dir/cookie")" "$url/" || true)"
      [ "$code" = 200 ] && break
      # A 500 that survives several compiles is a broken page, not a slow one.
      [ "$code" = 500 ] && fails=$((fails + 1)) && [ "$fails" -ge 5 ] && break
      kill -0 "$(awk '$1=="next"{print $2}' "$dir/pgids")" 2>/dev/null || { tail -20 "$dir/next.log" >&2; die "next dev exited during startup (verify.sh down $run)"; }
      sleep 1
    done
    [ "$code" = 200 ] || { tail -20 "$dir/next.log" >&2; die "/ did not answer 200 signed in (last $code; log $dir/next.log)"; }
    echo "RUN=$run"; echo "URL=$url"
  else
    echo "RUN=$run"; echo "URL=none (--no-web)"
  fi
  echo "EVIDENCE=$dir/evidence"
  echo "MODE=$(meta "$dir" mode)"
}

pgid_of() { awk -v k="$2" '$1==k{print $2}' "$1/pgids" 2>/dev/null; }

cmd_doctor() {
  local dir ok=1 root
  dir="$(run_dir "${1:-}")"
  root="$(meta "$dir" repo)"
  local shim next sp port
  shim="$(pgid_of "$dir" shim)"; next="$(pgid_of "$dir" next)"
  sp="$(cat "$dir/shim_port" 2>/dev/null || true)"; port="$(cat "$dir/port" 2>/dev/null || true)"
  if [ -n "$shim" ]; then
    if curl -fsS -m 3 "http://127.0.0.1:$sp/health" | grep -q seer-verify-shim; then echo "shim     ok   :$sp"; else echo "shim     FAIL :$sp not answering"; ok=0; fi
  fi
  if [ "$(meta "$dir" web)" = 1 ]; then
    if [ -n "$next" ] && kill -0 "$next" 2>/dev/null; then echo "next     ok   pgid $next"; else echo "next     FAIL not running"; ok=0; fi
    local owner
    owner="$(ss -ltnpH "sport = :${port:-0}" 2>/dev/null | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)"
    if [ -n "$owner" ] && [ "$(ps -o pgid= -p "$owner" | tr -d ' ')" = "$next" ]; then
      echo "port     ok   :$port owned by this run (pid $owner)"
    else
      echo "port     FAIL :$port is ${owner:+owned by pid $owner, }not this run's next"; ok=0
    fi
    local code
    code="$(curl -s -o /dev/null -m 60 -w '%{http_code}' -H "Cookie: authjs.session-token=$(cat "$dir/cookie")" "http://127.0.0.1:$port/" || true)"
    if [ "$code" = 200 ]; then echo "signin   ok   / answers 200 with the minted session"; else echo "signin   FAIL / answered $code"; ok=0; fi
  fi
  local n
  if n="$(psql_run -d "$(meta "$dir" db)" -tAc "select count(*) from schema_migrations" 2>/dev/null)"; then
    echo "database ok   $(meta "$dir" db) ($n migrations, strategies: $(psql_run -d "$(meta "$dir" db)" -tAc "select count(*) from strategies"))"
  else echo "database FAIL $(meta "$dir" db)"; ok=0; fi
  [ -f "$dir/lab.sqlite" ] && echo "lab      ok   $dir/lab.sqlite (private copy)"
  echo "mode     $(meta "$dir" mode)   llm budget left: $(cat "$dir/llm_budget")"
  for k in repo head seed champion; do printf 'meta     %s=%s\n' "$k" "$(meta "$dir" $k)"; done
  if [ "$(git -C "$root" rev-parse --short HEAD)" != "$(meta "$dir" head)" ]; then
    echo "code     WARN HEAD moved since up: the web snapshot is stale (down + up); engine drives run the live checkout"
  fi
  if [ "$(tree_digest "$root")" != "$(meta "$dir" tree)" ]; then
    echo "code     WARN working tree changed since up: the web snapshot is stale (down + up); engine drives run the live checkout"
  fi
  # Engine egress: a harmful host must hit the dead proxy. Nothing leaves the machine either way.
  engine_env "$dir" >"$dir/engine.envv"
  if with_env "$dir/engine.envv" "$(meta "$dir" python)" -c 'import urllib.request as u; u.urlopen("https://api.github.com", timeout=3)' >/dev/null 2>&1; then
    echo "egress   FAIL engine reached api.github.com"; ok=0
  else echo "egress   ok   engine cannot reach api.github.com (dead proxy; allowed: $(meta "$dir" no_proxy))"; fi
  local blocked
  blocked="$(cat "$dir"/next.log "$dir"/seed.log 2>/dev/null | grep -oE 'egress BLOCKED [A-Z]+ https?://[^/ ]+' | sort | uniq -c || true)"
  [ -n "$blocked" ] && echo "$blocked" | sed 's/^/egress   /'
  grep -iE "⨯|error" "$dir/next.log" 2>/dev/null | grep -v "egress" | tail -3 | sed 's/^/log      /' || true
  [ "$ok" = 1 ] || exit 1
}

need_web() { [ "$(meta "$1" web)" = 1 ] || die "this run was started with --no-web"; }

cmd_api() {
  local dir method path body out
  dir="$(run_dir "${1:-}")"; method=${2:?METHOD}; path=${3:?PATH}; body=${4:-}
  need_web "$dir"
  local base="http://127.0.0.1:$(cat "$dir/port")"
  out="$(next_evidence "$dir" api "$method$path" txt)"
  local -a args=(-sS -o "$out.body" -w '%{http_code}|%{content_type}|%{redirect_url}' -X "$method" "$base$path"
    -H "Cookie: authjs.session-token=$(cat "$dir/cookie")" -H "Origin: $base")
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' --data "$body")
  local m code ctype redir
  m="$(curl "${args[@]}")"
  IFS='|' read -r code ctype redir <<<"$m"
  {
    echo "> $method $path"; [ -n "$body" ] && echo "> $(printf %s "$body" | cut -c1-400)"
    echo "< HTTP $code ${ctype:-} ${redir:+-> $redir}"
    if [[ ${ctype:-} =~ json|text ]] || [ ! -s "$out.body" ]; then
      if [[ ${ctype:-} =~ html ]]; then
        echo "[html $(wc -c <"$out.body") bytes; visible text:]"
        python3 "$HERE/htmltext.py" "$out.body" 80
        mv "$out.body" "${out%.txt}.html"; echo "[full html: ${out%.txt}.html]"
      else cat "$out.body"; echo; rm -f "$out.body"; fi
    else
      mv "$out.body" "${out%.txt}.bin"
      echo "[binary $(wc -c <"${out%.txt}.bin") bytes, sha256 $(sha256sum "${out%.txt}.bin" | cut -c1-16): ${out%.txt}.bin]"
    fi
  } >"$out"
  cat "$out"
  echo "[evidence: $out]" >&2
}

cmd_upload() {
  local dir file
  dir="$(run_dir "${1:-}")"; file=${2:?IMAGE}
  [ -f "$file" ] || die "no such file: $file"
  # The body Uploader.tsx sends: base64 without a data: prefix, plus the sha256 of the bytes.
  local json="$dir/upload.json"
  python3 -c 'import base64,hashlib,json,sys; b=open(sys.argv[1],"rb").read(); json.dump({"image":base64.b64encode(b).decode(),"sha256":hashlib.sha256(b).hexdigest()},open(sys.argv[2],"w"))' "$file" "$json"
  cmd_api "$1" POST /api/sean/orders "$(cat "$json")"
  rm -f "$json"
}

cmd_ui() {
  local dir steps width=1280 theme=dark
  dir="$(run_dir "${1:-}")"; steps=${2:?STEPS.mjs}; shift 2
  while [ $# -gt 0 ]; do case "$1" in --width) width=$2; shift 2 ;; --theme) theme=$2; shift 2 ;; *) die "ui: unknown flag $1" ;; esac; done
  need_web "$dir"
  [ -f "$steps" ] || die "no such steps file: $steps"
  steps="$(realpath "$steps")"   # before the cd into the snapshot, so relative paths work
  (cd "$dir/web" && node "$HERE/ui.mjs" "http://127.0.0.1:$(cat "$dir/port")" "$steps" "$dir/evidence" "$(cat "$dir/cookie")" "$width" "$theme")
}

cmd_shoot() {
  local dir out shots
  dir="$(run_dir "${1:-}")"; shift
  need_web "$dir"
  out="$(next_evidence "$dir" shoot "${*: -1}" txt)"
  shots="${out%.txt}"; mkdir -p "$shots"
  local rc=0
  (cd "$dir/web" && with_env "$dir/web.env" node scripts/shoot.mjs --base "http://127.0.0.1:$(cat "$dir/port")" --out "$shots" "$@") >"$out" 2>&1 || rc=$?
  echo "exit $rc; pngs and page text in $shots/" >>"$out"
  cat "$out"
  echo "[evidence: $out]" >&2
  return $rc
}

cmd_engine() {
  local dir; dir="$(run_dir "${1:-}")"; shift
  [ $# -gt 0 ] || die "engine: which seer_engine command?"
  local -a pos=()
  for a in "$@"; do
    case "$a" in
      --db|--db=*) die "engine: --db is refused; the run's lab copy is already SEER_LAB_DB" ;;
      -*) ;;
      *) pos+=("$a") ;;
    esac
  done
  local cmd=${pos[0]:-}
  [[ $ENGINE_DENY == *" $cmd "* ]] && die "engine: '$cmd' writes outside the run (stores, tracked files, roster) and is never driven"
  if [ "$cmd" = lab ]; then
    [[ $LAB_DENY == *" ${pos[1]:-} "* ]] && die "engine: 'lab ${pos[1]}' is never driven (test window, main checkout or tracked files)"
  fi
  if [[ $LLM_PAID == *" $cmd "* ]] && [ "$(cat "$dir/llm_budget")" != 0 ]; then
    local left; left=$(( $(cat "$dir/llm_budget") - 1 )); echo "$left" >"$dir/llm_budget"
    echo "verify: paid LLM drive; budget left $left" >&2
  fi
  local out rc=0
  out="$(next_evidence "$dir" engine "$*" txt)"
  engine_env "$dir" >"$dir/engine.envv"
  { echo "> python -m seer_engine $*   (mode $(meta "$dir" mode))"
    (cd "$(meta "$dir" repo)" && with_env "$dir/engine.envv" "$(meta "$dir" python)" -m seer_engine "$@") 2>&1 || rc=$?
    echo "< exit $rc"
  } >"$out"
  cat "$out"
  echo "[evidence: $out]" >&2
  return $rc
}

cmd_lab() { local run=${1:-}; shift || true; cmd_engine "$run" lab "$@"; }

cmd_sql() {
  local dir out
  dir="$(run_dir "${1:-}")"
  out="$(next_evidence "$dir" sql query txt)"
  { echo "> ${2:?SQL}"; printf 'begin read only;\n%s;\nrollback;\n' "$2" | psql_run -d "$(meta "$dir" db)" 2>&1; } | tee "$out"
  echo "[evidence: $out]" >&2
}

cmd_labsql() {
  local dir out
  dir="$(run_dir "${1:-}")"
  out="$(next_evidence "$dir" labsql query txt)"
  { echo "> ${2:?SQL}"
    "$(meta "$dir" python)" -c '
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
cur = c.execute(sys.argv[2])
print(" | ".join(d[0] for d in cur.description or []))
for r in cur.fetchmany(200): print(" | ".join("" if v is None else str(v) for v in r))
' "$dir/lab.sqlite" "$2" 2>&1; } | tee "$out"
  echo "[evidence: $out]" >&2
}

cmd_note() {
  local dir; dir="$(run_dir "${1:-}")"
  echo "$(date -Iseconds) ${2:?TEXT}" >>"$dir/evidence/LOG.md"
}

stop_run() {
  local dir=$1 kind pgid
  while read -r kind pgid; do
    [ -n "${pgid:-}" ] || continue
    if kill -0 "$pgid" 2>/dev/null; then
      kill -TERM -- "-$pgid" 2>/dev/null || true
      for _ in $(seq 1 20); do kill -0 "$pgid" 2>/dev/null || break; sleep 0.25; done
      kill -KILL -- "-$pgid" 2>/dev/null || true
    fi
  done <"$dir/pgids"
  for f in next.log shim.log seed.log migrate.log meta; do [ -f "$dir/$f" ] && cp "$dir/$f" "$dir/evidence/zz-$f"; done
  if docker inspect "$PG_CONTAINER" >/dev/null 2>&1 && [ -n "$(meta "$dir" db)" ]; then
    psql_run -c "drop database if exists $(meta "$dir" db) with (force)" >/dev/null || true
  fi
  rm -rf "$dir/web" "$dir/lab.sqlite" "$dir"/*.env "$dir/engine.envv" "$dir/cookie" "$dir/auth_secret" "$dir/owner" "$dir/port" "$dir/shim_port"
  : >"$dir/pgids"; echo stopped >"$dir/state"
  echo "verify: stopped $(basename "$dir"); evidence kept in $dir/evidence ($(find "$dir/evidence" -type f | wc -l) files)"
}

cmd_down() {
  if [ "${1:-}" = --all ]; then
    for d in "$VERIFY_HOME"/*/; do [ -f "$d/meta" ] && [ ! -f "$d/state" ] && stop_run "${d%/}"; done
    return 0
  fi
  stop_run "$(run_dir "${1:-}")"
}

cmd_ls() {
  [ -d "$VERIFY_HOME" ] || return 0
  for d in "$VERIFY_HOME"/*/; do
    d=${d%/}
    local state=stopped
    if [ ! -f "$d/state" ]; then
      state="up${d:+ }$( [ -f "$d/port" ] && echo ":$(cat "$d/port")" || echo "(no web)")"
    fi
    printf '%-20s %-12s %-30s %3s evidence  %s\n' "$(basename "$d")" "$state" "$(meta "$d" mode 2>/dev/null)" \
      "$(find "$d/evidence" -type f 2>/dev/null | wc -l)" "$(meta "$d" repo 2>/dev/null)"
  done
}

sub=${1:-}; shift || true
case "$sub" in
  up) cmd_up "$@" ;;
  doctor) cmd_doctor "$@" ;;
  api) cmd_api "$@" ;;
  upload) cmd_upload "$@" ;;
  ui) cmd_ui "$@" ;;
  shoot) cmd_shoot "$@" ;;
  engine) cmd_engine "$@" ;;
  lab) cmd_lab "$@" ;;
  sql) cmd_sql "$@" ;;
  labsql) cmd_labsql "$@" ;;
  note) cmd_note "$@" ;;
  down) cmd_down "$@" ;;
  ls) cmd_ls ;;
  *) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
