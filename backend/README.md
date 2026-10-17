# Backend GenLab M5GP

API FastAPI con JWT, datasets, corridas, experimentos agrupados, predefinidos, lotes y control de una tarea por GPU.

## Terminología

- La entidad SQLAlchemy histórica `Experiment` y la tabla `experiments` se mantienen por compatibilidad. En la interfaz nueva representan una **corrida individual**.
- `ExperimentGroup` es el nuevo contenedor científico **Experimento**.
- `Batch` representa un **Lote** de experimentos.

No se renombra ni elimina la tabla existente.

## Ejecución M5GP

Cada corrida conserva el flujo original:

1. reserva de GPU;
2. `CUDA_VISIBLE_DEVICES`;
3. importación de M5GP dentro del worker;
4. construcción del estimador;
5. `fit()` y `predict()`;
6. métricas Train/Test y artefactos;
7. liberación de GPU.

Para corridas agrupadas, el worker libera la GPU y solicita el despacho de la siguiente corrida `queued`.

## Partición de datos

GenLab soporta:

- Holdout aleatorio con `train_size`, `test_size` y `random_state`;
- K-fold (`KFold` o `StratifiedKFold`) con una corrida por fold y repetición.

La configuración queda guardada en `_genlab_split`, `metrics.json` y `experiment.json`. Los valores públicos `train_size`, `test_size`, `random_state`, `validation_strategy` y `cv_folds` permanecen también en `parameters` y se enviarán automáticamente a M5GP cuando sus constructores los declaren.

## Endpoints añadidos

```text
/runs
/experiment-groups
/parameter-presets
/batches
```

La API histórica `/experiments` continúa operativa.

## Nuevos archivos

```text
lab_models.py
lab_schemas.py
services/lab.py
routers/runs.py
routers/experiment_groups.py
routers/presets.py
routers/batches.py
```

## Arranque

```bash
python -m pip install -e ../core
python -m pip install -e .
uvicorn genlab_api.main:app --app-dir src --workers 1
```

