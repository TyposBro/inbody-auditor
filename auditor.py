"""InBody Story Auditor MVP — backend slice.

CSV in, verdict JSON out, computed INSIDE a Daytona sandbox.

Live run (creates exactly ONE sandbox, max 2 vCPUs of the 10 allowed):

    python3 auditor.py

Dry run (no sandbox, stdlib only):

    python3 auditor.py --dry-run [--limit N]

Limit rows pushed (header + first N rows):

    python3 auditor.py --limit 3
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import py_compile
from pathlib import Path

HERE = Path(__file__).parent

# Tier cap: 1 vCPU per sandbox, max 2 sandboxes. This slice uses exactly ONE.
TTL_MINUTES = 15


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


def push(sandbox, local_path: Path, remote_path: str) -> None:
    """Write a local file into the sandbox without quoting hazards."""
    payload = base64.b64encode(local_path.read_bytes()).decode()
    sandbox.process.code_run(
        "import base64, pathlib\n"
        f"p = pathlib.Path({remote_path!r})\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        f"p.write_bytes(base64.b64decode({payload!r}))\n"
        "print('wrote', p, p.stat().st_size, 'bytes')\n"
    )


def push_bytes(sandbox, data: bytes, remote_path: str) -> None:
    """Write in-memory bytes into the sandbox without quoting hazards."""
    payload = base64.b64encode(data).decode()
    sandbox.process.code_run(
        "import base64, pathlib\n"
        f"p = pathlib.Path({remote_path!r})\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        f"p.write_bytes(base64.b64decode({payload!r}))\n"
        "print('wrote', p, p.stat().st_size, 'bytes')\n"
    )


def load_rows(limit: int | None) -> bytes:
    """Read sample_inbody.csv, optionally cap to header + first N rows."""
    with open(HERE / "sample_inbody.csv", newline="") as f:
        reader = list(csv.reader(f))
    header, body = reader[0], reader[1:]
    if limit is not None:
        body = body[:limit]
    lines = [",".join(header)] + [",".join(r) for r in body]
    return ("\n".join(lines) + "\n").encode()


def dry_run(limit: int | None) -> int:
    for name in ("sample_inbody.csv", "analyze.py", "auditor.py"):
        p = HERE / name
        if not p.exists():
            print(f"missing: {name}")
            return 1
    for name in ("analyze.py", "auditor.py"):
        py_compile.compile(str(HERE / name), doraise=True)
        print(f"compile ok: {name}")
    n_rows = len(load_rows(limit).decode().strip().splitlines()) - 1
    print("would-run plan (no sandbox created):")
    print(f"  1. create ONE sandbox, set_ttl({TTL_MINUTES})")
    print(f"  2. push sample_inbody.csv ({n_rows} rows) -> /home/daytona/input.csv")
    print("  3. push analyze.py -> /home/daytona/analyze.py")
    print("  4. create_signed_preview_url for public URL")
    print("  5. exec: python3 /home/daytona/analyze.py /home/daytona/input.csv")
    print("  6. save stdout -> findings.json locally, print it")
    print("  7. delete sandbox with wait=True")
    return 0


def live(limit: int | None) -> int:
    from daytona import Daytona, DaytonaConfig  # noqa: E402  (lazy: dry-run stays stdlib-only)

    daytona = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"],
                                    target=os.environ.get("DAYTONA_TARGET", "us")))
    sandbox = None
    try:
        print("creating sandbox (1 of max 2)...", flush=True)
        sandbox = daytona.create()
        sandbox.set_ttl(TTL_MINUTES)
        push_bytes(sandbox, load_rows(limit), "/home/daytona/input.csv")
        push(sandbox, HERE / "analyze.py", "/home/daytona/analyze.py")
        # Signed preview URL pattern (no secret echoed; informational only).
        signed = sandbox.create_signed_preview_url(8000, expires_in_seconds=TTL_MINUTES * 60)
        print(f"sandbox URL (informational): {signed.url}", flush=True)
        result = sandbox.process.exec(
            "python3 /home/daytona/analyze.py /home/daytona/input.csv",
            timeout=120,
        )
        out = (result.result or "").strip()
        findings = json.loads(out)  # fail loudly if the sandbox printed non-JSON
        (HERE / "findings.json").write_text(json.dumps(findings, indent=2))
        print((HERE / "findings.json").read_text())
        return 0
    finally:
        # wait=True or the quota orphans the sandbox.
        if sandbox is not None:
            sandbox.delete(wait=True)
            print("sandbox deleted (wait=True)", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    if args.dry_run:
        return dry_run(args.limit)
    return live(args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
