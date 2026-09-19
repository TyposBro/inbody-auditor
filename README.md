# InBody Story Auditor — frontend slice
Findings.json in, shareable chart page out via Daytona signed preview URL.

## 90-sec demo
1. `python render.py` — writes report.html (105.8 to 98.7, chart, verdicts).
2. `python serve.py` — one sandbox, pushes report.html, prints signed URL.
3. Open the URL in any browser, no headers — chart plus verdicts plus footer.

## Notes
Single self-contained HTML, canvas chart, dark monospace, no CDN, no fetch.
Serve uses `create_signed_preview_url(3000, expires 900)` — never `get_preview_link` (401).
TTL 15, max 1 sandbox, keep-alive 12 min, delete with wait True.
Nosana solver: stubbed offline — findings.json is a fixture, Daytona serving is real.
Port 3000, health-checked via curl before printing the URL.

## Nosana coach
Nosana path: findings.json -> coach.py -> coach_line + coach_model in findings.json.
Live: `python coach.py` (model via GET /v1/models, temp 0, max_tokens 80).
Fallback: `--dry-run` prints plan only; `--offline "LINE"` writes stubbed line.
No key/402 keeps offline stubbed line; coach.py prints credits link.

## Publish proof (DNSimple)
`python publish.py --dry-run` — call plan with paths, no network, writes publish.json stub.
Sandbox default (https://api.sandbox.dnsimple.com/v2); sandbox zones do NOT resolve publicly.
Live: set DNSIMPLE_TOKEN in .env, then `python publish.py --sandbox`
Prod: `python publish.py --prod` (uses https://api.dnsimple.com/v2, irreversible).
