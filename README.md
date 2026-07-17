# GenLab M5GP

Laboratorio Web y API REST para M5GP 2.0, conservando su uso directo mediante
scripts Python y su integración con SRBench v2.

## Estructura definitiva: una sola fuente

```text
GenLab_M5GP/
├── core/
│   ├── src/m5gp/               # única copia M5GP usada por GenLab
│   └── tests/                  # scripts directos: python m5gp_Test.py
├── integrations/
│   └── srbench/                # adaptador + instalador; no duplica el motor
├── backend/                    # FastAPI, JWT, datasets, experimentos y GPU
├── frontend/                   # React y sesiones de usuario
├── tools/                      # instalador del core desde GitHub
├── docs/
├── data/
└── infra/
```

No existe `core/methods` ni `core/methods/src`.

## 1. Obtener el código original M5GP

```bash
python tools/install_core_from_github.py --ref main --copy-tests
python -m pip install -e core
```

El primer comando clona el repositorio M5GP 2.0 y coloca los módulos en la única
carpeta `core/src/m5gp`. No cambia `m5gp.py`, `compute_individuals`, los kernels
CUDA, selección, UMAD, supervivencia, reemplazo, predicción ni construcción
simbólica.

## 2. Ejecutar M5GP directamente

```bash
cd core/tests
python m5gp_Test.py
```

No requiere backend, API, JWT ni frontend.

## 3. Instalar M5GP en SRBench v2

```bash
bash integrations/srbench/install.sh /ruta/srbench --ref main
```

El instalador crea en SRBench:

```text
experiment/methods/m5gpRegressor.py
experiment/methods/src/m5gp/*.py
```

La referencia Git puede fijarse a un tag o commit con `--ref`.

## 4. Backend

```bash
python -m pip install -e backend
uvicorn genlab_api.main:app --app-dir backend/src \
  --host 0.0.0.0 --port 8000 --workers 1
```

El worker asigna una tarea por GPU. En un equipo con N GPUs puede mantener N
tareas M5GP simultáneas, una por dispositivo; cuando todas están ocupadas se
rechaza una ejecución nueva.

## 5. Probar la API REST

La API expone documentación interactiva en:

```text
http://localhost:8000/docs
```

Antes de realizar la prueba, instale el núcleo y el backend y mantenga el
servidor activo en una terminal:

```bash
cd /ruta/GenLab_M5GP
python tools/install_core_from_github.py --ref main --copy-tests
python -m pip install -e core
python -m pip install -e backend
cp .env.example .env

uvicorn genlab_api.main:app --app-dir backend/src \
  --host 0.0.0.0 --port 8000 --workers 1
```

En otra terminal, ejecute el siguiente flujo de prueba. Los comandos usan
`curl` y Python para leer las respuestas JSON; no requieren `jq`.

### 5.1 Comprobar el servicio

```bash
API_URL="http://localhost:8000"

curl -sS "$API_URL/health" | python -m json.tool
```

La respuesta esperada contiene:

```json
{
  "status": "ok",
  "service": "GenLab M5GP API",
  "version": "1.0.0"
}
```

### 5.2 Registrar un usuario e iniciar sesión

```bash
EMAIL="profesor@example.com"
PASSWORD="GenLabPrueba2026!"

curl -sS -X POST "$API_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"full_name\":\"Usuario de prueba\",\"password\":\"$PASSWORD\"}" \
  | python -m json.tool

TOKENS=$(curl -sS -X POST "$API_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

ACCESS_TOKEN=$(printf '%s' "$TOKENS" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

REFRESH_TOKEN=$(printf '%s' "$TOKENS" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["refresh_token"])')

curl -sS "$API_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool
```

Si el usuario ya fue registrado, el endpoint de registro responderá `409`; en
ese caso puede continuar directamente con el inicio de sesión.

### 5.3 Crear y cargar un dataset de prueba

```bash
cat > /tmp/genlab_demo.csv <<'CSV'
x1,x2,target
1.0,2.0,5.0
2.0,1.0,5.0
3.0,4.0,11.0
4.0,3.0,11.0
5.0,6.0,17.0
6.0,5.0,17.0
7.0,8.0,23.0
8.0,7.0,23.0
CSV

DATASET=$(curl -sS -X POST "$API_URL/api/v1/datasets" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "name=Dataset demostrativo" \
  -F "file=@/tmp/genlab_demo.csv;type=text/csv")

printf '%s' "$DATASET" | python -m json.tool

DATASET_ID=$(printf '%s' "$DATASET" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -sS "$API_URL/api/v1/datasets/$DATASET_ID/preview" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool
```

La misma ruta acepta archivos TSV. En ese caso, utilice una extensión `.tsv`
y datos separados por tabuladores, por ejemplo:

```bash
printf 'x1\tx2\ttarget\n1.0\t2.0\t5.0\n2.0\t1.0\t5.0\n' \
  > /tmp/genlab_demo.tsv

curl -sS -X POST "$API_URL/api/v1/datasets" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "name=Dataset TSV demostrativo" \
  -F "file=@/tmp/genlab_demo.tsv;type=text/tab-separated-values" \
  | python -m json.tool
```

El backend determina el separador por la extensión: coma para `.csv` y
tabulador para `.tsv`. La vista previa y el worker de experimentos utilizan la
misma regla.

### 5.4 Crear un experimento de regresión

Para regresión, `evaluationMethod` puede seleccionar cualquiera de los métodos
definidos por el estimador original de M5GP:

```text
evaluationMethod = 0   RMSE directo
evaluationMethod = 1   R² directo
evaluationMethod = 2   Linear Regression (cuML)
evaluationMethod = 3   Lasso Regression (cuML)
evaluationMethod = 4   Ridge Regression (cuML)
evaluationMethod = 5   Kernel Ridge Regression
evaluationMethod = 6   ElasticNet Regression (cuML)
evaluationMethod = 7   MiniBatch sin regularización (Linear Regression)
evaluationMethod = 8   MiniBatch Lasso
evaluationMethod = 9   MiniBatch Ridge
evaluationMethod = 10  MiniBatch ElasticNet

scorer = 0  RMSE
scorer = 1  RMSE
scorer = 2  R²
```

El valor seleccionado se envía sin transformación al constructor original de
`m5gpRegressor` y queda almacenado en `parameters`, `metrics.json` y
`experiment.json` para mantener la reproducibilidad del experimento.

```bash
EXPERIMENT=$(curl -sS -X POST "$API_URL/api/v1/experiments" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  --data "$(cat <<JSON
{
  "name": "Prueba API M5GP",
  "dataset_id": "$DATASET_ID",
  "task_type": "regression",
  "target_column": "target",
  "parameters": {
    "generations": 2,
    "Individuals": 64,
    "GenesIndividuals": 32,
    "mutationProb": 0.1,
    "mutationDeleteRateProb": 0.05,
    "sizeTournament": 0.15,
    "evaluationMethod": 4,
    "scorer": 0,
    "log": 1,
    "verbose": 1
  }
}
JSON
)")

printf '%s' "$EXPERIMENT" | python -m json.tool

EXPERIMENT_ID=$(printf '%s' "$EXPERIMENT" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
```

### 5.5 Crear un experimento de clasificación

La misma API permite definir un experimento de clasificación mediante
`task_type: "classification"`. En este caso, `evaluationMethod` selecciona el
clasificador del motor original y `scorer` selecciona la métrica utilizada por
M5GP durante la evaluación:

```text
evaluationMethod = 0  Logistic Regression
evaluationMethod = 1  Support Vector Classifier
evaluationMethod = 2  Random Forest Classifier
evaluationMethod = 3  K Neighbors Classifier

scorer = 0  Accuracy
scorer = 1  ROC AUC
scorer = 2  F1 Score
scorer = 3  Average Precision
```

Ejemplo:

```bash
CLASSIFICATION_EXPERIMENT=$(curl -sS -X POST "$API_URL/api/v1/experiments" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  --data "$(cat <<JSON
{
  "name": "Clasificación M5GP",
  "dataset_id": "$DATASET_ID",
  "task_type": "classification",
  "target_column": "class",
  "parameters": {
    "generations": 2,
    "Individuals": 64,
    "GenesIndividuals": 32,
    "mutationProb": 0.1,
    "mutationDeleteRateProb": 0.05,
    "sizeTournament": 0.15,
    "evaluationMethod": 0,
    "scorer": 0,
    "crossVal": true,
    "k": 3,
    "averageMode": "macro",
    "CrossAverage": false,
    "log": 1,
    "verbose": 1
  }
}
JSON
)" )

printf '%s' "$CLASSIFICATION_EXPERIMENT" | python -m json.tool
```

Los valores de la columna objetivo deben ser compatibles con el clasificador
original de M5GP. El backend selecciona `m5gpClassifier` cuando el tipo de tarea
es `classification`; para regresión continúa seleccionando `m5gpRegressor`.

### 5.6 Consultar GPUs e iniciar la ejecución

```bash
curl -sS "$API_URL/api/v1/gpus" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool

curl -sS -X POST \
  "$API_URL/api/v1/experiments/$EXPERIMENT_ID/run" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool
```

La ejecución requiere un equipo con GPU NVIDIA y el entorno CUDA/RAPIDS/cuML
utilizado por M5GP. Si no hay una GPU disponible, la API responderá `409` con el
mensaje correspondiente.

### 5.7 Consultar el estado hasta finalizar

```bash
while true; do
  RESULT=$(curl -sS \
    "$API_URL/api/v1/experiments/$EXPERIMENT_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN")

  printf '%s' "$RESULT" | python -m json.tool
  STATUS=$(printf '%s' "$RESULT" | \
    python -c 'import json,sys; print(json.load(sys.stdin)["status"])')

  case "$STATUS" in
    completed|failed|cancelled|rejected) break ;;
  esac

  sleep 5
done
```

Cuando el estado sea `completed`, pueden descargarse los resultados:

```bash
curl -sS \
  "$API_URL/api/v1/experiments/$EXPERIMENT_ID/artifacts/metrics.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o metrics.json

curl -sS \
  "$API_URL/api/v1/experiments/$EXPERIMENT_ID/artifacts/model.txt" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o model.txt

curl -sS \
  "$API_URL/api/v1/experiments/$EXPERIMENT_ID/artifacts/predictions.csv" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o predictions.csv

curl -sS \
  "$API_URL/api/v1/experiments/$EXPERIMENT_ID/artifacts/experiment.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o experiment.json

cat metrics.json
cat model.txt
python -m json.tool experiment.json
```

### 5.8 Volver a ejecutar o eliminar un experimento

Para volver a ejecutar el mismo experimento con el dataset, variable objetivo y
parámetros almacenados originalmente:

```bash
curl -sS -X POST   "$API_URL/api/v1/experiments/$EXPERIMENT_ID/rerun"   -H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool
```

La reejecución conserva la configuración inicial, elimina los artefactos de la
ejecución anterior y genera nuevamente el modelo, métricas y predicciones. Si
el experimento está activo o no hay una GPU libre, la API responde `409`.

Para eliminar un experimento que no se encuentre activo:

```bash
curl -i -X DELETE   "$API_URL/api/v1/experiments/$EXPERIMENT_ID"   -H "Authorization: Bearer $ACCESS_TOKEN"
```

La respuesta correcta es `204 No Content`. También se eliminan el log y los
artefactos asociados. No se elimina el dataset utilizado.

## 6. Frontend Web

El frontend es una aplicación de una sola página desarrollada con React,
TypeScript y Vite. Consume exclusivamente la API REST del backend; no importa
ni ejecuta directamente el motor M5GP. Esta separación permite que la misma
interfaz Web pueda utilizar un backend instalado en el mismo equipo, en otro
servidor de la red o en una infraestructura remota con GPUs.

### 6.1 Requisitos previos

Antes de iniciar el frontend deben cumplirse las siguientes condiciones:

1. El backend debe estar instalado y ejecutándose.
2. La API debe responder en `http://localhost:8000/health`.
3. El origen del frontend debe estar autorizado por CORS en el backend.
4. Debe estar disponible Node.js. Se recomienda Node.js 22, que es la versión
   utilizada por el Dockerfile del proyecto.

Compruebe las versiones instaladas:

```bash
node --version
npm --version
```

Compruebe que la API esté activa:

```bash
curl -sS http://localhost:8000/health | python -m json.tool
```

La configuración predeterminada del backend permite solicitudes desde:

```text
http://localhost:5173
```

Esta dirección se establece mediante:

```env
GENLAB_CORS_ORIGINS=http://localhost:5173
```

Si el frontend se publica en otra dirección, dominio o puerto, debe actualizarse
`GENLAB_CORS_ORIGINS` en el archivo `.env` de la raíz y reiniciarse el backend.

### 6.2 Configurar la dirección de la API

El cliente utiliza de forma predeterminada:

```text
http://localhost:8000/api/v1
```

La dirección se obtiene de la variable Vite `VITE_API_URL`. Para declarar una
dirección explícita, cree el archivo `frontend/.env.local`:

```bash
cat > frontend/.env.local <<'ENV'
VITE_API_URL=http://localhost:8000/api/v1
ENV
```

La URL debe incluir el prefijo `/api/v1`, porque el cliente concatena sobre esa
base rutas como `/auth/login`, `/datasets`, `/experiments` y `/gpus`.

Ejemplo para un backend ubicado en otro equipo de la red:

```env
VITE_API_URL=http://192.168.1.50:8000/api/v1
```

En ese caso, el backend también debe permitir el origen desde el cual se abre el
frontend, por ejemplo:

```env
GENLAB_CORS_ORIGINS=http://192.168.1.50:5173
```

Las variables `VITE_*` se incorporan durante el arranque o compilación de Vite.
Después de modificar `frontend/.env.local`, debe reiniciarse `npm run dev`.

### 6.3 Instalar y ejecutar en modo de desarrollo

Mantenga el backend ejecutándose en una primera terminal:

```bash
cd /ruta/GenLab_M5GP

uvicorn genlab_api.main:app --app-dir backend/src \
  --host 0.0.0.0 --port 8000 --workers 1
```

En una segunda terminal, instale e inicie el frontend:

```bash
cd /ruta/GenLab_M5GP/frontend
npm install
npm run dev
```

Vite mostrará una salida similar a:

```text
Local: http://localhost:5173/
```

Abra esa dirección en el navegador:

```text
http://localhost:5173
```

Para permitir acceso desde otro equipo de la misma red:

```bash
npm run dev -- --host 0.0.0.0
```

Después acceda mediante la IP del equipo que ejecuta Vite, por ejemplo:

```text
http://192.168.1.50:5173
```

### 6.4 Flujo completo de prueba desde la interfaz Web

#### Paso 1. Registrar un usuario

Al abrir el frontend aparece la pantalla de autenticación.

1. Seleccione **Crear una cuenta**.
2. Capture nombre, correo electrónico y contraseña.
3. La contraseña debe contener al menos 10 caracteres, de acuerdo con el
   formulario actual.
4. Presione **Registrarme**.

El frontend realiza primero:

```text
POST /api/v1/auth/register
```

Después inicia sesión automáticamente mediante:

```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

También puede utilizar un usuario creado previamente desde la API y seleccionar
**Iniciar sesión**.

#### Paso 2. Verificar el panel principal

Después de autenticarse se muestra **Overview**, con los siguientes indicadores:

- número de datasets del usuario;
- número de experimentos;
- GPUs disponibles respecto al total detectado;
- ejecuciones activas;
- tabla de experimentos recientes.

El panel consulta periódicamente:

```text
GET /api/v1/datasets
GET /api/v1/experiments
GET /api/v1/gpus
```

La información se actualiza aproximadamente cada cuatro segundos.

#### Paso 3. Cargar un dataset

Abra **Datasets** desde la barra lateral.

1. Escriba un nombre descriptivo.
2. Seleccione un archivo CSV o TSV.
3. Presione **Cargar dataset**.

El frontend envía un formulario `multipart/form-data` a:

```text
POST /api/v1/datasets
```

Para una prueba mínima puede crear el siguiente archivo:

```bash
cat > /tmp/genlab_frontend_demo.csv <<'CSV'
x1,x2,target
1.0,2.0,5.0
2.0,1.0,5.0
3.0,4.0,11.0
4.0,3.0,11.0
5.0,6.0,17.0
6.0,5.0,17.0
7.0,8.0,23.0
8.0,7.0,23.0
CSV
```

Seleccione `/tmp/genlab_frontend_demo.csv` en el formulario. También puede seleccionar un archivo `.tsv` separado por tabuladores. Cuando la carga
termine, el dataset debe aparecer en la tabla con:

- nombre asignado;
- nombre del archivo original;
- número de filas y columnas;
- fecha de creación.

#### Paso 4. Revisar los recursos GPU

Abra **GPU Resources**.

La pantalla muestra una tarjeta por GPU con:

- identificador lógico;
- nombre del dispositivo;
- estado `available` o `busy`;
- memoria total, cuando puede obtenerse.

Esta vista consulta:

```text
GET /api/v1/gpus
```

Si no se detectan GPUs, la interfaz mostrará el mensaje correspondiente. En esa
situación pueden probarse autenticación, sesiones, datasets y navegación, pero
la ejecución de M5GP no podrá completarse porque el núcleo original requiere
CUDA, RAPIDS y cuML.

#### Paso 5. Crear un experimento

Abra **Experiments** y presione **Nuevo experimento**.

Complete el formulario:

- **Nombre:** nombre identificador de la ejecución.
- **Dataset:** archivo cargado previamente.
- **Objetivo:** columna que se desea predecir.
- **Tarea:** regresión simbólica o clasificación.
- **generations:** número de generaciones.
- **Individuals:** tamaño de la población.
- **GenesIndividuals:** genes por individuo.
- **mutationProb:** probabilidad de mutación.
- **mutationDeleteRateProb:** probabilidad de eliminación durante UMAD.
- **sizeTournament:** proporción utilizada para el torneo.
- **evaluationMethod:** método de regresión o clasificador definido por M5GP.
- **scorer:** métrica utilizada durante la evaluación.
- Para clasificación: **crossVal**, **k**, **averageMode** y **CrossAverage**.

Al seleccionar **Regresión simbólica**, el formulario muestra los once métodos
originales (`evaluationMethod` de 0 a 10), incluyendo RMSE/R² directos, Linear,
Lasso, Ridge, Kernel Ridge, ElasticNet y las cuatro variantes MiniBatch. Cada
opción muestra una descripción breve y el valor numérico que se enviará a la
API. Al seleccionar **Clasificación**, muestra Logistic
Regression, SVC, Random Forest y KNN, además de las opciones de validación
cruzada y promedio de métricas. El cambio de tarea restablece valores válidos
para evitar mezclar parámetros de regresión con parámetros del clasificador.

Para una prueba rápida de integración de regresión puede utilizar:

```text
generations = 2
Individuals = 64
GenesIndividuals = 32
mutationProb = 0.10
mutationDeleteRateProb = 0.05
sizeTournament = 0.15
evaluationMethod = 4
```

Estos valores reducen la duración de la prueba, pero no constituyen una
configuración recomendada para experimentos científicos finales.

Al presionar **Crear y ejecutar**, el frontend realiza dos operaciones:

```text
POST /api/v1/experiments
POST /api/v1/experiments/{experiment_id}/run
```

Después abre automáticamente la página de detalle del experimento.

#### Paso 6. Monitorear la ejecución

La pantalla de detalle consulta el experimento aproximadamente cada tres
segundos:

```text
GET /api/v1/experiments/{experiment_id}
```

Muestra:

- estado de la ejecución;
- GPU asignada;
- porcentaje y barra de progreso;
- generación actual y total de generaciones;
- parámetros iniciales utilizados para crear el experimento;
- dataset, variable objetivo y tipo de tarea;
- complejidad del modelo;
- métricas finales, diferenciadas entre regresión y clasificación;
- expresión simbólica;
- mensaje de error, si la ejecución falla.

En experimentos de regresión aparecen dos gráficas:

1. **Evolución del ajuste por generación**, construida con el valor `Train Fit`
   que el ciclo original de M5GP imprime al terminar cada generación.
2. **Comparación de resultados de prueba**, que superpone los valores reales y
   las predicciones del conjunto de prueba. Para datasets grandes, la API
   entrega una muestra uniforme de hasta 300 observaciones exclusivamente para
   visualización; el archivo `predictions.csv` conserva todos los resultados.

La información gráfica se consulta mediante:

```text
GET /api/v1/experiments/{experiment_id}/visualization
```

La gráfica no modifica ni intercepta el ciclo evolutivo: el backend lee el log
y los artefactos generados después de ejecutar `fit()` y `predict()`.

El porcentaje no es una estimación de tiempo. Se determina por el avance del
flujo real del worker:

```text
1%       GPU reservada
3%       carga del dataset
5%       preparación de datos y estimador
8%       inicialización de población y evaluación inicial
8%-90%   generaciones del ciclo evolutivo
92%      evaluación sobre datos de prueba
97%      guardado de artefactos
100%     ejecución finalizada
```

Durante el ciclo evolutivo, el backend lee del log las líneas que el
`m5gp.py` original imprime con el formato `Generation: n`. El cálculo es:

```text
porcentaje = 8 + redondear(82 × generación_actual / generaciones_totales)
```

El resultado se limita a 90% durante entrenamiento. Cada generación puede
tardar un tiempo distinto, por lo que 50% de avance no implica necesariamente
50% del tiempo total. Este seguimiento no modifica `m5gp.py`,
`compute_individuals` ni los demás métodos del ciclo evolutivo.

Los estados que pueden observarse dependen del backend, pero normalmente el
flujo pasa por creación, reserva de GPU, ejecución y finalización. Si todas las
GPUs están ocupadas, el backend rechaza el inicio con HTTP `409`.

#### Paso 7. Consultar configuración, reejecutar o eliminar

En la página de detalle se muestra la sección **Parámetros iniciales**, con el
dataset, columna objetivo, tipo de tarea y los valores almacenados en
`parameters`.

El botón **Volver a ejecutar** utiliza:

```text
POST /api/v1/experiments/{experiment_id}/rerun
```

La reejecución conserva la configuración y reemplaza los resultados anteriores.
El botón **Eliminar** utiliza:

```text
DELETE /api/v1/experiments/{experiment_id}
```

Por seguridad, ambos botones se deshabilitan mientras el experimento está en
estado `reserved`, `running` o `cancelling`. La eliminación también está
disponible desde la tabla del historial.

#### Paso 8. Descargar artefactos

Cuando el experimento termina, la sección **Artefactos** permite solicitar:

```text
model.joblib
predictions.csv
metrics.json
model.txt
generation_history.json
test_results.json
experiment.json
```

Para clasificación también se generan:

```text
classification_report.json
confusion_matrix.json
```

El frontend descarga cada archivo utilizando el JWT del usuario:

```text
GET /api/v1/experiments/{experiment_id}/artifacts/{filename}
```

La disponibilidad de cada artefacto depende de que la ejecución haya concluido
y de que el worker lo haya generado correctamente.

El botón **Resultados completos JSON** descarga `experiment.json`. Para un
experimento de regresión, el documento incluye:

- nombre del dataset y algoritmo;
- parámetros efectivos del estimador;
- semilla aleatoria;
- tiempo de proceso y tiempo de pared del entrenamiento;
- niveles de ruido de objetivo y características;
- tamaño y expresión simbólica del modelo;
- MSE, MAE y R² para entrenamiento y prueba.

Para clasificación se mantienen los mismos campos generales y se agregan
`accuracy_train`, `f1_macro_train`, `precision_macro_train`,
`recall_macro_train`, `accuracy_test`, `f1_macro_test`,
`precision_macro_test` y `recall_macro_test`. Los campos de regresión permanecen
con valor `null` para conservar un esquema estable. Además:

- `metrics.json` contiene secciones `train` y `test` apropiadas para la tarea;
- `classification_report.json` contiene el reporte por clase;
- `confusion_matrix.json` contiene clases y matriz de confusión;
- `generation_history.json` conserva el historial de `Train Fit`;
- `test_results.json` conserva valores reales y predicciones para las gráficas.

### 6.5 Cómo funcionan las sesiones

El frontend almacena temporalmente los tokens en el navegador con la clave:

```text
genlab_tokens
```

El valor se guarda en `localStorage` e incluye:

- `access_token`;
- `refresh_token`.

En cada solicitud protegida se envía:

```http
Authorization: Bearer <access_token>
```

Cuando la API responde `401`, el cliente intenta renovar la sesión mediante:

```text
POST /api/v1/auth/refresh
```

Si la renovación falla, elimina los tokens y vuelve a mostrar la pantalla de
inicio de sesión. Al cerrar sesión se invoca `/auth/logout` y se limpia el
almacenamiento local.

Para borrar manualmente una sesión durante pruebas, abra las herramientas de
desarrollo del navegador y ejecute en la consola:

```javascript
localStorage.removeItem('genlab_tokens')
location.reload()
```

### 6.6 Verificar las solicitudes desde el navegador

Para revisar la comunicación frontend-backend:

1. Abra las herramientas de desarrollo del navegador.
2. Seleccione la pestaña **Network** o **Red**.
3. Filtre por `fetch` o `XHR`.
4. Ejecute una operación, por ejemplo iniciar sesión o cargar un dataset.
5. Compruebe la URL, método HTTP, código de respuesta y cuerpo JSON.

Las solicitudes protegidas deben contener el encabezado `Authorization`. Una
respuesta `401` suele indicar token ausente, vencido o inválido. Una respuesta
`403` indica que el usuario no tiene acceso al recurso. Una respuesta `409` al
iniciar un experimento normalmente indica que no existe una GPU libre.

### 6.7 Compilar y probar la versión de producción

Antes de desplegar el frontend, verifique que TypeScript y Vite compilen:

```bash
cd frontend
npm install
npm run build
```

El resultado se genera en:

```text
frontend/dist/
```

Para probar localmente esa compilación:

```bash
npm run preview -- --host 0.0.0.0
```

Vite mostrará el puerto utilizado, normalmente:

```text
http://localhost:4173
```

Si utiliza el puerto `4173`, debe añadirlo a CORS durante la prueba:

```env
GENLAB_CORS_ORIGINS=http://localhost:4173
```

Después reinicie el backend.

### 6.8 Ejecución mediante Docker Compose

Desde la raíz del proyecto:

```bash
docker compose up --build
```

La configuración incluida inicia:

- PostgreSQL;
- API en `http://localhost:8000`;
- frontend servido por Nginx en `http://localhost:5173`.

Compruebe:

```bash
curl -sS http://localhost:8000/health | python -m json.tool
```

Y abra:

```text
http://localhost:5173
```

Para que los contenedores ejecuten M5GP se requiere Docker con soporte NVIDIA y
acceso a las GPUs del host. La imagen del backend también debe disponer del
entorno CUDA/RAPIDS/cuML compatible con el motor instalado.

### 6.9 Rutas principales de la interfaz

```text
/                       Overview
/datasets               Gestión de datasets
/experiments            Historial de experimentos
/experiments/new        Creación de experimento
/experiments/{id}       Detalle, métricas y artefactos
/resources              Estado de GPUs
```

Las rutas requieren una sesión válida. Cuando no existe un usuario autenticado,
la aplicación muestra la pantalla de login y registro.

### 6.10 Problemas frecuentes

#### El navegador muestra `Failed to fetch` o `NetworkError`

Compruebe que:

```bash
curl -sS http://localhost:8000/health
```

responda correctamente y que `VITE_API_URL` apunte a la dirección real de la
API.

#### Error de CORS

Ajuste en `.env`:

```env
GENLAB_CORS_ORIGINS=http://localhost:5173
```

Reinicie el backend después del cambio.

#### El login devuelve `401`

Verifique correo y contraseña. Para reiniciar la sesión del navegador:

```javascript
localStorage.removeItem('genlab_tokens')
location.reload()
```

#### No aparecen GPUs

Compruebe en el host:

```bash
nvidia-smi
```

También confirme que el proceso del backend tenga acceso a los dispositivos
NVIDIA y que se encuentre activo el entorno CUDA/RAPIDS/cuML.

#### El experimento devuelve `409`

Todas las GPUs se encuentran ocupadas. La primera versión de GenLab M5GP no
mantiene una cola de trabajos; debe esperar a que se libere un dispositivo y
volver a iniciar el experimento.

#### Al seleccionar un TSV aparece «Solo se admiten archivos CSV»

Ese texto corresponde a una versión anterior de la aplicación. La versión
actual valida explícitamente las extensiones `.csv` y `.tsv` y muestra:

```text
Solo se admiten archivos CSV o TSV
```

Si ejecuta el frontend con Vite, detenga los procesos anteriores y vuelva a
iniciar backend y frontend:

```bash
# Terminal 1
cd /home/acardenasf/GenLab_M5GP_clean
source .venv/bin/activate
uvicorn genlab_api.main:app --app-dir backend/src --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd /home/acardenasf/GenLab_M5GP_clean/frontend
npm ci
npm run dev -- --host 0.0.0.0
```

Después realice una recarga forzada del navegador:

```text
Ctrl + Shift + R
```

Si utiliza Docker Compose, la imagen anterior puede seguir sirviendo un bundle
Web y un backend desactualizados. Reconstruya ambos servicios sin caché:

```bash
cd /home/acardenasf/GenLab_M5GP_clean
docker compose down
docker compose build --no-cache api web
docker compose up -d --force-recreate api web
```

Compruebe además que el backend activo contiene el mensaje actualizado:

```bash
grep -R "Solo se admiten archivos CSV o TSV" \
  backend/src/genlab_api/services/files.py
```

Y que el frontend permite ambas extensiones:

```bash
grep -R 'accept=".csv,.tsv' frontend/src/pages.tsx
```

#### El experimento falla con `FileNotFoundError` en `data/uploads/...`

Este error corresponde a versiones que almacenaban la ubicación del dataset
como una ruta relativa. El worker cambia temporalmente su directorio de trabajo
al directorio de artefactos del experimento y la ruta relativa deja de apuntar
al archivo cargado.

La versión actual guarda las nuevas cargas con una ruta absoluta y resuelve
automáticamente los registros anteriores. Al ejecutar por primera vez un
experimento antiguo, el backend actualiza en la base de datos la ruta relativa
a su ubicación absoluta.

Después de instalar la corrección, reinicie el backend:

```bash
cd /home/acardenasf/GenLab_M5GP_clean
source .venv/bin/activate
uvicorn genlab_api.main:app --app-dir backend/src --host 0.0.0.0 --port 8000 --reload
```

Compruebe que el archivo continúe físicamente en:

```text
data/uploads/<id-del-usuario>/<nombre-del-dataset>.csv
data/uploads/<id-del-usuario>/<nombre-del-dataset>.tsv
```

Si el archivo fue eliminado manualmente, vuelva a cargarlo desde el frontend y
cree un nuevo experimento asociado con la nueva carga.

#### El frontend sigue usando una URL anterior

Detenga `npm run dev`, revise `frontend/.env.local` y vuelva a iniciar Vite. En
una compilación de producción, ejecute nuevamente `npm run build`.

#### La compilación falla después de actualizar dependencias

Elimine la instalación local y utilice el archivo de bloqueo:

```bash
cd frontend
rm -rf node_modules
npm ci
npm run build
```


### Diagnóstico de una página Web en blanco

La interfaz valida la sesión almacenada antes de iniciar React. Si el navegador
conserva datos incompatibles de una versión anterior, estos se eliminan y se
muestra nuevamente el inicio de sesión.

Después de actualizar el frontend:

```bash
cd frontend
rm -rf node_modules dist
npm ci
npm run dev -- --host 0.0.0.0
```

En el navegador utilice `Ctrl+Shift+R`. También puede limpiar manualmente la
sesión desde la consola:

```javascript
localStorage.removeItem('genlab_tokens');
location.reload();
```

Los errores de renderizado se presentan ahora en una pantalla de diagnóstico,
en lugar de producir una página completamente vacía.

### Corrección de pantalla en blanco por `LineChart`

La gráfica se encuentra en `frontend/src/charts.tsx` y se importa desde `pages.tsx` con:

```typescript
import { LineChart } from './charts';
```

Esta separación evita incompatibilidades entre versiones anteriores de `components.tsx` y las páginas que utilizan las gráficas. Después de actualizar, elimine la caché de Vite y reinstale dependencias:

```bash
cd frontend
rm -rf node_modules dist node_modules/.vite
npm ci
npm run dev -- --host 0.0.0.0
```

Después realice una recarga forzada del navegador con `Ctrl + Shift + R`.

## Corrección de descargas: historial y resultados de prueba

En la página de detalle de un experimento completado, los botones **Historial por generación** y **Resultados de prueba JSON** descargan respectivamente:

- `generation_history.json`: tarea, nombre de la métrica de ajuste e historial `{generation, fit}`.
- `test_results.json`: tarea, índice de muestra, valor real y predicción.

Para mantener compatibilidad con experimentos completados antes de incorporar estos artefactos, la API puede generarlos bajo demanda:

- El historial se recupera primero desde `experiment.progress.history` y, si no existe, desde las líneas `Generation: ... Train Fit: ...` del log.
- Los resultados de prueba se reconstruyen desde `predictions.csv`.

Los archivos reconstruidos se guardan en el directorio de artefactos del experimento, de modo que las descargas posteriores usan el archivo ya generado.

Si la descarga falla, el frontend muestra el detalle del error HTTP en la misma página en lugar de ignorar la promesa de descarga.

## Corrección de descargas JSON y gráficas

La página de resultados ya no depende del endpoint combinado
`/api/v1/experiments/{id}/visualization`. Para evitar incompatibilidades entre
versiones del backend y frontend, utiliza dos endpoints JSON explícitos:

```text
GET /api/v1/experiments/{id}/generation-history
GET /api/v1/experiments/{id}/test-results
GET /api/v1/experiments/{id}/test-results?max_points=300
```

- **Historial por generación** descarga el primer endpoint como
  `generation_history.json`.
- **Resultados de prueba JSON** descarga el segundo endpoint como
  `test_results.json`.
- Las gráficas consultan esos mismos endpoints; para la gráfica de prueba se
  usa `max_points=300`, mientras la descarga conserva todos los registros.
- El backend reconstruye los JSON desde `progress`/log y `predictions.csv`
  cuando un experimento antiguo todavía no tiene esos archivos físicos.

Después de actualizar, reinicie por completo ambos servicios:

```bash
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 5173/tcp 2>/dev/null || true

cd /home/acardenasf/GenLab_M5GP
source .venv/bin/activate
uvicorn genlab_api.main:app \
  --app-dir backend/src \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

En otra terminal:

```bash
cd /home/acardenasf/GenLab_M5GP/frontend
rm -rf node_modules/.vite dist
npm ci
npm run dev -- --host 0.0.0.0
```

Compruebe que el backend actualizado cargó las rutas:

```bash
curl -s http://localhost:8000/openapi.json | python -c '
import json, sys
paths = json.load(sys.stdin)["paths"]
for path in sorted(paths):
    if "generation-history" in path or "test-results" in path:
        print(path)
'
```

La salida esperada es:

```text
/api/v1/experiments/{experiment_id}/generation-history
/api/v1/experiments/{experiment_id}/test-results
```

El frontend corregido no debe realizar solicitudes a:

```text
/api/v1/experiments/{id}/visualization
```

## Compatibilidad de artefactos JSON de experimentos anteriores

Los botones **Historial por generación** y **Resultados de prueba JSON** utilizan los endpoints dedicados:

```text
GET /api/v1/experiments/{id}/generation-history
GET /api/v1/experiments/{id}/test-results
```

El backend conserva además compatibilidad con las URL históricas:

```text
GET /api/v1/experiments/{id}/artifacts/generation_history.json
GET /api/v1/experiments/{id}/artifacts/test_results.json
```

Para experimentos antiguos, aunque el campo `artifact_dir` esté vacío, la API busca el directorio determinístico `data/artifacts/<usuario>/<experimento>`. El historial se reconstruye desde el progreso o el log y los resultados de prueba desde `predictions.csv`.

## Solución de instalación npm fuera del entorno de generación

El `package-lock.json` del frontend usa exclusivamente el registro público de npm. No debe contener direcciones internas como `packages.applied-caas-gateway1.internal.api.openai.org`.

Verificación:

```bash
cd frontend
grep -n "applied-caas-gateway" package-lock.json
```

El comando no debe producir salida.

Requisitos del frontend:

```bash
node --version
npm --version
```

Vite 8 requiere Node.js `20.19.0` o superior, o Node.js `22.12.0` o superior. Se recomienda Node.js 22 LTS.

Instalación limpia:

```bash
cd frontend
rm -rf node_modules dist node_modules/.vite
npm cache verify
npm ci --registry=https://registry.npmjs.org/ --no-audit --no-fund
npm run build
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort --force
```

Si existe una configuración npm global que fuerza otro registro:

```bash
npm config get registry
npm config set registry https://registry.npmjs.org/
```

También deben revisarse los archivos de configuración:

```bash
npm config get userconfig
npm config get globalconfig
```


### Previsualización de datasets en el frontend

En la opción **Datasets**, cada archivo cargado incluye el botón **Previsualizar**. La interfaz consulta `GET /api/v1/datasets/{dataset_id}/preview` y muestra:

- el catálogo de columnas y su tipo de dato;
- las primeras 20 filas del archivo CSV o TSV;
- los nombres exactos que aparecerán en el selector **Variable objetivo** al crear un experimento.

Esta vista permite identificar la columna objetivo antes de abrir **Nuevo experimento**. En la página de resultados, las gráficas de regresión se muestran después de la sección **Artefactos**.


### Selección y vista previa de datasets

En **Datasets cargados**, haga clic sobre cualquier fila para visualizar sus columnas y primeras 20 filas. La vista previa también se abre automáticamente después de cargar un archivo CSV o TSV.

### Cambio de idioma y visualización de contraseña

El frontend incorpora un selector de idioma en la esquina superior derecha. Puede alternar toda la interfaz entre **Español** e **English**; la preferencia queda almacenada en el navegador. La pantalla de acceso también incluye un botón dentro del campo de contraseña para mostrar u ocultar temporalmente el texto capturado.

## Información Acerca de

La aplicación incorpora una opción **Acerca de** en el menú lateral. Esta vista
consulta el endpoint público:

```http
GET /api/v1/about
```

La respuesta incluye la versión exacta de GenLab M5GP, autoría y derechos de
autor, instituciones que apoyan el proyecto, agradecimientos, referencias de
M5GP y M5GP 2.0, enlaces de acceso y descarga del código fuente, y el aviso
legal aplicable.

Prueba rápida:

```bash
curl -s http://localhost:8000/api/v1/about | python -m json.tool
```

La versión puede configurarse con `GENLAB_APP_VERSION` y el canal de publicación
con `GENLAB_RELEASE_CHANNEL`. Los permisos de uso, modificación y redistribución
deben consultarse en el archivo `LICENSE` del repositorio público.

---

## Publicar el proyecto en GitHub

El repositorio oficial de GenLab M5GP está previsto en:

```text
https://github.com/armandocardenasf/GenLab-m5gp
```

Este repositorio **no incluye los módulos fuente originales de M5GP 2.0**. Después de clonar GenLab, instálelos desde su repositorio independiente:

```bash
python tools/install_core_from_github.py --ref main
python -m pip install -e core
```

Antes de confirmar o enviar cambios a GitHub, ejecute:

```bash
python tools/check_github_repository.py
```

Para publicar desde la terminal integrada de VS Code:

```bash
git init -b main
git add .
git commit -m "Initial GenLab M5GP release"
git remote add origin https://github.com/armandocardenasf/GenLab-m5gp.git
git push -u origin main
```

La guía completa para VS Code y terminal está disponible en [`docs/GITHUB_PUBLISHING.md`](docs/GITHUB_PUBLISHING.md).
