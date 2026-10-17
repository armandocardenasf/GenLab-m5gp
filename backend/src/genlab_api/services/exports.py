from __future__ import annotations

import io
import json
import math
import re
import zipfile
from datetime import date, datetime
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from ..lab_models import ExperimentGroup
from ..models import Dataset
from .lab import aggregate_metrics, group_runs, resolved_group_status, run_result_row

_INVALID_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_INVALID_SHEET = re.compile(r"[\\/*?:\[\]]+")


def safe_filename(value: str, fallback: str = "genlab_results") -> str:
    text = _INVALID_FILENAME.sub("_", value.strip()).strip("._")
    return (text or fallback)[:120]


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return str(value)


def experiment_export_payload(
    db: Session,
    group: ExperimentGroup,
    dataset_id: str | None = None,
) -> dict:
    aggregate = aggregate_metrics(db, group)
    if dataset_id is not None:
        datasets = [
            item for item in aggregate["by_dataset"]
            if item["dataset_id"] == dataset_id
        ]
        if not datasets:
            raise ValueError("El dataset no pertenece al experimento")
        benchmark = [
            item for item in aggregate.get("benchmark", [])
            if item["dataset_id"] == dataset_id
        ]
        aggregate = {
            **aggregate,
            "by_dataset": datasets,
            "benchmark": benchmark,
        }

    all_rows = group_runs(db, group.id)
    run_rows: list[dict] = []
    for link, run in all_rows:
        if dataset_id is not None and run.dataset_id != dataset_id:
            continue
        dataset = db.get(Dataset, run.dataset_id)
        run_rows.append(
            run_result_row(
                run,
                link,
                dataset.name if dataset is not None else run.dataset_id,
            )
        )

    payload = {
        "experiment": {
            "id": group.id,
            "name": group.name,
            "task_type": group.task_type,
            "preset_name": group.preset_name,
            "runs_per_dataset": group.runs_per_dataset,
            "validation": group.validation or {},
            "parameters": group.parameters or {},
            "created_at": group.created_at,
            "status": resolved_group_status(group, all_rows),
        },
        "scope": "dataset" if dataset_id else "experiment",
        "dataset_id": dataset_id,
        "aggregate": aggregate,
        "runs": run_rows,
    }
    return _json_value(payload)


def export_json_bytes(payload: dict) -> bytes:
    return json.dumps(
        _json_value(payload),
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_name(value: str, used: set[str]) -> str:
    base = _INVALID_SHEET.sub("_", value).strip() or "Sheet"
    base = base[:31]
    candidate = base
    suffix = 1
    while candidate.lower() in used:
        suffix += 1
        tail = f"_{suffix}"
        candidate = f"{base[:31-len(tail)]}{tail}"
    used.add(candidate.lower())
    return candidate


def _cell_xml(ref: str, value, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    if value is None:
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style_attr}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if math.isfinite(number):
            text = str(value)
            return f'<c r="{ref}" t="n"{style_attr}><v>{escape(text)}</v></c>'
    if isinstance(value, (datetime, date)):
        value = value.isoformat()
    text = escape(str(value))
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t{preserve}>{text}</t></is></c>'


def _worksheet_xml(rows: list[list]) -> str:
    body: list[str] = []
    for row_index, row in enumerate(rows, 1):
        cells: list[str] = []
        for column_index, value in enumerate(row):
            ref = f"{_column_name(column_index)}{row_index}"
            cells.append(_cell_xml(ref, value, style=1 if row_index == 1 else 0))
        body.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData>{"".join(body)}</sheetData>'
        '</worksheet>'
    )


def _metadata_rows(payload: dict) -> list[list]:
    experiment = payload["experiment"]
    return [
        ["Campo", "Valor"],
        ["experiment_id", experiment.get("id")],
        ["name", experiment.get("name")],
        ["task_type", experiment.get("task_type")],
        ["preset_name", experiment.get("preset_name")],
        ["runs_per_dataset", experiment.get("runs_per_dataset")],
        ["scope", payload.get("scope")],
        ["dataset_id", payload.get("dataset_id")],
        ["created_at", experiment.get("created_at")],
        ["validation", json.dumps(experiment.get("validation") or {}, ensure_ascii=False)],
        ["parameters", json.dumps(experiment.get("parameters") or {}, ensure_ascii=False)],
    ]


def _aggregate_rows(payload: dict) -> list[list]:
    headers = [
        "scope",
        "dataset_id",
        "dataset_name",
        "section",
        "metric",
        "mean",
        "std",
        "min",
        "max",
        "n",
    ]
    rows: list[list] = [headers]
    aggregate = payload["aggregate"]

    def add(scope: str, dataset_id: str | None, dataset_name: str, sections: dict):
        for section, metrics in (sections or {}).items():
            if not isinstance(metrics, dict):
                continue
            for metric, summary in metrics.items():
                if not isinstance(summary, dict):
                    continue
                rows.append([
                    scope,
                    dataset_id,
                    dataset_name,
                    section,
                    metric,
                    summary.get("mean"),
                    summary.get("std"),
                    summary.get("min"),
                    summary.get("max"),
                    summary.get("n"),
                ])

    if payload.get("dataset_id") is None:
        add("overall", None, "Todos los datasets", aggregate.get("overall") or {})
    for dataset in aggregate.get("by_dataset", []):
        add(
            "dataset",
            dataset.get("dataset_id"),
            dataset.get("dataset_name", ""),
            dataset.get("metrics") or {},
        )
    return rows


def _run_rows(payload: dict) -> list[list]:
    headers = [
        "dataset",
        "run_id",
        "run_name",
        "repeat",
        "fold",
        "seed",
        "status",
        "progress_percent",
        "generation",
        "total_generations",
        "r2_train",
        "r2_test",
        "rmse_train",
        "rmse_test",
        "mae_train",
        "mae_test",
        "accuracy_train",
        "accuracy_test",
        "f1_macro_train",
        "f1_macro_test",
        "model_size",
        "training_time_s",
        "process_time_s",
        "started_at",
        "finished_at",
    ]
    rows: list[list] = [headers]
    for item in payload.get("runs", []):
        repeat = item.get("repeat_index")
        fold = item.get("fold_index")
        rows.append([
            item.get("dataset_name"),
            item.get("run_id"),
            item.get("run_name"),
            repeat + 1 if isinstance(repeat, int) else None,
            fold + 1 if isinstance(fold, int) else None,
            item.get("seed"),
            item.get("status"),
            item.get("progress_percent"),
            item.get("generation"),
            item.get("total_generations"),
            item.get("r2_train"),
            item.get("r2_test"),
            item.get("rmse_train"),
            item.get("rmse_test"),
            item.get("mae_train"),
            item.get("mae_test"),
            item.get("accuracy_train"),
            item.get("accuracy_test"),
            item.get("f1_macro_train"),
            item.get("f1_macro_test"),
            item.get("model_size"),
            item.get("training_time"),
            item.get("process_time"),
            item.get("started_at"),
            item.get("finished_at"),
        ])
    return rows


def export_xlsx_bytes(payload: dict) -> bytes:
    """Create a compact XLSX workbook using only the Python standard library."""
    sheets = [
        ("Experimento", _metadata_rows(payload)),
        ("Resultados agregados", _aggregate_rows(payload)),
        ("Corridas", _run_rows(payload)),
    ]
    used: set[str] = set()
    normalized = [(_sheet_name(name, used), rows) for name, rows in sheets]

    workbook_sheets = []
    workbook_rels = []
    content_types = []
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                + "".join(
                    f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for index in range(1, len(normalized) + 1)
                )
                + '</Types>',
            )
            archive.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>',
            )
            for index, (name, rows) in enumerate(normalized, 1):
                workbook_sheets.append(
                    f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
                )
                workbook_rels.append(
                    f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
                )
                archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(rows))
            style_rel_id = len(normalized) + 1
            workbook_rels.append(
                f'<Relationship Id="rId{style_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            )
            archive.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets>{"".join(workbook_sheets)}</sheets>'
                '</workbook>',
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'{"".join(workbook_rels)}'
                '</Relationships>',
            )
            archive.writestr(
                "xl/styles.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
                '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
                '<borders count="1"><border/></borders>'
                '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
                '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
                '</styleSheet>',
            )
        return buffer.getvalue()


def export_table_workbook_bytes(sheets: list[tuple[str, list[list]]]) -> bytes:
    """Create an XLSX workbook from arbitrary table sheets without extra dependencies."""
    used: set[str] = set()
    normalized = [(_sheet_name(name, used), rows) for name, rows in sheets]
    workbook_sheets: list[str] = []
    workbook_rels: list[str] = []
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                + "".join(
                    f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for index in range(1, len(normalized) + 1)
                )
                + '</Types>',
            )
            archive.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>',
            )
            for index, (name, rows) in enumerate(normalized, 1):
                workbook_sheets.append(
                    f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
                )
                workbook_rels.append(
                    f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
                )
                archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(rows))
            style_rel_id = len(normalized) + 1
            workbook_rels.append(
                f'<Relationship Id="rId{style_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            )
            archive.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets>{"".join(workbook_sheets)}</sheets>'
                '</workbook>',
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'{"".join(workbook_rels)}'
                '</Relationships>',
            )
            archive.writestr(
                "xl/styles.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
                '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
                '<borders count="1"><border/></borders>'
                '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
                '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
                '</styleSheet>',
            )
        return buffer.getvalue()
