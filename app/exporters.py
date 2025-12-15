"""
Export helpers.

We keep exporters small and dependency-free:
- JSON: pretty printed
- CSV: 1 row per record (daily temps serialized)
- Markdown: simple report table
"""

from __future__ import annotations
import csv
import io
import json
from typing import List, Dict, Any


def export_json(records: List[Dict[str, Any]]) -> str:
    """Export list of records as pretty JSON."""
    return json.dumps(records, indent=2, default=str)


def export_csv(records: List[Dict[str, Any]]) -> str:
    """
    Export list of records as CSV.

    We "flatten" records to one row each.
    daily_temps (list) becomes a JSON string in a cell.
    """
    output = io.StringIO()
    if not records:
        return ""

    fieldnames = list(records[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for r in records:
        writer.writerow({
            k: (json.dumps(v) if isinstance(v, (list, dict)) else v)
            for k, v in r.items()
        })

    return output.getvalue()


def export_markdown(records: List[Dict[str, Any]]) -> str:
    """
    Export a simple Markdown report.

    We intentionally omit daily_temps from the table to keep it readable.
    """
    if not records:
        return "# Weather Records\n\n_No records._\n"

    cols = [
        "id", "location_input", "resolved_name", "country", "state",
        "lat", "lon", "start_date", "end_date", "created_at", "updated_at"
    ]

    lines = [
        "# Weather Records",
        "",
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]

    for r in records:
        row = [str(r.get(c, "")) for c in cols]
        lines.append("| " + " | ".join(row) + " |")

    lines += [
        "",
        "## Notes",
        "- `daily_temps` is available via the record detail endpoint/page.",
        "",
    ]

    return "\n".join(lines)
