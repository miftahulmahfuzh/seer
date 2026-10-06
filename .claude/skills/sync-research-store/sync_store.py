#!/usr/bin/env python3
"""Move the Seer research store between machines through Vercel Blob.

The store (``engine/.research/``) is the train/eval input: ``lab run`` reads it and never
opens Neon. It is gitignored and rebuilt from the database, which takes ~30 minutes and a
yfinance crawl -- so on a second laptop it is far cheaper to copy than to rebuild.

Identity is the manifest's own ``fingerprint``: sha256 over the sorted per-file sha256 map,
which ``research.load_store`` already verifies. That makes every operation content-addressed:
a push of an unchanged store is a no-op, a pull you already have is a no-op, and a corrupt
download cannot be installed because the fingerprint will not reproduce.

Stdlib only -- the repo forbids new third-party dependencies, and `urllib` is enough for
Blob's REST API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BLOB_API = "https://blob.vercel-storage.com"
BLOB_API_VERSION = "7"
PREFIX = "seer/research-store"
POINTER = f"{PREFIX}/LATEST.json"
MANIFEST = "manifest.json"
KEEP_VERSIONS = 3
TIMEOUT = 600


def out(obj: dict) -> int:
    print(json.dumps(obj, indent=2))
    return 0 if obj.get("ok", True) else 1


def fail(reason: str, **extra) -> int:
    return out({"ok": False, "reason": reason, **extra})


# ------------------------------------------------------------------ repo and store


def repo_root(start: Path | None = None) -> Path | None:
    """The main checkout, even when called from a worktree."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=start or Path.cwd(), capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Path(common).parent
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def store_dir(root: Path) -> Path:
    return root / "engine" / ".research"


def read_manifest(store: Path) -> dict | None:
    path = store / MANIFEST
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def verify_store(store: Path) -> tuple[bool, str]:
    """Re-derive every file's sha256 and the fingerprint, the way ``load_store`` does.

    Returns (ok, detail). This is the gate on both ends: a push never uploads a store that
    does not verify, and a pull never installs one.
    """
    manifest = read_manifest(store)
    if manifest is None:
        return False, "no readable manifest.json"
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        return False, "manifest has no files map"
    for name, want in sorted(files.items()):
        path = store / name
        if not path.is_file():
            return False, f"{name} is listed in the manifest but missing"
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != want:
            return False, f"{name} sha256 {got[:12]} != manifest {str(want)[:12]}"
    # research.fingerprint_of: sha256 of the sorted "name:sha256\n" lines. Replicated rather
    # than imported because this script is stdlib-only and may run under a bare python3 with no
    # access to the engine's venv. If the engine ever changes the recipe this check fails loudly,
    # which is the right failure: the fingerprint is the sync identity.
    text = "".join(f"{name}:{files[name]}\n" for name in sorted(files))
    derived = hashlib.sha256(text.encode("utf-8")).hexdigest()
    stated = manifest.get("fingerprint", "")
    if derived != stated:
        return False, (
            f"fingerprint mismatch: manifest says {str(stated)[:12]} but the files derive "
            f"{derived[:12]} -- the store is inconsistent, or research.fingerprint_of changed"
        )
    return True, f"{len(files)} files verified, fingerprint reproduces"


def fingerprint(store: Path) -> str | None:
    manifest = read_manifest(store)
    return manifest.get("fingerprint") if manifest else None


# ------------------------------------------------------------------ blob transport


def token() -> str | None:
    tok = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if tok:
        return tok.strip()
    root = repo_root()
    if root:
        envf = root / ".env.local"
        if envf.is_file():
            for line in envf.read_text().splitlines():
                if line.startswith("BLOB_READ_WRITE_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def blob_request(method: str, url: str, tok: str, data: bytes | None = None,
                 headers: dict | None = None, retries: int = 3) -> dict | bytes:
    hdrs = {"authorization": f"Bearer {tok}", "x-api-version": BLOB_API_VERSION}
    hdrs.update(headers or {})
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read()
                ctype = resp.headers.get("content-type", "")
                if "json" in ctype:
                    return json.loads(body)
                return body
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                last = f"HTTP {exc.code}: {detail}"
                continue
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                last = str(exc.reason)
                continue
            raise RuntimeError(f"network: {exc.reason}") from exc
    raise RuntimeError(last or "request failed")


def blob_put(tok: str, pathname: str, payload: bytes, content_type: str) -> dict:
    return blob_request(
        "PUT", f"{BLOB_API}/{pathname}", tok, data=payload,
        headers={
            "x-content-type": content_type,
            "x-add-random-suffix": "0",
            "x-cache-control-max-age": "0",
            "content-length": str(len(payload)),
        },
    )


def blob_list(tok: str, prefix: str) -> list[dict]:
    res = blob_request("GET", f"{BLOB_API}?prefix={prefix}&limit=1000", tok)
    return res.get("blobs", []) if isinstance(res, dict) else []


def blob_get(url: str) -> bytes:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def blob_delete(tok: str, urls: list[str]) -> None:
    blob_request("POST", f"{BLOB_API}/delete", tok,
                 data=json.dumps({"urls": urls}).encode(),
                 headers={"content-type": "application/json"})


def pointer(tok: str) -> dict | None:
    for b in blob_list(tok, POINTER):
        if b.get("pathname") == POINTER:
            try:
                return json.loads(blob_get(b["url"]))
            except Exception:  # noqa: BLE001 - a corrupt pointer is "no pointer"
                return None
    return None


# ------------------------------------------------------------------ commands


def cmd_status(args) -> int:
    root = repo_root()
    if not root:
        return fail("not inside a git repository")
    store = store_dir(root)
    local = fingerprint(store) if store.is_dir() else None
    local_ok, local_detail = verify_store(store) if store.is_dir() else (False, "no store on this machine")

    tok = token()
    remote, remote_err = None, None
    if not tok:
        remote_err = "BLOB_READ_WRITE_TOKEN not set (see the skill's Setup section)"
    else:
        try:
            ptr = pointer(tok)
            remote = ptr
        except RuntimeError as exc:
            remote_err = str(exc)

    same = bool(local and remote and local == remote.get("fingerprint"))
    return out({
        "ok": True,
        "store": str(store),
        "local": {"present": store.is_dir(), "fingerprint": local,
                  "verified": local_ok, "detail": local_detail,
                  "files": sorted(p.name for p in store.glob("*")) if store.is_dir() else []},
        "remote": remote or ({"error": remote_err} if remote_err else {"present": False}),
        "in_sync": same,
        "advice": (
            "in sync -- nothing to do" if same else
            "no local store; run `pull`" if not local and remote else
            "no remote store; run `push`" if local and not remote else
            "local and remote differ; `push` to publish yours or `pull` to take theirs"
            if local and remote else "nothing anywhere yet; build a store first"
        ),
    })


def cmd_push(args) -> int:
    root = repo_root()
    if not root:
        return fail("not inside a git repository")
    store = store_dir(root)
    if not store.is_dir():
        return fail("no store to push", store=str(store),
                    hint="build one: python -m seer_engine research_store --with-fundamentals")
    ok, detail = verify_store(store)
    if not ok:
        return fail(f"refusing to push a store that does not verify: {detail}")
    fp = fingerprint(store)
    tok = token()
    if not tok:
        return fail("BLOB_READ_WRITE_TOKEN not set", hint="see the skill's Setup section")

    try:
        ptr = pointer(tok)
    except RuntimeError as exc:
        return fail(f"could not read the remote pointer: {exc}")
    if ptr and ptr.get("fingerprint") == fp and not args.force:
        return out({"ok": True, "skipped": True, "fingerprint": fp,
                    "reason": "the remote already holds this exact store"})

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "store.tar.gz"
        with tarfile.open(archive, "w:gz", compresslevel=6) as tar:
            for path in sorted(store.iterdir()):
                if path.is_file():
                    tar.add(path, arcname=path.name)
        payload = archive.read_bytes()

    key = f"{PREFIX}/{fp}.tar.gz"
    try:
        put = blob_put(tok, key, payload, "application/gzip")
        meta = {
            "fingerprint": fp,
            "pathname": key,
            "url": put.get("url"),
            "bytes": len(payload),
            "pushed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pushed_from": os.uname().nodename,
            "manifest": read_manifest(store),
        }
        blob_put(tok, POINTER, json.dumps(meta, indent=2).encode(), "application/json")
    except RuntimeError as exc:
        return fail(f"upload failed: {exc}")

    pruned = _prune(tok, keep=args.keep) if args.keep else []
    return out({"ok": True, "pushed": True, "fingerprint": fp, "pathname": key,
                "bytes": len(payload), "mb": round(len(payload) / 1024 ** 2, 1),
                "verified": detail, "pruned": pruned})


def cmd_pull(args) -> int:
    root = repo_root()
    if not root:
        return fail("not inside a git repository")
    store = store_dir(root)
    tok = token()
    if not tok:
        return fail("BLOB_READ_WRITE_TOKEN not set", hint="see the skill's Setup section")

    try:
        ptr = pointer(tok)
    except RuntimeError as exc:
        return fail(f"could not read the remote pointer: {exc}")
    if not ptr:
        return fail("the remote holds no store yet", hint="push one from the other laptop first")

    want = ptr.get("fingerprint")
    local = fingerprint(store) if store.is_dir() else None
    if local == want and not args.force:
        return out({"ok": True, "skipped": True, "fingerprint": want,
                    "reason": "this machine already has that exact store"})
    if local and local != want and not args.force:
        return fail(
            "this machine has a DIFFERENT store and pulling would discard it",
            local_fingerprint=local, remote_fingerprint=want,
            hint="`push` yours first if it is the one you want to keep, or re-run with --force",
        )

    try:
        payload = blob_get(ptr["url"])
    except Exception as exc:  # noqa: BLE001
        return fail(f"download failed: {exc}")

    # Extract to a sibling temp dir, verify there, and only then swap. A half-written store
    # is worse than no store: `lab run` would read it.
    staging = store.parent / f".research.incoming-{os.getpid()}"
    backup = store.parent / f".research.replaced-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as fh:
            fh.write(payload)
            tmp_archive = Path(fh.name)
        with tarfile.open(tmp_archive, "r:gz") as tar:
            for member in tar.getmembers():
                # Never let an archive write outside the staging directory.
                if member.name != Path(member.name).name or member.issym() or member.islnk():
                    return fail(f"refusing an archive with an unsafe member: {member.name!r}")
            tar.extractall(staging)
        tmp_archive.unlink(missing_ok=True)

        ok, detail = verify_store(staging)
        if not ok:
            return fail(f"the downloaded store does not verify, nothing was installed: {detail}")
        got = fingerprint(staging)
        if got != want:
            return fail("downloaded fingerprint does not match the pointer; nothing installed",
                        expected=want, got=got)

        if store.is_dir():
            store.rename(backup)
        staging.rename(store)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and not store.exists():
            backup.rename(store)  # restore on a failed swap
        elif backup.exists():
            shutil.rmtree(backup, ignore_errors=True)

    return out({"ok": True, "pulled": True, "fingerprint": want, "verified": detail,
                "store": str(store), "pushed_from": ptr.get("pushed_from"),
                "pushed_at": ptr.get("pushed_at"),
                "mb": round(len(payload) / 1024 ** 2, 1)})


def _prune(tok: str, keep: int) -> list[str]:
    blobs = [b for b in blob_list(tok, f"{PREFIX}/") if b.get("pathname", "").endswith(".tar.gz")]
    blobs.sort(key=lambda b: b.get("uploadedAt", ""), reverse=True)
    doomed = blobs[keep:]
    if doomed:
        blob_delete(tok, [b["url"] for b in doomed])
    return [b["pathname"] for b in doomed]


def cmd_list(args) -> int:
    tok = token()
    if not tok:
        return fail("BLOB_READ_WRITE_TOKEN not set", hint="see the skill's Setup section")
    try:
        blobs = blob_list(tok, f"{PREFIX}/")
        ptr = pointer(tok)
    except RuntimeError as exc:
        return fail(str(exc))
    rows = [
        {"pathname": b.get("pathname"), "mb": round(int(b.get("size", 0)) / 1024 ** 2, 1),
         "uploadedAt": b.get("uploadedAt"),
         "current": bool(ptr and b.get("pathname", "").endswith(f"{ptr.get('fingerprint')}.tar.gz"))}
        for b in sorted(blobs, key=lambda b: b.get("uploadedAt", ""), reverse=True)
        if b.get("pathname", "").endswith(".tar.gz")
    ]
    return out({"ok": True, "versions": rows, "pointer": ptr})


def cmd_prune(args) -> int:
    tok = token()
    if not tok:
        return fail("BLOB_READ_WRITE_TOKEN not set")
    try:
        return out({"ok": True, "pruned": _prune(tok, keep=args.keep), "kept": args.keep})
    except RuntimeError as exc:
        return fail(str(exc))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="compare this machine's store with the remote")
    p = sub.add_parser("push", help="publish this machine's store")
    p.add_argument("--force", action="store_true", help="re-upload even if the remote matches")
    p.add_argument("--keep", type=int, default=KEEP_VERSIONS, help="versions to retain (0 = never prune)")
    p = sub.add_parser("pull", help="install the remote store on this machine")
    p.add_argument("--force", action="store_true", help="discard a differing local store")
    sub.add_parser("list", help="versions held remotely")
    p = sub.add_parser("prune", help="delete all but the newest N versions")
    p.add_argument("--keep", type=int, default=KEEP_VERSIONS)
    args = ap.parse_args()
    try:
        return {"status": cmd_status, "push": cmd_push, "pull": cmd_pull,
                "list": cmd_list, "prune": cmd_prune}[args.cmd](args)
    except KeyboardInterrupt:
        return fail("interrupted")


if __name__ == "__main__":
    sys.exit(main())
