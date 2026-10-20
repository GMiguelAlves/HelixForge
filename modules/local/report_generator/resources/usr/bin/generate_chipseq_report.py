#!/usr/bin/env python3
import argparse
import base64
import hashlib
import html
import json
import shutil
import sys
import time
from pathlib import Path


SECTION_ORDER = (
    ("project", "Project and metadata"),
    ("reference", "Reference"),
    ("sequencing_qc", "Sequencing / QC"),
    ("alignment", "Alignment"),
    ("bam_processing", "BAM processing"),
    ("peak_calling", "Peak calling"),
    ("peak_qc", "Peak QC / FRiP"),
    ("consensus_idr", "Consensus / IDR"),
    ("differential_binding", "Differential binding"),
    ("annotation", "Annotation"),
    ("tracks", "Tracks"),
    ("provenance", "Provenance"),
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scalar(value):
    if value is None:
        return '<span class="missing">Not available</span>'
    if isinstance(value, bool):
        return "true" if value else "false"
    return html.escape(str(value))


def render_table(rows):
    if not rows:
        return '<p class="missing">No declared values</p>'
    fields = []
    for row in rows:
        if isinstance(row, dict):
            for key in row:
                if key not in fields and not isinstance(row[key], (dict, list)):
                    fields.append(key)
    if not fields:
        return render_value(rows)
    head = "".join(f"<th>{html.escape(str(field))}</th>" for field in fields)
    body = []
    for row in rows[:200]:
        body.append("<tr>" + "".join(f"<td>{scalar(row.get(field))}</td>" for field in fields) + "</tr>")
    suffix = f'<p class="muted">Showing 200 of {len(rows)} rows.</p>' if len(rows) > 200 else ""
    return f"<div class=table-wrap><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>{suffix}"


def render_value(value):
    if value is None:
        return '<p class="missing">Not available</p>'
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return render_table(value)
        return "<ul>" + "".join(f"<li>{render_value(item)}</li>" for item in value) + "</ul>"
    if isinstance(value, dict):
        if not value:
            return '<p class="missing">No declared values</p>'
        rows = []
        complex_blocks = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                complex_blocks.append(f"<details><summary>{html.escape(str(key))}</summary>{render_value(item)}</details>")
            else:
                rows.append(f"<tr><th>{html.escape(str(key))}</th><td>{scalar(item)}</td></tr>")
        table = f"<table class=key-value>{''.join(rows)}</table>" if rows else ""
        return table + "".join(complex_blocks)
    return scalar(value)


def generate_html(data, presentation):
    title = presentation.get("title") or "ChIP-seq final report"
    language = presentation.get("language") or "en"
    project = data.get("project", {})
    cards = "".join(
        f'<div class=metric><span>{html.escape(label)}</span><strong>{scalar(project.get(field))}</strong></div>'
        for field, label in (("project_id", "Project"), ("dataset", "Dataset"), ("genome_id", "Genome"), ("build", "Build"))
    )
    sections = []
    for key, label in SECTION_ORDER:
        section = data.get("sections", {}).get(key, {"status": "not_requested", "data": None})
        status = section.get("status", "incomplete")
        content = '<p class="not-executed">Not executed</p>' if status == "not_requested" else render_value(section.get("data"))
        sections.append(
            f'<section id="{html.escape(key)}"><div class=section-title><h2>{html.escape(label)}</h2>'
            f'<span class="status status-{html.escape(status)}">{html.escape(status)}</span></div>{content}</section>'
        )
    css = """
    :root{--ink:#172126;--muted:#637078;--line:#dbe1e4;--panel:#fff;--accent:#216e78;--bg:#f4f7f7}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
    header{background:#15343a;color:#fff;padding:32px max(24px,calc((100% - 1280px)/2))}header h1{margin:0 0 8px;font-size:30px}
    main{max-width:1280px;margin:auto;padding:24px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:22px}
    .metric,section{background:var(--panel);border:1px solid var(--line);border-radius:8px}.metric{padding:14px}.metric span{display:block;color:var(--muted);font-size:12px;text-transform:uppercase}.metric strong{font-size:18px}
    section{padding:20px;margin:14px 0}.section-title{display:flex;justify-content:space-between;gap:16px;align-items:center}.section-title h2{margin:0 0 14px}
    .status{border-radius:99px;padding:3px 10px;font-size:12px;font-weight:700}.status-available{background:#dff3e6;color:#176136}.status-not_requested{background:#edf0f2;color:#59646a}.status-not_implemented{background:#fff0c7;color:#775800}.status-failed{background:#ffe0e0;color:#8b2020}.status-incomplete{background:#ffe9d6;color:#834c13}
    table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}th{background:#eef3f4}.table-wrap{overflow:auto}.key-value{width:auto;min-width:420px}
    details{margin:9px 0;border-left:3px solid var(--line);padding-left:12px}summary{cursor:pointer;font-weight:650}.missing,.muted,.not-executed{color:var(--muted)}
    footer{max-width:1280px;margin:auto;padding:0 24px 28px;color:var(--muted);font-size:12px}
    """
    return "\n".join([
        "<!doctype html>", f'<html lang="{html.escape(language)}"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">', f"<title>{html.escape(title)}</title><style>{css}</style></head><body>",
        f"<header><h1>{html.escape(title)}</h1><p>Manifest-driven HelixForge Report API v1</p></header>",
        f"<main><div class=metrics>{cards}</div>{''.join(sections)}</main>",
        "<footer>Missing values are not interpreted as zero. Status is preserved from upstream manifests.</footer></body></html>",
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate-dir", required=True)
    parser.add_argument("--presentation-base64", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    args = parser.parse_args()
    started = int(time.time())
    presentation = json.loads(base64.b64decode(args.presentation_base64).decode("utf-8"))
    if presentation.get("provider") != "html_v1":
        raise ValueError("Report API v1 supports only provider=html_v1")
    if presentation.get("language", "en") not in {"en", "pt-BR"}:
        raise ValueError("report language must be en or pt-BR")
    aggregate = Path(args.aggregate_dir)
    data = load_json(aggregate / "report_data.json")
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    (output / "chipseq_report.html").write_text(generate_html(data, presentation), encoding="utf-8")
    shutil.copy2(aggregate / "report_data.json", output / "report.json")
    shutil.copy2(aggregate / "provenance.json", output / "provenance.json")
    shutil.copy2(aggregate / "versions.yml", output / "versions.yml")
    ended = int(time.time())
    execution = {"schema_version": "1.0", "id": data["id"], "process": "REPORT_GENERATOR", "provider": "html_v1", "presentation": presentation, "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time, "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started}
    write_json(output / "execution.json", execution)
    manifest = {
        "schema_version": "1.0", "type": "chipseq_report", "id": data["id"], "provider": "html_v1",
        "project": data["project"], "component_status": {key: value["status"] for key, value in data["sections"].items()},
        "artifacts": {
            "report": {"path": "chipseq_report.html", "sha256": sha256(output / "chipseq_report.html")},
            "structured_json": {"path": "report.json", "sha256": sha256(output / "report.json")},
            "provenance": {"path": "provenance.json", "sha256": sha256(output / "provenance.json")},
            "versions": {"path": "versions.yml", "sha256": sha256(output / "versions.yml")},
            "execution": {"path": "execution.json", "sha256": sha256(output / "execution.json")},
        }, "status": data["status"],
    }
    write_json(output / "manifest.json", manifest)
    write_json(args.execution, execution)
    Path(args.versions).write_text(f'"REPORT_GENERATOR":\n    python: "{sys.version.split()[0]}"\n    provider: "html_v1"\n', encoding="utf-8")
    print(f"Generated self-contained HTML for {data['id']}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
