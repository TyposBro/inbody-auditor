"""Serve report.html from ONE Daytona sandbox via signed preview URL.

    python serve.py               # render + serve, keep alive 12 min, then delete
    python serve.py --write-only  # only regenerate report.html, no sandbox
"""

from __future__ import annotations

import argparse
import base64
import os
import time
from pathlib import Path

HERE = Path(__file__).parent


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

TTL = int(os.environ.get("SANDBOX_TTL_MINUTES", "15"))

from render import main as render_main  # noqa: E402


def serve() -> int:
    from daytona import Daytona, DaytonaConfig

    report = HERE / "report.html"
    if not report.exists():
        print("no report.html yet, rendering first.")
        render_main()

    daytona = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"],
                                    target=os.environ.get("DAYTONA_TARGET", "us")))
    sandbox = daytona.create()
    try:
        sandbox.set_ttl(TTL)
        print(f"serving from sandbox {sandbox.id}")

        payload = base64.b64encode(report.read_bytes()).decode()
        sandbox.process.code_run(
            "import base64, pathlib\n"
            "p = pathlib.Path('/home/daytona/report.html')\n"
            f"p.write_bytes(base64.b64decode({payload!r}))\n"
            "print('wrote', p, p.stat().st_size, 'bytes')\n"
        )
        sandbox.process.exec(
            "cd /home/daytona && nohup python3 -m http.server 3000 >/tmp/http.log 2>&1 &")
        time.sleep(1.5)
        probe = sandbox.process.exec(
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/report.html")
        print(f"local probe: HTTP {probe.result.strip()}")

        # NOT get_preview_link (401 in browser without header). Signed URL
        # bakes the token into the hostname: opens anywhere, no headers.
        signed = sandbox.create_signed_preview_url(3000, expires_in_seconds=900)
        print("\nPREVIEW (opens in any browser, expires in 15 min):")
        print(f"  {signed.url}")
        print("sandbox TTL is set, keeping alive 12 min for the demo.")
        time.sleep(12 * 60)
        return 0
    finally:
        daytona.delete(sandbox, wait=True)
        print("sandbox deleted.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-only", action="store_true",
                        help="only regenerate report.html, no sandbox")
    args = parser.parse_args()
    if args.write_only:
        return render_main()
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
