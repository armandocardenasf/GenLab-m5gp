# Backend GenLab M5GP

API FastAPI con autenticación JWT, usuarios, datasets, experimentos, artefactos
y control de una tarea por GPU. La carga de datasets admite archivos `CSV` separados por comas y `TSV` separados por tabuladores.

## Relación con el motor original

El backend no altera el ciclo M5GP. Cada ejecución se inicia en un proceso
independiente y sigue este orden:

1. reservar una GPU física mediante un lease en base de datos;
2. establecer `CUDA_VISIBLE_DEVICES`;
3. importar el paquete `m5gp` dentro del proceso;
4. construir el estimador con parámetros aceptados por su constructor original;
5. ejecutar `fit()` y `predict()`;
6. guardar métricas y artefactos;
7. liberar el lease.

El worker no pasa `backend`, `device_id`, callbacks, límites internos de tiempo
ni parámetros no definidos por el estimador original.

## Arranque

```bash
python -m pip install -e ../core
python -m pip install -e .
uvicorn genlab_api.main:app --app-dir src --workers 1
```

## Gestión de experimentos

La API permite:

- `POST /api/v1/experiments/{id}/rerun`: volver a ejecutar el mismo experimento con su configuración almacenada;
- `DELETE /api/v1/experiments/{id}`: eliminar un experimento inactivo y sus artefactos;
- `GET /api/v1/experiments/{id}`: consultar parámetros iniciales, estado, progreso y resultados.

El progreso de entrenamiento se obtiene leyendo las líneas `Generation: n` que
imprime el motor original. El backend no modifica el ciclo evolutivo.


## Regresión y clasificación

El campo `task_type` de cada experimento determina el estimador original que
crea el worker:

- `regression` → `m5gpRegressor`;
- `classification` → `m5gpClassifier`.

La validación de la API mantiene separados los parámetros de cada tarea. Para
clasificación, `evaluationMethod` acepta 0–3 y se admiten `scorer`, `crossVal`,
`k`, `averageMode` y `CrossAverage`.

## Artefactos por tipo

Todos los experimentos completados generan `model.joblib`, `predictions.csv`,
`metrics.json`, `model.txt`, `generation_history.json`, `test_results.json` y
`experiment.json`.

Los experimentos de clasificación agregan `classification_report.json` y
`confusion_matrix.json`. El endpoint
`GET /api/v1/experiments/{id}/visualization` entrega el historial y una muestra
de resultados de prueba para el frontend.

## Endpoint Acerca de

`GET /api/v1/about` es público y devuelve metadatos de versión, autoría,
instituciones de apoyo, referencias, código fuente y términos legales. No
requiere JWT.
