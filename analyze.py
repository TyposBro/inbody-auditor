"""InBody Story Auditor — analyze step (stdlib only).

Reads a CSV with header: date,weight_kg,muscle_kg,fat_pct
Outputs verdict JSON to stdout.

    python3 analyze.py /home/daytona/input.csv
"""

from __future__ import annotations

import csv
import json
import sys


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/home/daytona/input.csv"
    try:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print(json.dumps({"error": f"input not found: {path}"}))
        return 1
    if not rows:
        print(json.dumps({"error": "empty csv"}))
        return 1

    first, last = rows[0], rows[-1]
    start_weight = float(first["weight_kg"])
    now_weight = float(last["weight_kg"])
    delta_kg = round(now_weight - start_weight, 1)
    muscle_delta = round(float(last["muscle_kg"]) - float(first["muscle_kg"]), 1)
    fat_pct_delta = round(float(last["fat_pct"]) - float(first["fat_pct"]), 1)
    protein_floor_g = int(round(now_weight * 2.0))

    verdicts = [
        f"Down {abs(delta_kg):.1f} kg total ({start_weight:.1f} to {now_weight:.1f})",
        f"Muscle {'held' if muscle_delta >= 0 else 'lost'} ({muscle_delta:+.1f} kg), fat {fat_pct_delta:+.1f} pts",
        f"Protein floor {protein_floor_g} g/day at {now_weight:.1f} kg",
    ]

    chart_points = [
        {"date": r["date"], "weight": float(r["weight_kg"])} for r in rows
    ]

    print(json.dumps({
        "start_weight": start_weight,
        "now_weight": now_weight,
        "delta_kg": delta_kg,
        "muscle_delta": muscle_delta,
        "fat_pct_delta": fat_pct_delta,
        "protein_floor_g": protein_floor_g,
        "verdicts": verdicts,
        "chart_points": chart_points,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
