from __future__ import annotations

import json
from typing import Any

from .exports import export_json_bytes, export_table_workbook_bytes


def comparison_export_payload(report: dict[str, Any]) -> dict[str, Any]:
    return report


def comparison_json_bytes(report: dict[str, Any]) -> bytes:
    return export_json_bytes(report)


def _metadata_rows(report: dict[str, Any]) -> list[list]:
    analysis = report.get("analysis") or report.get("snapshot") or {}
    return [
        ["Campo", "Valor"],
        ["report_id", report.get("id")],
        ["name", report.get("name")],
        ["description", report.get("description")],
        ["task_type", report.get("task_type") or analysis.get("task_type")],
        ["primary_metric", analysis.get("primary_metric")],
        ["alpha", analysis.get("alpha")],
        ["generated_at", analysis.get("generated_at")],
        ["created_at", report.get("created_at")],
        ["updated_at", report.get("updated_at")],
        ["notes", " | ".join(analysis.get("notes") or [])],
    ]


def _experiment_rows(analysis: dict[str, Any]) -> list[list]:
    headers = [
        "experiment_id",
        "name",
        "preset",
        "status",
        "completed_runs",
        "total_runs",
        "runs_per_dataset",
        "validation",
        "parameters",
    ]
    rows = [headers]
    for item in analysis.get("experiments", []):
        rows.append([
            item.get("id"),
            item.get("name"),
            item.get("preset_name"),
            item.get("status"),
            item.get("completed_runs"),
            item.get("total_runs"),
            item.get("runs_per_dataset"),
            json.dumps(item.get("validation") or {}, ensure_ascii=False),
            json.dumps(item.get("parameters") or {}, ensure_ascii=False),
        ])
    return rows


def _ranking_rows(analysis: dict[str, Any]) -> list[list]:
    rows = [["metric", "rank", "experiment_id", "experiment", "mean", "std", "min", "max", "n"]]
    for metric, ranking in (analysis.get("rankings") or {}).items():
        for item in ranking:
            rows.append([
                metric,
                item.get("rank"),
                item.get("experiment_id"),
                item.get("label"),
                item.get("mean"),
                item.get("std"),
                item.get("min"),
                item.get("max"),
                item.get("n"),
            ])
    return rows


def _dataset_rows(analysis: dict[str, Any]) -> list[list]:
    metrics = list((analysis.get("metric_specs") or {}).keys())
    experiment_names = {
        item.get("id"): item.get("name") for item in analysis.get("experiments", [])
    }
    rows = [[
        "dataset_id", "dataset", "rows", "features", "points",
        "experiment_id", "experiment", "completed_runs", *metrics,
    ]]
    for dataset in analysis.get("datasets", []):
        for experiment_id, payload in (dataset.get("experiments") or {}).items():
            metric_values = []
            summaries = payload.get("metrics") or {}
            for metric in metrics:
                summary = summaries.get(metric) or {}
                metric_values.append(summary.get("mean"))
            rows.append([
                dataset.get("dataset_id"),
                dataset.get("dataset_name"),
                dataset.get("rows"),
                dataset.get("features"),
                dataset.get("points"),
                experiment_id,
                experiment_names.get(experiment_id, experiment_id),
                payload.get("completed_runs"),
                *metric_values,
            ])
    return rows


def _wilcoxon_rows(analysis: dict[str, Any]) -> list[list]:
    wilcoxon = analysis.get("wilcoxon") or {}
    names = {item.get("id"): item.get("name") for item in wilcoxon.get("experiments", [])}
    rows = [[
        "row_experiment", "column_experiment", "n_pairs", "statistic",
        "p_value", "p_adjusted_holm", "category", "significant",
        "exploratory", "winner", "rank_biserial", "median_oriented_difference", "datasets",
    ]]
    for item in wilcoxon.get("cells", []):
        winner_id = item.get("winner_experiment_id")
        rows.append([
            names.get(item.get("row_experiment_id"), item.get("row_experiment_id")),
            names.get(item.get("column_experiment_id"), item.get("column_experiment_id")),
            item.get("n_pairs"),
            item.get("statistic"),
            item.get("p_value"),
            item.get("p_adjusted"),
            item.get("category"),
            item.get("significant"),
            item.get("exploratory"),
            names.get(winner_id, winner_id),
            item.get("rank_biserial"),
            item.get("median_oriented_difference"),
            ", ".join(item.get("dataset_ids") or []),
        ])
    return rows


def _parameter_rows(analysis: dict[str, Any]) -> list[list]:
    rows = [["parameter", "experiment_id", "experiment", "value", "numeric", "correlations"]]
    for parameter in analysis.get("varying_parameters", []):
        correlations = json.dumps(parameter.get("correlations") or {}, ensure_ascii=False)
        for item in parameter.get("values", []):
            rows.append([
                parameter.get("parameter"),
                item.get("experiment_id"),
                item.get("experiment_name"),
                item.get("value"),
                parameter.get("numeric"),
                correlations,
            ])
    return rows


def _computational_rows(analysis: dict[str, Any]) -> list[list]:
    rows = [[
        "axis", "experiment_id", "experiment", "dataset_id", "dataset",
        "x", "training_time_mean", "training_time_std", "training_time_min",
        "training_time_max", "n",
    ]]
    for axis, items in (analysis.get("computational") or {}).items():
        for item in items:
            rows.append([
                axis,
                item.get("experiment_id"),
                item.get("experiment_name"),
                item.get("dataset_id"),
                item.get("dataset_name"),
                item.get("x"),
                item.get("training_time_mean"),
                item.get("training_time_std"),
                item.get("training_time_min"),
                item.get("training_time_max"),
                item.get("n"),
            ])
    return rows


def comparison_xlsx_bytes(report: dict[str, Any]) -> bytes:
    analysis = report.get("analysis") or report.get("snapshot") or {}
    sheets = [
        ("Reporte", _metadata_rows(report)),
        ("Experimentos", _experiment_rows(analysis)),
        ("Rankings", _ranking_rows(analysis)),
        ("Datasets", _dataset_rows(analysis)),
        ("Wilcoxon", _wilcoxon_rows(analysis)),
        ("Parametros", _parameter_rows(analysis)),
        ("Computacional", _computational_rows(analysis)),
    ]
    return export_table_workbook_bytes(sheets)
