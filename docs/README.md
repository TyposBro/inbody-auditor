# InBody Auditor — Daytona HackSprint Seoul 2026-09-19

Your transformation as a demo: 105.8 to 98.7 kg, muscle held +0.3, fat -3.1 pts, protein floor 197 g/day. Free core, no subscription, story not claim.

## Live proof

- Daytona: CSV analysis inside a fresh sandbox per run, signed preview URL opens in any browser, wait-True teardown. Tier cap 10 vCPU, create median 2.6 s.
- Nosana: coach.py live via inference v1, model qwen/qwen3.8-27b picked at runtime, embed models skipped, max_tokens 300 for reasoning models. Line shows on report.
- DNSimple: publish.py prod live, hosted zone auditor-demo.test, TXT inbody-20260919, record 84669063, HTTP 201, account 178711.

## 90-sec demo

1. `python auditor.py` — one sandbox computes findings.json, deletes clean.
2. `python coach.py` — Nosana coach line into findings.json.
3. `python render.py` — chart plus coach line into report.html.
4. `python serve.py` — run in background, open signed URL on projector.
5. Show publish.json record id on final slide.

Dry runs: every script supports --dry-run, zero network, zero sandbox.

## Files

auditor.py, analyze.py, sample_inbody.csv, coach.py, render.py, report.html, serve.py, publish.py, findings.json, publish.json, deck.pdf, site/, docs/.

## Links

- Repo: https://github.com/TyposBro/inbody-auditor
- Live: https://auditor.typosbro.me
- Deck: https://auditor.typosbro.me/deck.pdf and deck.html
- Report: https://auditor.typosbro.me/report.html
