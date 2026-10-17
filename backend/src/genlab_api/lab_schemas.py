from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ExperimentDatasetInput(BaseModel):
    dataset_id: str
    target_column: str


class ValidationConfig(BaseModel):
    strategy: Literal["holdout", "kfold"] = "holdout"
    train_size: float = Field(default=0.75, gt=0.0, lt=1.0)
    test_size: float = Field(default=0.25, gt=0.0, lt=1.0)
    random_state: int = 42
    folds: int = Field(default=5, ge=2, le=20)
    shuffle: bool = True

    @model_validator(mode="after")
    def validate_holdout_proportions(self):
        if self.strategy == "holdout":
            total = float(self.train_size) + float(self.test_size)
            if abs(total - 1.0) > 1e-6:
                raise ValueError("train_size + test_size debe ser igual a 1.0")
        return self


class ExperimentGroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    task_type: Literal["regression", "classification"]
    datasets: list[ExperimentDatasetInput] = Field(min_length=1)
    runs_per_dataset: int = Field(default=1, ge=1, le=100)
    preset_name: str | None = Field(default=None, max_length=120)
    parameters: dict[str, Any] = Field(default_factory=dict)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    @field_validator("parameters")
    @classmethod
    def protect_internal_parameters(cls, value: dict[str, Any]):
        forbidden = {
            "_progress_callback",
            "_cancel_callback",
            "owner_id",
            "artifact_dir",
            "_genlab_split",
        }
        if forbidden.intersection(value):
            raise ValueError("Parámetros internos no permitidos")
        for key in ("generations", "Individuals", "GenesIndividuals"):
            if key in value and int(value[key]) < 1:
                raise ValueError(f"{key} debe ser mayor que cero")
        if "maxRandomConstant" in value and float(value["maxRandomConstant"]) <= 0:
            raise ValueError("maxRandomConstant debe ser mayor que cero")
        if "functions_set" in value:
            functions = value["functions_set"]
            if not isinstance(functions, list) or not functions:
                raise ValueError("functions_set debe contener al menos una función")
            valid = {
                "+", "-", "*", "/", "sin", "cos", "exp", "log", "Abs",
                "Add", "Mul", "avg", "std", "tan", "tanh", "sqrt",
                "if==", "if>", "if<",
            }
            invalid = [str(item) for item in functions if str(item) not in valid]
            if invalid:
                raise ValueError(f"Funciones M5GP no reconocidas: {', '.join(invalid)}")
        return value

    @model_validator(mode="after")
    def validate_task_parameters(self):
        parameters = self.parameters or {}
        evaluation_method = int(parameters.get("evaluationMethod", 0 if self.task_type == "classification" else 4))
        scorer = int(parameters.get("scorer", 0))
        if self.task_type == "classification":
            if evaluation_method not in {0, 1, 2, 3}:
                raise ValueError("Para clasificación evaluationMethod debe ser 0, 1, 2 o 3")
            if scorer not in {0, 1, 2, 3}:
                raise ValueError("Para clasificación scorer debe ser 0, 1, 2 o 3")
            if "averageMode" in parameters and str(parameters["averageMode"]) not in {"micro", "macro", "weighted", "samples"}:
                raise ValueError("averageMode inválido para clasificación")
        else:
            if evaluation_method not in set(range(0, 11)):
                raise ValueError("Para regresión evaluationMethod debe estar entre 0 y 10")
            if scorer not in {0, 1, 2}:
                raise ValueError("Para regresión scorer debe ser 0, 1 o 2")
        return self


class ParameterPresetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=400)
    task_type: Literal["both", "regression", "classification"] = "both"
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ParameterPresetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    task_type: Literal["both", "regression", "classification"] | None = None
    parameters: dict[str, Any] | None = None
    is_default: bool | None = None


class BatchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    experiment_ids: list[str] = Field(min_length=1)

COMPARISON_METRICS = {
    "regression": {
        "r2_test",
        "rmse_test",
        "mae_test",
        "model_size",
        "training_time",
    },
    "classification": {
        "accuracy_test",
        "f1_macro_test",
        "precision_macro_test",
        "recall_macro_test",
        "model_size",
        "training_time",
    },
}


class ComparisonRequest(BaseModel):
    task_type: Literal["regression", "classification"]
    experiment_ids: list[str] = Field(min_length=2, max_length=30)
    primary_metric: str | None = None
    alpha: float = Field(default=0.05, gt=0.0, lt=0.5)

    @model_validator(mode="after")
    def validate_comparison(self):
        if len(set(self.experiment_ids)) != len(self.experiment_ids):
            raise ValueError("Un experimento no puede repetirse en el comparativo")
        default_metric = "r2_test" if self.task_type == "regression" else "f1_macro_test"
        self.primary_metric = self.primary_metric or default_metric
        if self.primary_metric not in COMPARISON_METRICS[self.task_type]:
            raise ValueError("Métrica principal no válida para el tipo de experimento")
        return self


class ComparisonReportCreate(ComparisonRequest):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=1000)
