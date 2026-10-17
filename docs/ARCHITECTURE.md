# Arquitectura GenLab M5GP

```text
Frontend React
    │ REST/JWT
    ▼
FastAPI
    ├── Datasets
    ├── ExperimentGroup ──┬── Dataset A ── Run 1, Run 2, ...
    │                     └── Dataset B ── Run 1, Run 2, ...
    ├── ParameterPreset
    ├── Batch ── ExperimentGroup[]
    └── GPU scheduler / leases
                    │
                    ▼
             legacy experiments table
             (una fila = una corrida)
                    │
                    ▼
              worker por GPU
                    │
                    ▼
             core/src/m5gp
```

## Compatibilidad incremental

La tabla `experiments` no se renombra. Esta decisión permite conservar datos y endpoints históricos. Las tablas `experiment_groups`, `experiment_group_datasets`, `experiment_group_runs`, `parameter_presets`, `batches` y `batch_experiments` se agregan sobre el esquema existente.

## Validación externa

El worker construye Train/Test antes de llamar `fit()`. Holdout usa `train_test_split`; K-fold usa `KFold` y clasificación usa `StratifiedKFold`.

Los parámetros de partición se almacenan también como argumentos candidatos del constructor. `_constructor_parameters()` los reenvía sólo cuando el constructor real de M5GP los declare.

## Planificación GPU

Las corridas agrupadas se crean como `queued`. `dispatch_queued()` usa el servicio de leases existente. Al finalizar una corrida, el worker libera la GPU y solicita el despacho de la siguiente.

## Agregación

El servicio `services/lab.py` calcula métricas globales y por dataset. Los artefactos individuales permanecen en los directorios históricos de cada corrida.

## Fuente M5GP

`core/src/m5gp` continúa siendo la única fuente del motor utilizada por GenLab. El ciclo evolutivo no se modifica desde el backend.

