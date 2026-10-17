from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import mean, median, pstdev
from typing import Any

from scipy.stats import rankdata, spearmanr, wilcoxon
from sqlalchemy.orm import Session

from ..lab_models import ExperimentGroup
from ..models import Dataset, Experiment, ExperimentStatus
from .lab import group_dataset_links, group_runs, resolved_group_status


METRIC_SPECS: dict[str, dict[str, Any]] = {
    "r2_test": {"label": "R² Test", "section": "test", "key": "r2", "higher_better": True, "log": False},
    "rmse_test": {"label": "RMSE Test", "section": "test", "key": "rmse", "higher_better": False, "log": False},
    "mae_test": {"label": "MAE Test", "section": "test", "key": "mae", "higher_better": False, "log": False},
    "accuracy_test": {"label": "Accuracy Test", "section": "test", "key": "accuracy", "higher_better": True, "log": False},
    "f1_macro_test": {"label": "F1 macro Test", "section": "test", "key": "f1_macro", "higher_better": True, "log": False},
    "precision_macro_test": {"label": "Precision macro Test", "section": "test", "key": "precision_macro", "higher_better": True, "log": False},
    "recall_macro_test": {"label": "Recall macro Test", "section": "test", "key": "recall_macro", "higher_better": True, "log": False},
    "model_size": {"label": "Model Size", "section": None, "key": "model_size", "higher_better": False, "log": True},
    "training_time": {"label": "Training Time (s)", "section": None, "key": "training_time", "higher_better": False, "log": True},
}

TASK_METRICS = {
    "regression": ["r2_test", "rmse_test", "mae_test", "model_size", "training_time"],
    "classification": [
        "accuracy_test",
        "f1_macro_test",
        "precision_macro_test",
        "recall_macro_test",
        "model_size",
        "training_time",
    ],
}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return None


def _run_metric(run: Experiment, metric: str) -> float | None:
    if not isinstance(run.metrics, dict):
        return None
    spec = METRIC_SPECS[metric]
    section = spec["section"]
    if section is None:
        return _finite(run.metrics.get(spec["key"]))
    values = run.metrics.get(section)
    if not isinstance(values, dict):
        return None
    return _finite(values.get(spec["key"]))


def _summary(values: list[float]) -> dict[str, Any] | None:
    if not values:
        return None
    return {
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "n": len(values),
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _scalar_parameters(group: ExperimentGroup) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in (group.parameters or {}).items():
        if isinstance(value, (str, bool, int, float)) and not isinstance(value, (dict, list)):
            if isinstance(value, float) and not math.isfinite(value):
                continue
            result[key] = value
    for key, value in (group.validation or {}).items():
        if isinstance(value, (str, bool, int, float)):
            result[f"validation.{key}"] = value
    result["runs_per_dataset"] = group.runs_per_dataset
    return result


def _holm_adjust(items: list[tuple[int, float]]) -> dict[int, float]:
    """Return Holm-Bonferroni adjusted p-values indexed by comparison position."""
    if not items:
        return {}
    ordered = sorted(items, key=lambda item: item[1])
    m = len(ordered)
    adjusted: dict[int, float] = {}
    running = 0.0
    for rank, (index, p_value) in enumerate(ordered):
        candidate = min(1.0, (m - rank) * p_value)
        running = max(running, candidate)
        adjusted[index] = min(1.0, running)
    return adjusted


def _significance_category(p_adjusted: float | None, alpha: float) -> str:
    if p_adjusted is None:
        return "unavailable"
    if p_adjusted < alpha * 1e-3:
        return "sig_1e3"
    if p_adjusted < alpha * 1e-2:
        return "sig_1e2"
    if p_adjusted < alpha * 1e-1:
        return "sig_1e1"
    if p_adjusted < alpha:
        return "sig_alpha"
    return "ns"


def _wilcoxon_matrix(
    experiments: list[dict[str, Any]],
    dataset_metric_values: dict[str, dict[str, dict[str, float]]],
    metric: str,
    alpha: float,
) -> dict[str, Any]:
    raw_cells: list[dict[str, Any]] = []
    p_values: list[tuple[int, float]] = []
    higher_better = bool(METRIC_SPECS[metric]["higher_better"])

    for left_index in range(len(experiments)):
        for right_index in range(left_index):
            left = experiments[left_index]
            right = experiments[right_index]
            left_values = dataset_metric_values.get(left["id"], {})
            right_values = dataset_metric_values.get(right["id"], {})
            common = sorted(set(left_values) & set(right_values))
            pairs: list[tuple[str, float, float]] = []
            for dataset_id in common:
                a = _finite(left_values[dataset_id].get(metric))
                b = _finite(right_values[dataset_id].get(metric))
                if a is not None and b is not None:
                    pairs.append((dataset_id, a, b))

            p_value: float | None = None
            statistic: float | None = None
            if len(pairs) >= 2:
                a_values = [item[1] for item in pairs]
                b_values = [item[2] for item in pairs]
                differences = [a - b for a, b in zip(a_values, b_values)]
                if all(abs(value) <= 1e-15 for value in differences):
                    statistic, p_value = 0.0, 1.0
                else:
                    try:
                        result = wilcoxon(
                            a_values,
                            b_values,
                            zero_method="wilcox",
                            alternative="two-sided",
                            method="auto",
                        )
                        statistic = float(result.statistic)
                        p_value = float(result.pvalue)
                    except ValueError:
                        p_value = None
            left_mean = mean(item[1] for item in pairs) if pairs else None
            right_mean = mean(item[2] for item in pairs) if pairs else None
            winner: str | None = None
            if left_mean is not None and right_mean is not None and left_mean != right_mean:
                left_better = left_mean > right_mean if higher_better else left_mean < right_mean
                winner = left["id"] if left_better else right["id"]

            oriented_differences = [
                (a - b) if higher_better else (b - a)
                for _, a, b in pairs
                if abs(a - b) > 1e-15
            ]
            rank_biserial: float | None = None
            median_difference: float | None = None
            if oriented_differences:
                ranks = rankdata([abs(value) for value in oriented_differences], method="average")
                positive = sum(float(rank) for rank, value in zip(ranks, oriented_differences) if value > 0)
                negative = sum(float(rank) for rank, value in zip(ranks, oriented_differences) if value < 0)
                denominator = positive + negative
                rank_biserial = (positive - negative) / denominator if denominator else 0.0
                median_difference = median(oriented_differences)

            cell = {
                "row_experiment_id": left["id"],
                "column_experiment_id": right["id"],
                "n_pairs": len(pairs),
                "dataset_ids": [item[0] for item in pairs],
                "statistic": statistic,
                "p_value": p_value,
                "p_adjusted": None,
                "category": "unavailable",
                "significant": False,
                "exploratory": len(pairs) < 5,
                "winner_experiment_id": winner,
                "left_mean": left_mean,
                "right_mean": right_mean,
                "rank_biserial": rank_biserial,
                "median_oriented_difference": median_difference,
            }
            raw_cells.append(cell)
            if p_value is not None and math.isfinite(p_value):
                p_values.append((len(raw_cells) - 1, p_value))

    adjusted = _holm_adjust(p_values)
    for index, cell in enumerate(raw_cells):
        p_adjusted = adjusted.get(index)
        cell["p_adjusted"] = p_adjusted
        cell["category"] = _significance_category(p_adjusted, alpha)
        cell["significant"] = bool(p_adjusted is not None and p_adjusted < alpha)

    return {
        "metric": metric,
        "metric_label": METRIC_SPECS[metric]["label"],
        "alpha": alpha,
        "correction": "Holm-Bonferroni",
        "pairing": "dataset-level means over common datasets",
        "minimum_pairs_for_inference": 5,
        "experiments": [{"id": item["id"], "name": item["name"]} for item in experiments],
        "cells": raw_cells,
    }


def build_comparison_snapshot(
    db: Session,
    groups: list[ExperimentGroup],
    task_type: str,
    primary_metric: str,
    alpha: float,
) -> dict[str, Any]:
    if len(groups) < 2:
        raise ValueError("Se requieren al menos dos experimentos")
    if any(group.task_type != task_type for group in groups):
        raise ValueError("Todos los experimentos deben ser del mismo tipo")
    if primary_metric not in TASK_METRICS[task_type]:
        raise ValueError("Métrica principal no válida")

    metrics = TASK_METRICS[task_type]
    experiments: list[dict[str, Any]] = []
    dataset_catalog: dict[str, dict[str, Any]] = {}
    dataset_metric_values: dict[str, dict[str, dict[str, float]]] = {}
    benchmark_values: dict[str, dict[str, list[float]]] = {
        metric: {} for metric in metrics
    }
    dataset_run_values: dict[str, dict[str, dict[str, list[float]]]] = {}
    computational: dict[str, list[dict[str, Any]]] = {
        "samples": [],
        "features": [],
        "points": [],
    }

    for group in groups:
        all_rows = group_runs(db, group.id)
        completed_pairs = [
            (link, run)
            for link, run in all_rows
            if run.status == ExperimentStatus.completed.value and isinstance(run.metrics, dict)
        ]
        experiment_entry = {
            "id": group.id,
            "name": group.name,
            "task_type": group.task_type,
            "preset_name": group.preset_name,
            "parameters": group.parameters or {},
            "validation": group.validation or {},
            "scalar_parameters": _scalar_parameters(group),
            "runs_per_dataset": group.runs_per_dataset,
            "total_runs": len(all_rows),
            "completed_runs": len(completed_pairs),
            "status": resolved_group_status(group, all_rows),
            "created_at": group.created_at,
        }
        experiments.append(experiment_entry)
        dataset_metric_values[group.id] = {}
        dataset_run_values[group.id] = {}

        for metric in metrics:
            benchmark_values[metric][group.id] = []
            for _, run in completed_pairs:
                value = _run_metric(run, metric)
                if value is not None:
                    benchmark_values[metric][group.id].append(value)

        for dataset_link in group_dataset_links(db, group.id):
            dataset = db.get(Dataset, dataset_link.dataset_id)
            if dataset is None:
                continue
            features = max(int(dataset.columns) - 1, 1)
            dataset_catalog.setdefault(
                dataset.id,
                {
                    "dataset_id": dataset.id,
                    "dataset_name": dataset.name,
                    "rows": int(dataset.rows),
                    "features": features,
                    "points": int(dataset.rows) * features,
                    "experiments": {},
                },
            )
            dataset_runs = [
                run for _, run in completed_pairs if run.dataset_id == dataset.id
            ]
            dataset_run_values[group.id][dataset.id] = {}
            metric_summaries: dict[str, Any] = {}
            metric_means: dict[str, float] = {}
            for metric in metrics:
                values = [
                    value
                    for run in dataset_runs
                    if (value := _run_metric(run, metric)) is not None
                ]
                dataset_run_values[group.id][dataset.id][metric] = values
                summary = _summary(values)
                if summary is not None:
                    metric_summaries[metric] = summary
                    metric_means[metric] = float(summary["mean"])
            dataset_metric_values[group.id][dataset.id] = metric_means
            dataset_catalog[dataset.id]["experiments"][group.id] = {
                "target_column": dataset_link.target_column,
                "completed_runs": len(dataset_runs),
                "metrics": metric_summaries,
            }

            times = [
                value
                for run in dataset_runs
                if (value := _run_metric(run, "training_time")) is not None
            ]
            time_summary = _summary(times)
            if time_summary is not None:
                base = {
                    "experiment_id": group.id,
                    "experiment_name": group.name,
                    "dataset_id": dataset.id,
                    "dataset_name": dataset.name,
                    "training_time_mean": time_summary["mean"],
                    "training_time_std": time_summary["std"],
                    "training_time_min": time_summary["min"],
                    "training_time_max": time_summary["max"],
                    "n": time_summary["n"],
                }
                computational["samples"].append({**base, "x": int(dataset.rows)})
                computational["features"].append({**base, "x": features})
                computational["points"].append({**base, "x": int(dataset.rows) * features})

    dataset_sets = [set(dataset_run_values.get(item["id"], {})) for item in experiments]
    common_dataset_ids = sorted(set.intersection(*dataset_sets)) if dataset_sets else []
    all_dataset_ids = sorted(set.union(*dataset_sets)) if dataset_sets else []
    benchmark_scope = "common_datasets" if common_dataset_ids else "all_available_datasets"

    # Rebuild benchmark values so performance comparisons use only datasets
    # shared by every selected experiment whenever such a common set exists.
    for metric in metrics:
        for experiment in experiments:
            experiment_id = experiment["id"]
            selected_dataset_ids = common_dataset_ids or sorted(dataset_run_values.get(experiment_id, {}))
            benchmark_values[metric][experiment_id] = [
                value
                for dataset_id in selected_dataset_ids
                for value in dataset_run_values.get(experiment_id, {}).get(dataset_id, {}).get(metric, [])
            ]

    benchmarks: list[dict[str, Any]] = []
    rankings: dict[str, list[dict[str, Any]]] = {}
    for metric in metrics:
        rows = []
        for experiment in experiments:
            values = benchmark_values[metric].get(experiment["id"], [])
            summary = _summary(values)
            if summary is None:
                continue
            rows.append(
                {
                    "experiment_id": experiment["id"],
                    "label": experiment["name"],
                    "values": values,
                    **summary,
                }
            )
        spec = METRIC_SPECS[metric]
        ordered = sorted(
            rows,
            key=lambda item: item["mean"],
            reverse=bool(spec["higher_better"]),
        )
        rankings[metric] = [
            {**row, "rank": index + 1}
            for index, row in enumerate(ordered)
        ]
        benchmarks.append(
            {
                "metric": metric,
                "title": spec["label"],
                "higher_better": spec["higher_better"],
                "log_scale": spec["log"],
                "rows": rows,
            }
        )

    varying_parameters: list[dict[str, Any]] = []
    parameter_names = sorted(
        set().union(*(set(item["scalar_parameters"]) for item in experiments))
    )
    for parameter in parameter_names:
        values = [item["scalar_parameters"].get(parameter) for item in experiments]
        distinct = {str(value) for value in values if value is not None}
        if len(distinct) < 2:
            continue
        numeric_pairs = [
            (item["id"], _finite(item["scalar_parameters"].get(parameter)))
            for item in experiments
        ]
        numeric = all(value is not None for _, value in numeric_pairs)
        correlations: dict[str, Any] = {}
        if numeric:
            x = [float(value) for _, value in numeric_pairs if value is not None]
            for metric in metrics:
                y: list[float] = []
                x_match: list[float] = []
                ranking_by_id = {
                    item["experiment_id"]: item for item in rankings.get(metric, [])
                }
                for experiment_id, x_value in numeric_pairs:
                    row = ranking_by_id.get(experiment_id)
                    if x_value is not None and row is not None:
                        x_match.append(float(x_value))
                        y.append(float(row["mean"]))
                if len(x_match) >= 3 and len(set(x_match)) > 1 and len(set(y)) > 1:
                    result = spearmanr(x_match, y)
                    correlations[metric] = {
                        "rho": _finite(result.statistic),
                        "p_value": _finite(result.pvalue),
                        "n": len(x_match),
                    }
        varying_parameters.append(
            {
                "parameter": parameter,
                "numeric": numeric,
                "values": [
                    {
                        "experiment_id": item["id"],
                        "experiment_name": item["name"],
                        "value": item["scalar_parameters"].get(parameter),
                    }
                    for item in experiments
                ],
                "correlations": correlations,
            }
        )

    parameter_points: list[dict[str, Any]] = []
    for parameter in varying_parameters:
        if not parameter["numeric"]:
            continue
        for experiment in experiments:
            x_value = _finite(experiment["scalar_parameters"].get(parameter["parameter"]))
            if x_value is None:
                continue
            metrics_payload: dict[str, float] = {}
            for metric in metrics:
                row = next(
                    (
                        item
                        for item in rankings.get(metric, [])
                        if item["experiment_id"] == experiment["id"]
                    ),
                    None,
                )
                if row is not None:
                    metrics_payload[metric] = float(row["mean"])
            parameter_points.append(
                {
                    "parameter": parameter["parameter"],
                    "experiment_id": experiment["id"],
                    "experiment_name": experiment["name"],
                    "x": x_value,
                    "metrics": metrics_payload,
                }
            )

    wilcoxon_payload = _wilcoxon_matrix(
        experiments,
        dataset_metric_values,
        primary_metric,
        alpha,
    )

    tradeoff: list[dict[str, Any]] = []
    metric_rows = {item["experiment_id"]: item for item in rankings.get(primary_metric, [])}
    time_rows = {item["experiment_id"]: item for item in rankings.get("training_time", [])}
    size_rows = {item["experiment_id"]: item for item in rankings.get("model_size", [])}
    for experiment in experiments:
        metric_row = metric_rows.get(experiment["id"])
        time_row = time_rows.get(experiment["id"])
        if metric_row is None or time_row is None:
            continue
        tradeoff.append(
            {
                "experiment_id": experiment["id"],
                "experiment_name": experiment["name"],
                "metric": primary_metric,
                "score": metric_row["mean"],
                "training_time": time_row["mean"],
                "model_size": size_rows.get(experiment["id"], {}).get("mean"),
            }
        )

    return _json_safe(
        {
            "task_type": task_type,
            "generated_at": datetime.now(timezone.utc),
            "primary_metric": primary_metric,
            "alpha": alpha,
            "metric_specs": {metric: METRIC_SPECS[metric] for metric in metrics},
            "experiments": experiments,
            "datasets": list(dataset_catalog.values()),
            "benchmarks": benchmarks,
            "rankings": rankings,
            "wilcoxon": wilcoxon_payload,
            "computational": computational,
            "varying_parameters": varying_parameters,
            "parameter_points": parameter_points,
            "tradeoff": tradeoff,
            "coverage": {
                "common_dataset_ids": common_dataset_ids,
                "all_dataset_ids": all_dataset_ids,
                "benchmark_scope": benchmark_scope,
                "comparable_on_common_datasets": bool(common_dataset_ids),
            },
            "notes": [
                "Rankings y gráficas de desempeño usan únicamente datasets comunes a todos los experimentos cuando existe al menos uno.",
                "Wilcoxon usa medias por dataset y solo datasets comunes entre cada par de experimentos.",
                "Los p-valores se ajustan con Holm-Bonferroni para comparaciones múltiples.",
                "Contrastes con menos de cinco datasets comunes se marcan como exploratorios.",
                "RMSE/MAE entre datasets con escalas objetivo distintas deben interpretarse por dataset o normalizarse antes de comparar globalmente.",
                "Dataset points se define como filas × características predictoras.",
            ],
        }
    )
