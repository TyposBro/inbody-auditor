"""Publish report proof via DNSimple API v2 (stdlib urllib only).

Reads findings.json + report.html sha1 (first 8), creates a hosted zone
named by DNSIMPLE_ZONE and a TXT record inbody-<date> with preview URL or hash.

Sandbox default (no --prod flag needed):

    python publish.py --dry-run     # call plan, no network, writes publish.json stub
    python publish.py --sandbox     # live sandbox run (default base)
    python publish.py --prod        # prod base, irreversible warning

Auth: Authorization Bearer DNSIMPLE_TOKEN (sandbox token from
app.sandbox.dnsimple.com/user). Never prints the token.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
FINDINGS = HERE / "findings.json"
REPORT = HERE / "report.html"
OUT = HERE / "publish.json"

PROD_BASE = "https://api.dnsimple.com/v2"
SANDBOX_BASE = "https://api.sandbox.dnsimple.com/v2"
DEFAULT_ZONE = "auditor-demo.test"
RECORD_TTL = 300


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


def report_hash() -> str:
    if REPORT.exists():
        return hashlib.sha1(REPORT.read_bytes()).hexdigest()[:8]
    # fallback so --dry-run still works without report.html
    if FINDINGS.exists():
        return hashlib.sha1(FINDINGS.read_bytes()).hexdigest()[:8]
    return "no-report"


def record_name_today() -> str:
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    return f"inbody-{day}"


def api_call(method: str, url: str, token: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status = e.code
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {"raw": body}
    return status, parsed


def missing_token_exit() -> int:
    print("missing DNSIMPLE_TOKEN — no network call made.", file=sys.stderr)
    print("sandbox signup: app.sandbox.dnsimple.com/signup", file=sys.stderr)
    print("token page: app.sandbox.dnsimple.com/user", file=sys.stderr)
    print("credits: https://www.theaibuilders.dev/20260919-tokyo-credits/dnsimple (use Luma email)", file=sys.stderr)
    print("put token in .env as DNSIMPLE_TOKEN, rerun with --sandbox", file=sys.stderr)
    return 2


def dry_run(base: str, zone: str, record: str, content: str, digest: str) -> int:
    account = "<account_id from GET /v2/whoami>"
    plan = [
        f"GET {base}/whoami -> account id",
        f"POST {base}/{account}/domains {{\"name\": \"{zone}\"}} -> hosted zone",
        f"POST {base}/{account}/zones/{zone}/records "
        f"{{\"name\": \"{record}\", \"type\": \"TXT\", \"content\": \"{content}\", \"ttl\": {RECORD_TTL}}}",
    ]
    print("dry-run call plan (no network):")
    for step in plan:
        print(f"  {step}")
    stub = {
        "mode": "dry-run",
        "sandbox": base == SANDBOX_BASE,
        "base": base,
        "zone": zone,
        "record_name": record,
        "record_type": "TXT",
        "content": content,
        "hash": digest,
        "account_id": None,
        "record_id": None,
        "status": "stub",
    }
    OUT.write_text(json.dumps(stub, indent=2))
    print(f"wrote {OUT.name} stub (sandbox={stub['sandbox']}, zone={zone}, record={record})")
    return 0


def live(base: str, zone: str, record: str, content: str, digest: str) -> int:
    token = os.environ.get("DNSIMPLE_TOKEN", "").strip()
    if not token:
        return missing_token_exit()

    status, who = api_call("GET", f"{base}/whoami", token)
    print(f"GET /v2/whoami -> HTTP {status}")
    account_id = None
    try:
        account_id = who["data"]["account"]["id"]
    except (KeyError, TypeError):
        pass
    if not account_id:
        # Fresh event tokens can return account null on whoami; fall back to accounts list.
        s2, acc = api_call("GET", f"{base}/accounts", token)
        try:
            account_id = acc["data"][0]["id"]
            print(f"whoami account null, using accounts[0] -> {account_id}")
        except (KeyError, TypeError, IndexError):
            print(f"account lookup failed: whoami={json.dumps(who)[:200]} accounts={json.dumps(acc)[:200]}")
            return 1
    print(f"account id: {account_id}")

    status, dom = api_call("POST", f"{base}/{account_id}/domains", token, {"name": zone})
    print(f"POST /v2/{account_id}/domains (zone={zone}) -> HTTP {status}")
    if status not in (200, 201, 400):
        print(f"domain create failed: {json.dumps(dom)[:500]}")
        return 1

    payload = {"name": record, "type": "TXT", "content": content, "ttl": RECORD_TTL}
    status, rec = api_call("POST", f"{base}/{account_id}/zones/{zone}/records", token, payload)
    print(f"POST /v2/{account_id}/zones/{zone}/records -> HTTP {status}")
    try:
        record_id = rec["data"]["id"]
    except (KeyError, TypeError):
        print(f"record create failed: {json.dumps(rec)[:500]}")
        return 1

    print(f"zone: {zone}")
    print(f"record id: {record_id}")
    print(f"API status: {status}")
    OUT.write_text(json.dumps({
        "mode": "live",
        "sandbox": base == SANDBOX_BASE,
        "base": base,
        "zone": zone,
        "record_name": record,
        "record_type": "TXT",
        "content": content,
        "hash": digest,
        "account_id": account_id,
        "record_id": record_id,
        "status": status,
    }, indent=2))
    print(f"wrote {OUT.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no network, print call plan, write publish.json stub")
    ap.add_argument("--sandbox", action="store_true", help="live sandbox run (default base)")
    ap.add_argument("--prod", action="store_true", help="use prod base (irreversible)")
    args = ap.parse_args()

    base = PROD_BASE if args.prod else SANDBOX_BASE
    if args.prod:
        print("WARN: --prod uses https://api.dnsimple.com/v2 — irreversible real zone/record.", file=sys.stderr)

    zone = os.environ.get("DNSIMPLE_ZONE", DEFAULT_ZONE).strip() or DEFAULT_ZONE
    digest = report_hash()
    record = record_name_today()
    content = os.environ.get("PREVIEW_URL", "").strip() or digest

    if FINDINGS.exists():
        try:
            json.loads(FINDINGS.read_text())
        except json.JSONDecodeError as e:
            print(f"findings.json invalid: {e}", file=sys.stderr)
            return 1
    else:
        print("missing findings.json", file=sys.stderr)
        return 1

    if args.dry_run:
        return dry_run(base, zone, record, content, digest)
    return live(base, zone, record, content, digest)


if __name__ == "__main__":
    raise SystemExit(main())
