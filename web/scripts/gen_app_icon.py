#!/usr/bin/env python3
"""Generate the Seer home-screen eye via OpenRouter (spends money).

    python3 scripts/gen_app_icon.py --dry-run
    python3 scripts/gen_app_icon.py coral
    python3 scripts/gen_app_icon.py coral --seed 7 --note "the spiral tail is too thin"

Candidates land in `web/scripts/.icon/_candidates/coral.aNN.png` with a `.txt` sidecar carrying the
exact prompt. Promote one to `web/scripts/.icon/eye.png`, then `python3 scripts/make_icon_assets.py`
composes the Sigma pupil in and writes the shipped PNGs.

Ported from run-insights' tools/gen_app_icon.py: same `.env.local`-first key read (prints the
source, never the value), the `RES_OPTIONS=no-aaaa` WSL DNS workaround, and the JSON POST to
`/images/generations` (there is no `/images/edits` on OpenRouter — it 404s).

THE KEY. `OPENROUTER_API_KEY` from web/.env.local. It is read here only; nothing under app/, lib/
or components/ may name it.

stdlib only. The compositor needs PIL; this does not.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn

# Inherited from run-insights, where AAAA lookups were measured hanging 4-12s under WSL
# before every request. Must be set before any DNS resolution happens.
os.environ.setdefault("RES_OPTIONS", "no-aaaa")

WEB = Path(__file__).resolve().parent.parent
ROOT = WEB.parent
CANDIDATES = WEB / "scripts" / ".icon" / "_candidates"

BASE = "https://openrouter.ai/api/v1"
KEY_VAR = "OPENROUTER_API_KEY"
MODEL = "qwen/qwen-image-3-pro"

# `resolution` and `aspect_ratio`, NOT `size`. OpenRouter ignores `size` and defaults to 2K, so
# omitting these silently returns a 2048² master *after* the money is spent. RESOLUTION is an enum
# there ('1K' | '2K'), not a pixel count.
RESOLUTION = "1K"
ASPECT_RATIO = "1:1"
MASTER_PX = 1024  # what '1K' means. Recorded in the sidecar, not sent.

STYLE_VERSION = "v1"

# --------------------------------------------------------------------------- #
# The palette — web/app/globals.css, light scheme
# --------------------------------------------------------------------------- #
INK = "#1d1c1a"  # --ink / --splash-ink
CORAL = "#f47862"  # --coral / --splash, what the tile and the launch splash are painted

# --------------------------------------------------------------------------- #
# The style block
# --------------------------------------------------------------------------- #
# The model draws the eye only. The pupil is left EMPTY on purpose: the Lucide Sigma (the A · Quant
# icon) is composited into it by code, because an image model cannot be trusted to draw a crisp
# glyph and the NO TEXT rule would fight it anyway.
STYLE = f"""
A single flat vector app icon for a mobile stock-picking app, in the manner of a modern iOS
home-screen icon — one bold graphic idea, drawn cleanly, readable at a glance.

FULL BLEED — THE MOST IMPORTANT RULE. The background colour fills the entire square image, edge to
edge and corner to corner. Do NOT draw a rounded-corner tile, a squircle, a circle or any badge
shape sitting on a backdrop. Do NOT render a phone, a screen, a device frame, a mockup or a drop
shadow. No border, no frame, no vignette, no glow, no white margin. The operating system applies its
own rounded mask afterwards.

NO TEXT ANYWHERE. No word, no letter, no number, no hieroglyph cartouche, no watermark, no glyph in
any alphabet. Any text is an automatic rejection.

GENEROUS MARGIN. The eye sits centred with clear empty space on all four sides, about 70 percent of
the image width, staying well inside the middle — nothing near an edge or corner.

THE SUBJECT: a single Ancient Egyptian Eye of Horus (wedjat), the right eye, drawn as a bold
pictogram in solid near-black {INK}: the thick arched eyebrow above, the almond-shaped eye outline,
the vertical teardrop marking falling straight down below the eye, and the curling spiral tail
sweeping down and back from beneath the outer corner. Thick, even, confident strokes of one weight.

THE PUPIL IS EMPTY — CRITICAL. Inside the almond outline there is NO pupil, NO iris, NO dot, NO
circle, NO black disk. The whole inside of the almond is plain flat background colour, completely
empty, so a symbol can be placed there later. Leave the centre of the eye open and clear.

TECHNIQUE: flat vector fills only. Two colours in the entire image: the flat background and the
near-black eye. No gradients, no gold, no shading, no glow, no bevel, no texture, no paper grain, no
3D, no ornament, no extra decoration. Smooth crisp curves, nothing thinner than a confident stroke —
hairlines vanish at 40 pixels, which is the size this icon is judged at.
""".strip()

VARIANTS = {
    "coral": f"""
BACKGROUND: one flat solid field of warm coral {CORAL}, filling the whole square, and nothing else.
No sun, no pyramid, no rays, no pattern, no secondary shape.
""",
}


def build_prompt(variant: str, note: str | None = None) -> str:
    parts = [STYLE, "", f"THIS VARIANT — {variant}:", VARIANTS[variant].strip()]
    if note:
        # After the variant block, so a correction reads as a refinement of this image rather than
        # as an amendment to the style.
        parts += ["", f"CORRECTION FOR THIS ATTEMPT: {note}"]
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# The key
# --------------------------------------------------------------------------- #

def read_api_key() -> str:
    """`.env.local` first, then the environment. Prints WHICH, never the value.

    A stale exported shell variable silently winning over the file you just edited is a confusing
    hour, and one printed word ends it.
    """
    env_file = WEB / ".env.local"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() != KEY_VAR:
                continue
            value = value.strip().strip('"').strip("'")
            if value:
                print(f"key source: .env.local ({KEY_VAR})")
                return value

    value = os.environ.get(KEY_VAR, "").strip()
    if value:
        print(f"key source: environment ({KEY_VAR})")
        return value

    die(f"{KEY_VAR} is in neither .env.local nor the environment.\n"
        f"  Paste the value into web/.env.local by\n"
        f"  hand; that file is gitignored. Do not echo it, pipe it or let a\n"
        f"  script print it.")


# --------------------------------------------------------------------------- #
# The request
# --------------------------------------------------------------------------- #

def post_generation(key: str, model: str, prompt: str, seed: int | None = None) -> bytes:
    """OpenRouter's single image endpoint.

    **There is no `/images/edits` here.** It 404s on this provider — not "unknown model", the route
    does not exist. The chat-completions route (`modalities: ["image", "text"]`) also produces
    images on this provider, but `qwen/qwen-image-3-pro` refuses it with "no endpoints found that
    support the requested output modalities". Do not reach for it: this endpoint is the one the
    model answers.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "resolution": RESOLUTION,
        "aspect_ratio": ASPECT_RATIO,
        "n": 1,
    }
    if seed is not None:
        payload["seed"] = seed

    req = urllib.request.Request(
        f"{BASE}/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    return send(req)


def send(req) -> bytes:
    started = time.monotonic()
    try:
        # A Qwen call has been measured at just over two minutes on the deck this descends from,
        # so this ceiling is doing real work rather than guarding a hypothetical.
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:2000]
        die(f"HTTP {exc.code} from the image API\n{detail}\n\n"
            f"  If this says the model is unknown, list what the provider actually\n"
            f"  serves — and note that OpenRouter's image models are NOT in\n"
            f"  /api/v1/models, which is why they look absent:\n"
            f"    curl -s {BASE}/images/models | python3 -m json.tool | grep '\"id\"'")
    except urllib.error.URLError as exc:
        die(f"could not reach {BASE}: {exc.reason}")

    elapsed = time.monotonic() - started
    data = payload.get("data") or []
    if not data or "b64_json" not in data[0]:
        die(f"response had no b64_json image:\n{json.dumps(payload)[:2000]}")
    print(f"generated in {elapsed:.1f}s")
    return base64.b64decode(data[0]["b64_json"])


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def next_attempt_path(variant: str) -> Path:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    used = {
        int(m.group(1))
        for p in CANDIDATES.glob(f"{variant}.a*.png")
        if (m := re.fullmatch(rf"{re.escape(variant)}\.a(\d+)\.png", p.name))
    }
    return CANDIDATES / f"{variant}.a{(max(used) + 1) if used else 1:02d}.png"


def write_sidecar(png_path: Path, variant: str, model: str, prompt: str, seed: int | None) -> Path:
    """The exact prompt beside the exact image, so a candidate you like in six weeks can be
    explained and regenerated instead of guessed at."""
    sidecar = png_path.with_suffix(".txt")
    sidecar.write_text(
        "\n".join([
            f"variant:        {variant}",
            "provider:       openrouter",
            f"model:          {model}",
            f"seed:           {seed if seed is not None else '(none)'}",
            f"style version:  {STYLE_VERSION}",
            f"resolution:     {RESOLUTION} {ASPECT_RATIO}  (expect {MASTER_PX}²)",
            f"image sha256:   {hashlib.sha256(png_path.read_bytes()).hexdigest()}",
            "",
            "--- prompt as sent ---",
            prompt,
            "",
        ]),
        encoding="utf-8",
    )
    return sidecar


# --------------------------------------------------------------------------- #

def rel(path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def die(message) -> NoReturn:
    print(f"\nerror: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the Seer home-screen eye.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Promote a chosen candidate to scripts/.icon/eye.png, then run "
               "scripts/make_icon_assets.py to write the shipped PNGs.",
    )
    parser.add_argument("variant", nargs="?", choices=sorted(VARIANTS),
                        help="which variant to draw")
    parser.add_argument("--all", action="store_true",
                        help="print every variant's prompt; only legal with --dry-run")
    parser.add_argument("--dry-run", action="store_true",
                        help="assemble and print the prompt; no key, no network, no file")
    parser.add_argument("--note", help="a correction appended after the variant block")
    parser.add_argument("--model", default=MODEL, help=f"image model (default {MODEL})")
    parser.add_argument("--seed", type=int, help="reproducibility; qwen-image-3-pro honours it")
    args = parser.parse_args()

    if args.all:
        if not args.dry_run:
            die("--all is only legal with --dry-run. One image per invocation, so the "
                "look-at-it step stays real.")
        targets = sorted(VARIANTS)
    elif args.variant:
        targets = [args.variant]
    else:
        die("name a variant, or pass --all --dry-run. Choices: " + ", ".join(sorted(VARIANTS)))

    # Two loops rather than one with a `continue`, so the key is a `str` and not a `str | None`
    # threaded through a call that cannot accept None.
    if args.dry_run:
        for variant in targets:
            prompt = build_prompt(variant, args.note)
            print(f"\n{'=' * 78}\n{variant}  ({len(prompt)} chars)\n{'=' * 78}\n{prompt}")
        return

    # Read before the first request, so a missing key costs nothing instead of failing after the
    # first image is already paid for.
    key = read_api_key()

    for variant in targets:
        prompt = build_prompt(variant, args.note)
        print(f"\n{variant} — {args.model}")
        png = post_generation(key, args.model, prompt, args.seed)
        path = next_attempt_path(variant)
        path.write_bytes(png)
        sidecar = write_sidecar(path, variant, args.model, prompt, args.seed)
        print(f"wrote {rel(path)} ({len(png):,} bytes)")
        print(f"      {rel(sidecar)}")


if __name__ == "__main__":
    main()
