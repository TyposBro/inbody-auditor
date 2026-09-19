"""Render findings.json + sample_inbody.csv as a shareable chart page.

    python render.py            # write report.html only
"""

from __future__ import annotations

import csv
import html
import json
import time
from pathlib import Path

HERE = Path(__file__).parent
FINDINGS = HERE / "findings.json"
CSV = HERE / "sample_inbody.csv"
REPORT = HERE / "report.html"

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>InBody Auditor</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ background:#0b0d10; color:#e6e9ef; font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
         margin:0; padding:32px; max-width:760px; }}
  h1 {{ font-size:20px; margin:0 0 4px; font-weight:600; }}
  .sub {{ color:#8b93a1; margin-bottom:24px; }}
  .stats {{ display:flex; gap:28px; margin-bottom:24px; flex-wrap:wrap; }}
  .stat b {{ display:block; font-size:26px; font-weight:600; }}
  .stat span {{ color:#8b93a1; font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
  canvas {{ width:100%; height:260px; background:#11141a; border:1px solid #232833;
            border-radius:8px; margin-bottom:24px; }}
  ul {{ list-style:none; margin:0 0 24px; padding:0; }}
  li {{ padding:10px 12px; border-radius:6px; margin-bottom:6px; }}
  .ok {{ background:#0f3d24; color:#5ee89b; border:1px solid #1d6b40; }}
  .warn {{ background:#3a2f10; color:#ffd479; border:1px solid #6f5a17; }}
  .bad {{ background:#3d1113; color:#ff8f8f; border:1px solid #7a2024; }}
  footer {{ margin-top:28px; color:#6b7280; font-size:12px; }}
</style>
<h1>InBody Auditor</h1>
<div class="sub">{start} kg &rarr; {end} kg &middot; {lost} kg lost &middot; generated {stamp}</div>
<div class="stats">
  <div class="stat"><b>{lost} kg</b><span>lost</span></div>
  <div class="stat"><b>{muscle} kg</b><span>muscle held</span></div>
  <div class="stat"><b>{protein} g</b><span>protein floor</span></div>
</div>
<canvas id="c" width="700" height="260"></canvas>
<script>
var DATA = {data_json};
(function () {{
  var c = document.getElementById("c"), x = c.getContext("2d");
  var W = c.width, H = c.height, pad = 36;
  var ws = DATA.map(function (r) {{ return r.w; }});
  var lo = Math.min.apply(null, ws) - 1, hi = Math.max.apply(null, ws) + 1;
  function px(i) {{ return pad + i * (W - 2 * pad) / Math.max(1, DATA.length - 1); }}
  function py(w) {{ return H - pad - (w - lo) / (hi - lo) * (H - 2 * pad); }}
  x.strokeStyle = "#232833"; x.fillStyle = "#6b7280"; x.font = "11px monospace";
  for (var g = 0; g <= 4; g++) {{
    var v = lo + (hi - lo) * g / 4, y = py(v);
    x.beginPath(); x.moveTo(pad, y); x.lineTo(W - pad, y); x.stroke();
    x.fillText(v.toFixed(1), 4, y + 4);
  }}
  x.strokeStyle = "#5ee89b"; x.lineWidth = 2; x.beginPath();
  DATA.forEach(function (r, i) {{ i ? x.lineTo(px(i), py(r.w)) : x.moveTo(px(i), py(r.w)); }});
  x.stroke();
  x.fillStyle = "#e6e9ef";
  DATA.forEach(function (r, i) {{
    x.beginPath(); x.arc(px(i), py(r.w), 3, 0, 7); x.fill();
    if (i % 2 === 0 || i === DATA.length - 1) x.fillText(r.d.slice(5), px(i) - 12, H - 12);
  }});
}})();
</script>
<ul>
{verdicts}
</ul>
<footer>Free core, no subscription: this page is the story. The chart is yours to share.</footer>
"""


def load() -> tuple[dict, list[dict]]:
    findings = json.loads(FINDINGS.read_text()) if FINDINGS.exists() else {}
    rows: list[dict] = []
    if CSV.exists():
        with open(CSV, newline="") as f:
            for r in csv.DictReader(f):
                try:
                    rows.append({"d": r["date"].strip(), "w": float(r["weight_kg"])})
                except (KeyError, ValueError):
                    continue
    return findings, rows


def build(findings: dict, rows: list[dict]) -> str:
    start = float(findings.get("start_weight", rows[0]["w"] if rows else 105.8))
    end = float(findings.get("end_weight", findings.get("now_weight", rows[-1]["w"] if rows else 98.7)))
    lost = round(start - end, 1)
    muscle = findings.get("muscle_held_kg", None)
    if muscle is None:
        md = findings.get("muscle_delta", None)
        muscle = f"{md:+.1f}" if isinstance(md, (int, float)) else "held"
    protein = findings.get("protein_floor_g", 150)
    verdicts = findings.get("verdicts", [])
    items = "\n".join(
        (
            f'<li class="{html.escape(str(v.get("status", "ok")))}">'
            f'<b>{html.escape(str(v.get("check", "")))}</b> — '
            f'{html.escape(str(v.get("detail", "")))}</li>'
            if isinstance(v, dict) else
            f'<li class="ok">{html.escape(str(v))}</li>'
        )
        for v in verdicts
    )
    coach = str(findings.get("coach_line", "")).strip()
    cmodel = str(findings.get("coach_model", "")).strip()
    if coach:
        items += f'\n<li class="warn">Nosana coach [{html.escape(cmodel)}] — {html.escape(coach)}</li>'
    return PAGE.format(
        start=f"{start:.1f}", end=f"{end:.1f}", lost=f"{lost:.1f}",
        muscle=muscle, protein=protein,
        stamp=time.strftime("%H:%M:%S"),
        data_json=json.dumps(rows),
        verdicts=items,
    )


def main() -> int:
    findings, rows = load()
    html_out = build(findings, rows)
    REPORT.write_text(html_out)
    print(f"wrote {REPORT.name} ({len(html_out)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
