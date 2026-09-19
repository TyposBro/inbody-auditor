"""Nosana coach slice — findings.json in, one coaching line out.

Live run (needs NOSANA_API_KEY in .env):

    python coach.py

Dry run (no network, writes nothing):

    python coach.py --dry-run

Offline override (no network, writes fallback):

    python coach.py --offline "Hold protein, keep lifting."

Stdlib only. Model id is picked at runtime via GET /v1/models, never hardcoded.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_BASE = "https://inference.nosana.com/v1"
CREDITS_LINK = "https://www.theaibuilders.dev/20260919-tokyo-credits/nosana"


def _load_env() -> None:
    for candidate in (HERE / ".env", Path.home() / "Documents/hacksprint-daytona/.env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        return


_load_env()


def base_url() -> str:
    return os.environ.get("NOSANA_BASE_URL", DEFAULT_BASE).rstrip("/")


def api_key() -> str:
    key = os.environ.get("NOSANA_API_KEY", "").strip().strip("'\"")
    if not key:
        raise RuntimeError("NOSANA_API_KEY not set")
    return key


def models(key: str | None = None, timeout: int = 20) -> list[str]:
    """Model ids currently served. GET /v1/models, never hardcode."""
    req = urllib.request.Request(
        base_url() + "/models",
        method="GET",
        headers={"Authorization": f"Bearer {key or api_key()}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        if exc.code == 402:
            raise RuntimeError("402 insufficient_credits from Nosana") from exc
        raise RuntimeError(f"HTTP {exc.code} from Nosana: {body}") from exc
    return [entry["id"] for entry in payload.get("data", [])]


def ask(model: str, prompt: str, key: str | None = None, timeout: int = 90) -> str:
    """One chat completion, temperature 0, max_tokens 300 (reasoning models burn tokens thinking)."""
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a direct gym coach. Reply with one short coaching line only, under 20 words, no emoji.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 300,
        }
    ).encode()
    req = urllib.request.Request(
        base_url() + "/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key or api_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")[:300]
        if exc.code == 402:
            raise RuntimeError("402 insufficient_credits from Nosana") from exc
        if exc.code == 401:
            raise RuntimeError(f"401 unauthorized. The Nosana key is wrong or expired. {err}") from exc
        raise RuntimeError(f"HTTP {exc.code} from Nosana: {err}") from exc
    msg = payload["choices"][0]["message"]
    text = (msg.get("content") or "").strip()
    if not text:
        # Reasoning models can return content None with thinking in reasoning field.
        reason = (msg.get("reasoning") or "").strip()
        text = reason.splitlines()[-1].strip() if reason else ""
    if not text:
        raise RuntimeError("Nosana returned empty content; retry once")
    return text


def build_prompt(f: dict) -> str:
    delta = f.get("delta_kg", 0)
    muscle = f.get("muscle_delta", 0)
    fat = f.get("fat_pct_delta", 0)
    protein = f.get("protein_floor_g", 0)
    start = f.get("start_weight", "?")
    now = f.get("now_weight", "?")
    return (
        f"InBody change: {start} to {now} kg (delta {delta} kg), "
        f"muscle {muscle:+} kg, fat {fat} pts, protein floor {protein} g/day. "
        "Write one short coaching line under 20 words, direct, no emoji."
    )


def offline_fallback(f: dict) -> str:
    delta = f.get("delta_kg", 0)
    muscle = f.get("muscle_delta", 0)
    protein = f.get("protein_floor_g", 0)
    return f"Down {abs(delta)} kg, muscle {muscle:+} kg — hold {protein} g protein, keep lifting."


def missing_key_message() -> str:
    return (
        "NOSANA_API_KEY not set.\n"
        f"Claim credits with your Luma email: {CREDITS_LINK}\n"
        "Put the key in .env as NOSANA_API_KEY, then rerun: python coach.py"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no network, prints prompt + plan, writes nothing")
    ap.add_argument("--offline", metavar="LINE", default=None, help="no network, write LINE as stubbed fallback")
    ap.add_argument("--findings", default=str(HERE / "findings.json"))
    args = ap.parse_args()

    path = Path(args.findings)
    findings = json.loads(path.read_text())
    prompt = build_prompt(findings)

    if args.dry_run:
        print(f"prompt: {prompt}")
        print("would-call plan (no network, writes nothing):")
        print(f"  1. GET {base_url()}/models -> pick served model id at runtime")
        print(f"  2. POST {base_url()}/chat/completions temperature=0 max_tokens=80")
        print("  3. write coach_line + coach_model -> findings.json (preserve all keys)")
        return 0

    if args.offline is not None:
        findings["coach_line"] = args.offline
        findings["coach_model"] = "offline-stubbed"
        path.write_text(json.dumps(findings, indent=2) + "\n")
        print(f"wrote offline fallback -> {path} (model=offline-stubbed)")
        return 0

    try:
        key = api_key()
    except RuntimeError:
        print(missing_key_message())
        return 1

    try:
        served = models(key=key, timeout=20)
        if not served:
            raise RuntimeError("No models served by Nosana right now")
        chat = [m for m in served if "embed" not in m.lower()]
        model = chat[0] if chat else served[0]
        line = ask(model, prompt, key=key)
    except RuntimeError as exc:
        if "402" in str(exc) or "insufficient_credits" in str(exc):
            print("402 insufficient credits from Nosana — keeping offline fallback (stubbed).")
            findings["coach_line"] = offline_fallback(findings)
            findings["coach_model"] = "stubbed-402"
            path.write_text(json.dumps(findings, indent=2) + "\n")
            print(f"wrote stubbed fallback -> {path}")
            return 0
        print(f"FAIL {exc}")
        return 1

    findings["coach_line"] = line
    findings["coach_model"] = model
    path.write_text(json.dumps(findings, indent=2) + "\n")
    print(f"coach ({model}): {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
