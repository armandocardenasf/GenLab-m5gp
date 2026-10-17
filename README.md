# GenLab M5GP

GenLab M5GP es una plataforma Web y API REST para ejecutar, administrar y analizar experimentos de **M5GP 2.0** sobre GPU. La plataforma conserva el motor M5GP como una fuente independiente y añade una capa de experimentación reproducible para regresión simbólica y clasificación, con múltiples datasets, múltiples corridas, validación Train/Test o K-fold, lotes de ejecución, resultados agregados e individuales, visualizaciones y exportación de resultados.

Repositorio GenLab:

```text
https://github.com/armandocardenasf/GenLab-m5gp
```

Motor M5GP 2.0:

```text
https://github.com/armandocardenasf/m5gp-2.0
```

---

## 1. Modelo de trabajo de GenLab

GenLab distingue tres niveles de ejecución y una capa de análisis:

- **Corrida / ejecución (run):** una ejecución individual de M5GP sobre un dataset, con sus parámetros, semilla, partición de datos, métricas, modelo y artefactos.
- **Experimento:** agrupa uno o varios datasets y una o más corridas por dataset. Conserva los resultados individuales y calcula resultados agregados.
- **Lote (batch):** conjunto de experimentos guardados que pueden enviarse a la cola de ejecución.
- **Comparativo / reporte:** análisis guardado que integra dos o más experimentos del mismo tipo para comparar configuraciones, métricas, variabilidad, significancia estadística y costo computacional.

La tabla histórica `experiments` se mantiene por compatibilidad y sus registros representan corridas individuales en el modelo actual. Los experimentos agrupados, asociaciones con datasets, predefinidos y lotes se almacenan en tablas adicionales.

### Funciones principales

La versión actual incluye:

- regresión simbólica y clasificación con M5GP 2.0;
- carga de datasets CSV y TSV;
- múltiples datasets dentro de un experimento;
- múltiples corridas por dataset;
- validación Holdout y K-fold;
- perfiles de ejecución y predefinidos personalizados;
- constructor visual de parámetros que genera la configuración JSON de M5GP;
- cola automática de corridas y ejecución por lotes;
- seguimiento de avance por corrida y generación;
- métricas Train/Test;
- resultados agregados e individuales por dataset;
- gráficas de regresión tipo SRBench para `R² Test`, `RMSE Test`, `Model Size` y `Training Time`;
- gráfica observado contra predicho y correlación de Pearson;
- exportación de resultados a JSON y Excel `.xlsx`;
- comparativos guardados entre experimentos de regresión o entre experimentos de clasificación;
- matriz pareada de Wilcoxon con corrección de Holm-Bonferroni;
- análisis de impacto de parámetros y correlación de Spearman;
- análisis de escalamiento computacional por muestras, características y puntos del dataset;
- descarga de artefactos de cada corrida;
- interfaz bilingüe Español/English;
- autenticación JWT y aislamiento de recursos por usuario;
- control de una corrida activa por GPU.

---

## 2. Estructura del repositorio

```text
GenLab-m5gp/
├── core/
│   ├── src/m5gp/               # paquete canónico usado por GenLab
│   └── tests/                  # pruebas directas del motor
├── integrations/
│   └── srbench/                # adaptador e instalador para SRBench
├── backend/                    # FastAPI, JWT, datasets, experimentos y workers
├── frontend/                   # React, TypeScript y Vite
├── tools/                      # instalación y verificación del proyecto
├── docs/                       # documentación técnica
├── data/                       # base SQLite, uploads, artefactos y logs
├── docker-compose.yml
└── .env.example
```

GenLab no mantiene una segunda copia versionada del motor M5GP. Los archivos originales de M5GP 2.0 se descargan mediante `tools/install_core_from_github.py` y se colocan en `core/src/m5gp/`. Estos archivos están excluidos de Git mediante `.gitignore`.

---

## 3. Requisitos

### 3.1 Requisitos generales

Se requiere:

- Git;
- Python **3.10 a 3.13**;
- Conda/Miniconda/Anaconda para el entorno GPU recomendado;
- `pip` dentro del entorno Conda;
- Node.js para el frontend; se recomienda **Node.js 22**;
- npm;
- navegador Web moderno.

Para ejecutar realmente M5GP se requiere además:

- GPU NVIDIA compatible;
- controlador NVIDIA operativo;
- entorno CUDA compatible con la versión de M5GP instalada;
- dependencias GPU utilizadas por M5GP, particularmente RAPIDS/cuML y las bibliotecas CUDA que requiera el motor.

Compruebe la GPU con:

```bash
nvidia-smi
```

El backend y el frontend pueden arrancar sin GPU para probar autenticación, navegación, datasets y configuración. Las corridas de M5GP requieren el entorno GPU completo.

### 3.2 Dependencias GPU de M5GP

Los archivos `core/pyproject.toml` y `backend/pyproject.toml` instalan las dependencias generales de Python. El backend declara además SciPy para las pruebas estadísticas de Wilcoxon y correlación de Spearman. Estos archivos **no configuran por sí solos el entorno CUDA/RAPIDS/cuML**. Ese entorno debe existir previamente en el sistema o entorno Python donde se ejecutará el worker.

La instalación de CUDA/RAPIDS depende de la GPU, versión de controlador y versión de Python disponibles. Debe utilizarse una combinación compatible con el motor M5GP 2.0 que se vaya a instalar.

---

## 4. Instalación local recomendada

### 4.1 Clonar GenLab

```bash
git clone https://github.com/armandocardenasf/GenLab-m5gp.git
cd GenLab-m5gp
```

### 4.2 Activar el entorno Conda con CUDA/RAPIDS/cuML

Para la instalación actual de GenLab M5GP se recomienda utilizar **el entorno Conda que ya contiene CUDA, RAPIDS/cuML y las dependencias de M5GP**. No es necesario crear un entorno adicional con `python3 -m venv .venv`.

Consulte los entornos disponibles:

```bash
conda env list
```

Active el entorno que utiliza normalmente para M5GP:

```bash
conda activate <NOMBRE_ENTORNO>
```

Compruebe que la terminal está utilizando el Python de Conda:

```bash
which python
python --version
```

Verifique las bibliotecas principales antes de instalar GenLab:

```bash
python -c "import cupy; print('CuPy:', cupy.__version__)"
python -c "import cuml; print('cuML:', cuml.__version__)"
python -c "import numba; print('Numba:', numba.__version__)"
python -c "import numpy, pandas, sklearn; print('Dependencias base OK')"
```

También es conveniente confirmar que el sistema detecta la GPU:

```bash
nvidia-smi
```

Si el entorno Conda existente se utiliza para otros experimentos y se desea evitar modificarlo, puede clonarse antes de instalar GenLab:

```bash
conda create --name genlab-m5gp --clone <NOMBRE_ENTORNO_ORIGINAL>
conda activate genlab-m5gp
```

Esto es opcional. Si el entorno original ya está validado y puede recibir las dependencias del backend, puede utilizarse directamente.

> **Importante:** si previamente creó y activó un entorno con `python3 -m venv .venv`, desactívelo antes de activar Conda:
>
> ```bash
> deactivate
> conda activate <NOMBRE_ENTORNO>
> ```
>
> La carpeta `.venv` puede conservarse o eliminarse si ya no se utilizará. Eliminarla es opcional:
>
> ```bash
> rm -rf .venv
> ```

#### Alternativa: entorno `venv`

Un entorno `.venv` puede utilizarse en instalaciones que no dependan de un entorno Conda/RAPIDS previamente configurado. Sin embargo, `venv` **no instala CUDA ni RAPIDS/cuML por sí mismo**, por lo que no es la opción principal para la instalación GPU actual.

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

### 4.3 Actualizar herramientas Python dentro del entorno activo

Con el entorno Conda ya activado:

```bash
python -m pip install --upgrade pip setuptools wheel
```

### 4.4 Instalar el código original de M5GP 2.0

Desde la raíz de GenLab:

```bash
python tools/install_core_from_github.py --ref main --copy-tests
```

El comando:

1. descarga el repositorio `m5gp-2.0`;
2. copia los módulos originales en `core/src/m5gp/`;
3. registra el commit utilizado en `SOURCE_INFO.json`;
4. opcionalmente copia los scripts de prueba con `--copy-tests`.

Para una ejecución científica reproducible se recomienda sustituir `main` por un tag o commit específico:

```bash
python tools/install_core_from_github.py --ref <tag-o-commit> --copy-tests
```

Instale el paquete local:

```bash
python -m pip install -e core
```

### 4.5 Instalar el backend

Instalación normal:

```bash
python -m pip install -e backend
```

Instalación para desarrollo y pruebas:

```bash
python -m pip install -e 'backend[test]'
```

Si utilizará PostgreSQL:

```bash
python -m pip install -e 'backend[postgres]'
```

### 4.6 Instalar el frontend

```bash
cd frontend
npm ci --no-audit --no-fund
cd ..
```

`npm ci` utiliza las versiones registradas en `package-lock.json` y es la forma recomendada para reproducir la instalación del frontend.

### 4.7 Resumen rápido de instalación con Conda

Para una instalación ya preparada con CUDA/RAPIDS/cuML:

```bash
cd /ruta/GenLab-m5gp
conda activate <NOMBRE_ENTORNO>

python -m pip install --upgrade pip setuptools wheel
python tools/install_core_from_github.py --ref main --copy-tests
python -m pip install -e core
python -m pip install -e 'backend[test]'

cp .env.example .env

cd frontend
npm ci --no-audit --no-fund
npm run build
cd ..
```

Con esto quedan instalados el núcleo M5GP, el backend y el frontend. La ejecución de cada servicio se describe en las secciones 7, 8 y 9.

---

## 5. Configuración del backend

Copie el archivo de ejemplo:

```bash
cp .env.example .env
```

En Windows puede copiarlo manualmente como `.env`.

### 5.1 Variables de entorno

El backend reconoce las siguientes variables:

| Variable | Valor predeterminado | Descripción |
|---|---|---|
| `GENLAB_ENV` | `development` | Identificador del entorno. |
| `GENLAB_SECRET_KEY` | valor de desarrollo | Clave para firmar tokens JWT. Debe cambiarse en una instalación real. |
| `GENLAB_DATABASE_URL` | `sqlite:///./data/genlab.db` | URL SQLAlchemy de la base de datos. |
| `GENLAB_ACCESS_TOKEN_MINUTES` | `30` | Duración del access token. |
| `GENLAB_REFRESH_TOKEN_DAYS` | `7` | Duración del refresh token. |
| `GENLAB_CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos, separados por comas. |
| `GENLAB_DATA_DIR` | `./data` | Directorio para uploads, artefactos y logs. |
| `GENLAB_MAX_UPLOAD_MB` | `512` | Tamaño máximo de archivo cargado. |
| `GENLAB_TEST_SIZE` | `0.25` | Proporción Test predeterminada usada por rutas históricas. |
| `GENLAB_RANDOM_STATE` | `42` | Semilla predeterminada usada por rutas históricas. |
| `GENLAB_LEASE_TTL_SECONDS` | `86400` | Tiempo máximo de una reserva GPU sin worker válido. |
| `GENLAB_API_PREFIX` | `/api/v1` | Prefijo principal de la API. |
| `GENLAB_APP_NAME` | `GenLab M5GP API` | Nombre mostrado por FastAPI. |
| `GENLAB_APP_VERSION` | `1.0.0` | Versión mostrada por `/health` y `/about`. |
| `GENLAB_RELEASE_CHANNEL` | `stable` | Canal de publicación. |
| `GENLAB_GPU_COUNT` | vacío | Si se define, fuerza el número lógico de GPUs; si está vacío se utiliza `nvidia-smi`. |

Ejemplo de `.env` para desarrollo local:

```env
GENLAB_SECRET_KEY=reemplace-esta-clave-por-una-cadena-segura
GENLAB_DATABASE_URL=sqlite:///./data/genlab.db
GENLAB_CORS_ORIGINS=http://localhost:5173
GENLAB_ACCESS_TOKEN_MINUTES=30
GENLAB_REFRESH_TOKEN_DAYS=7
GENLAB_DATA_DIR=./data
GENLAB_APP_VERSION=1.0.0
GENLAB_RELEASE_CHANNEL=development
```

Puede generar una clave aleatoria con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 5.2 CORS

Para desarrollo con Vite:

```env
GENLAB_CORS_ORIGINS=http://localhost:5173
```

Para permitir varios orígenes:

```env
GENLAB_CORS_ORIGINS=http://localhost:5173,http://localhost:4173,https://genlab.example.org
```

Después de modificar `.env`, reinicie el backend.

### 5.3 Directorios de datos

Por defecto se utilizan:

```text
data/genlab.db
data/uploads/
data/artifacts/
data/logs/
```

`GENLAB_DATA_DIR` se convierte a una ruta absoluta al arrancar la API. Para evitar confusiones con rutas relativas se recomienda iniciar Uvicorn desde la raíz del repositorio.

---

## 6. Base de datos

### 6.1 SQLite

Es la opción predeterminada:

```env
GENLAB_DATABASE_URL=sqlite:///./data/genlab.db
```

Es adecuada para desarrollo y pruebas en una sola instalación.

### 6.2 PostgreSQL

Ejemplo:

```env
GENLAB_DATABASE_URL=postgresql+psycopg://genlab:password@localhost:5432/genlab
```

Instale primero:

```bash
python -m pip install -e 'backend[postgres]'
```

### 6.3 Creación del esquema

Al iniciar FastAPI se ejecuta:

```python
Base.metadata.create_all(engine)
```

Esto crea las tablas que no existan, incluidas las utilizadas para experimentos agrupados, corridas, predefinidos, lotes y reportes comparativos (`comparison_reports`). Actualmente el proyecto no utiliza Alembic para migraciones de esquema.

Antes de instalar una actualización sobre datos reales, respalde como mínimo:

```text
data/genlab.db
data/uploads/
data/artifacts/
data/logs/
```

En PostgreSQL realice además un respaldo de la base de datos con la herramienta administrativa correspondiente.

---

## 7. Ejecutar el backend

Desde la raíz del proyecto y con el entorno Conda que contiene CUDA/RAPIDS/cuML y M5GP activado:

```bash
conda activate <NOMBRE_ENTORNO>
```

Después ejecute el backend:

### Desarrollo

```bash
uvicorn genlab_api.main:app \
  --app-dir backend/src \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

### Ejecución estable

```bash
uvicorn genlab_api.main:app \
  --app-dir backend/src \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
```

Se recomienda mantener **un proceso Uvicorn** para el despliegue actual y dejar que GenLab gestione la concurrencia mediante reservas GPU y workers de corridas.

Verificación:

```bash
curl -sS http://localhost:8000/health | python -m json.tool
```

Respuesta esperada:

```json
{
  "status": "ok",
  "service": "GenLab M5GP API",
  "version": "1.0.0"
}
```

Documentación OpenAPI:

```text
http://localhost:8000/docs
```

---

## 8. Configurar y ejecutar el frontend

### 8.1 Dirección de la API

El frontend utiliza por defecto:

```text
http://localhost:8000/api/v1
```

Para cambiarla, cree `frontend/.env.local`:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

La dirección **debe incluir `/api/v1`**.

Ejemplo para un backend remoto:

```env
VITE_API_URL=http://192.168.1.50:8000/api/v1
```

El backend deberá autorizar en `GENLAB_CORS_ORIGINS` el origen desde el que se sirve el frontend.

### 8.2 Modo de desarrollo

En otra terminal:

```bash
cd frontend
npm ci --no-audit --no-fund
npm run dev -- --host 0.0.0.0
```

La dirección habitual es:

```text
http://localhost:5173
```

### 8.3 Compilación de producción

```bash
cd frontend
npm ci --no-audit --no-fund
npm run build
```

La salida se genera en:

```text
frontend/dist/
```

### 8.4 Probar la compilación

```bash
npm run preview -- --host 0.0.0.0
```

Vite suele utilizar el puerto `4173`. Si se prueba desde ese origen, agréguelo a CORS:

```env
GENLAB_CORS_ORIGINS=http://localhost:5173,http://localhost:4173
```

---

## 9. Arranque completo para desarrollo

### Terminal 1 — backend

Active primero el mismo entorno Conda que contiene CUDA/RAPIDS/cuML y M5GP:

```bash
cd /ruta/GenLab-m5gp
conda activate <NOMBRE_ENTORNO>

uvicorn genlab_api.main:app \
  --app-dir backend/src \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

### Terminal 2 — frontend

El frontend no depende del entorno Conda; utiliza Node.js/npm:

```bash
cd /ruta/GenLab-m5gp/frontend
npm run dev -- --host 0.0.0.0
```

Abra:

```text
http://localhost:5173
```

---

## 10. Perfiles de ejecución

Los perfiles del sistema son configuraciones operativas de conveniencia. No deben interpretarse como configuraciones científicamente óptimas para cualquier dataset.

### 10.1 Regresión simbólica

| Perfil | Método de evaluación | Generaciones | `GenesIndividuals` | `Individuals` | `maxRandomConstant` |
|---|---:|---:|---:|---:|---:|
| Mínima | 4 — Ridge | 15 | 64 | 256 | 1 |
| Estándar | 4 — Ridge | 40 | 64 | 512 | 1 |
| Intensiva | 4 — Ridge | 128 | 128 | 1024 | 1 |

El perfil **Estándar** es el predeterminado.

Los tres perfiles utilizan:

```json
[
  "+", "-", "*", "/",
  "sin", "cos", "tan", "tanh",
  "exp", "log", "Abs", "sqrt"
]
```

Parámetros evolutivos comunes:

```json
{
  "mutationProb": 0.10,
  "mutationDeleteRateProb": 0.05,
  "sizeTournament": 0.15,
  "genOperatorProb": 0.45,
  "genVariableProb": 0.40,
  "genConstantProb": 0.10,
  "genNoopProb": 0.001,
  "log": 1,
  "verbose": 1
}
```

### 10.2 Clasificación

Se conserva un perfil **Clasificación estándar** independiente. Los tres perfiles anteriores usan Ridge y, por tanto, son perfiles de regresión.

### 10.3 Parámetros personalizados

La opción **Parámetros** permite:

- revisar perfiles del sistema;
- copiar un perfil;
- construir una configuración desde un formulario;
- generar automáticamente el JSON solicitado por M5GP;
- editar el JSON manualmente;
- guardar predefinidos personalizados;
- definir un predefinido como predeterminado.

---

## 11. Validación Train/Test

GenLab realiza la partición externa del dataset antes de llamar a M5GP.

### 11.1 Holdout

Valores predeterminados:

```text
strategy     = holdout
train_size   = 0.75
test_size    = 0.25
random_state = 42
shuffle      = true
```

El worker construye `X_train`, `X_test`, `y_train` y `y_test`. M5GP recibe en `fit()` solamente el conjunto de entrenamiento y se evalúa posteriormente sobre Train y Test.

Cuando existen varias repeticiones, la semilla se deriva de la semilla base y del índice de repetición, permitiendo particiones diferentes pero reproducibles.

### 11.2 K-fold

En regresión se utiliza `KFold` y en clasificación `StratifiedKFold`.

Cada fold se materializa como una corrida independiente. Por ejemplo:

```text
10 repeticiones × 5 folds = 50 entrenamientos de M5GP
```

`folds` sólo tiene efecto cuando `strategy = kfold`. En Holdout puede existir en la configuración almacenada como valor disponible, pero no participa en la división de esa corrida.

---

## 12. Administración de GPUs y cola

GenLab detecta GPUs mediante `nvidia-smi`. Si `GENLAB_GPU_COUNT` está definido, utiliza ese número lógico en lugar de consultar el hardware.

La política actual es:

```text
1 corrida activa por GPU
```

Las corridas generadas por experimentos agrupados y lotes entran a una cola con estado `queued`. Cuando una corrida finaliza o falla, su GPU se libera y el backend intenta despachar la siguiente corrida pendiente.

La API histórica `/experiments/{id}/run` se conserva por compatibilidad y puede seguir respondiendo `409` cuando se solicita una ejecución directa sin GPU disponible. El flujo nuevo de experimentos agrupados utiliza la cola.

---

## 13. Seguimiento de avance

Cada corrida mantiene información de progreso:

- etapa actual;
- porcentaje;
- generación actual;
- generaciones totales;
- historial de ajuste por generación;
- mensaje descriptivo.

Durante `model.fit()` el backend lee el avance generacional del log de M5GP y actualiza la corrida. La interfaz consulta periódicamente esta información y muestra:

- avance global del experimento;
- progreso de cada corrida;
- porcentaje;
- generación actual/total;
- estado de la corrida.

El porcentaje representa avance del flujo y de generaciones; **no es una estimación lineal del tiempo restante**.

---

## 14. Resultados de regresión

Para cada corrida de regresión se registran por separado métricas de Train y Test:

```text
MSE
RMSE
MAE
R²
```

También se almacenan métricas de ejecución:

```text
Model Size
Training Time (s)
Process Time (s)
```

`Training Time` corresponde al tiempo de pared medido alrededor de `model.fit()`. `Model Size` se obtiene de la complejidad reportada por el modelo M5GP.

### 14.1 Resultados agregados

Para cada métrica se calculan:

```text
media
desviación estándar poblacional
mínimo
máximo
número de corridas válidas
```

Se muestran tanto a nivel global del experimento como por dataset.

### 14.2 Resultados individuales

En cada dataset puede abrirse el detalle de cada corrida. El resultado individual conserva:

- dataset;
- repetición y fold;
- semilla;
- estado y progreso;
- métricas Train/Test;
- Model Size;
- Training Time;
- modelo simbólico;
- historial por generación;
- predicciones;
- artefactos y log.

### 14.3 Gráficas tipo SRBench

Los experimentos de regresión muestran gráficas comparativas para:

```text
R² Test
RMSE Test
Model Size
Training Time (s)
```

Para cada dataset se representan las corridas individuales junto con su resumen. `Model Size` y `Training Time` utilizan escala logarítmica cuando corresponde.

También se incluye una nube de puntos observado contra predicho con línea `y = x`. La correlación de Pearson se calcula utilizando todos los puntos válidos; el muestreo se aplica únicamente a la cantidad de puntos enviados a la visualización cuando el experimento es grande.

---

## 15. Resultados de clasificación

Las métricas principales Train/Test son:

```text
Accuracy
F1 macro
Precision macro
Recall macro
```

También se generan, cuando corresponde:

```text
classification_report.json
confusion_matrix.json
```

---

## 16. Exportación de resultados

Desde la vista de un experimento pueden exportarse:

- todos los resultados del experimento;
- los resultados de un dataset específico.

Formatos:

```text
JSON
Excel .xlsx
```

Endpoints:

```text
GET /api/v1/experiment-groups/{id}/export/json
GET /api/v1/experiment-groups/{id}/export/xlsx
```

Para limitar la exportación a un dataset:

```text
?dataset_id=<dataset-id>
```

El libro `.xlsx` contiene las hojas:

```text
Experimento
Resultados agregados
Corridas
```

La exportación Excel se genera directamente como OpenXML y no requiere instalar una biblioteca adicional de Excel en el backend.

---


## 17. Comparativos y reportes de experimentos

La opción **Comparativos** permite integrar resultados de dos o más experimentos del mismo tipo sin modificar las corridas ni los artefactos originales. Un reporte puede contener únicamente experimentos de **regresión** o únicamente experimentos de **clasificación**.

Cada reporte guarda una **instantánea del análisis** junto con los identificadores de los experimentos utilizados, la métrica principal y el nivel de significancia `α`. Esto permite consultar posteriormente el mismo resultado. Si terminan nuevas corridas o cambian los resultados de un experimento, el botón **Actualizar análisis** vuelve a calcular explícitamente la instantánea; el reporte no cambia de forma silenciosa.

### 17.1 Selección de experimentos

Desde `/comparisons` se selecciona:

- tipo de tarea: regresión o clasificación;
- dos o más experimentos del mismo tipo;
- métrica principal;
- nivel `α`, por defecto `0.05`;
- nombre y descripción del reporte.

Los experimentos pueden utilizar configuraciones diferentes. Esto permite estudiar el efecto de parámetros como:

```text
generations
Individuals
GenesIndividuals
mutationProb
mutationDeleteRateProb
sizeTournament
genOperatorProb
genVariableProb
genConstantProb
genNoopProb
maxRandomConstant
evaluationMethod
validation.train_size
validation.test_size
runs_per_dataset
```

El reporte identifica automáticamente los parámetros que realmente cambian entre los experimentos seleccionados.

### 17.2 Métricas disponibles

Para regresión pueden utilizarse como métrica principal:

```text
R² Test
RMSE Test
MAE Test
Model Size
Training Time
```

Para clasificación:

```text
Accuracy Test
F1 macro Test
Precision macro Test
Recall macro Test
Model Size
Training Time
```

### 17.3 Visualizaciones tipo SRBench

El comparativo genera gráficas de resumen por experimento/configuración. En regresión se muestran de forma predeterminada:

```text
R² Test
RMSE Test
Model Size
Training Time (s)
```

En clasificación:

```text
Accuracy Test
F1 macro Test
Model Size
Training Time (s)
```

Cuando los experimentos comparten datasets, los rankings y gráficas de desempeño utilizan únicamente ese conjunto común para evitar comparar configuraciones sobre problemas distintos. Cada gráfica conserva los valores de las corridas individuales y muestra media y rango mínimo–máximo. `Model Size` y `Training Time` se representan en escala logarítmica cuando corresponde.

El reporte agrega además un **boxplot** de la métrica principal para visualizar mediana, cuartiles, dispersión y extremos entre corridas.

> Cuando se comparan RMSE o MAE de datasets con escalas objetivo diferentes, la comparación global debe interpretarse con precaución. En ese caso conviene analizar los resultados por dataset o normalizar previamente la métrica.

### 17.4 Matriz de Wilcoxon

GenLab puede generar una matriz triangular similar a la utilizada en análisis de benchmarks. Para cada par de experimentos se aplica la prueba de **Wilcoxon de rangos con signo** sobre las medias obtenidas en los **datasets comunes**.

El procedimiento es:

1. para cada experimento se calcula la media de la métrica seleccionada en cada dataset;
2. se conservan únicamente datasets presentes en ambos experimentos del par;
3. se ejecuta Wilcoxon pareado y bilateral;
4. los p-valores de todos los pares se corrigen mediante **Holm-Bonferroni**;
5. la matriz clasifica la evidencia utilizando `p_adj` respecto a `α`:

```text
p_adj < 10^-3 · α
p_adj < 10^-2 · α
p_adj < 10^-1 · α
p_adj < α
no significativo
```

La matriz informa además el número de datasets emparejados y cuál experimento presenta mejor media considerando la dirección de la métrica. Si existen menos de cinco datasets comunes, el contraste se marca como **exploratorio**. El resultado estadístico no debe interpretarse aisladamente de magnitud del efecto, dispersión y diseño experimental.

### 17.5 Impacto de parámetros

Para parámetros numéricos que cambian entre los experimentos, la interfaz permite seleccionar un parámetro y una métrica y genera un diagrama de dispersión configuración–resultado. También calcula la correlación de **Spearman (`ρ`)** y su p-valor cuando existen al menos tres configuraciones válidas.

Esta sección ayuda a explorar asociaciones como:

```text
generations        vs R² Test
Individuals        vs RMSE Test
GenesIndividuals   vs Model Size
Individuals        vs Training Time
```

La correlación se presenta como herramienta exploratoria; no implica una relación causal entre el parámetro y el resultado.

### 17.6 Análisis de costo computacional

El reporte incluye un diagrama costo–desempeño con la métrica principal frente a `Training Time` y tres gráficas de escalamiento similares a las utilizadas en SRBench:

```text
Training Time vs Dataset Nsamples
Training Time vs Dataset Nfeatures
Training Time vs Dataset Npoints
```

donde:

```text
Nsamples  = número de filas del dataset
Nfeatures = número de variables predictoras
Npoints   = Nsamples × Nfeatures
```

Los ejes de tamaño y tiempo se representan en escala logarítmica. Para cada punto se conserva media, desviación estándar y rango de tiempos de las corridas disponibles.

### 17.7 Guardar, actualizar y exportar

Los reportes se almacenan en la tabla `comparison_reports`. Al iniciar FastAPI, `Base.metadata.create_all()` crea esta tabla cuando aún no existe. Como en cualquier actualización de esquema, se recomienda respaldar previamente la base de datos y `data/`.

Rutas API:

```text
POST   /api/v1/comparison-reports/preview
POST   /api/v1/comparison-reports
GET    /api/v1/comparison-reports
GET    /api/v1/comparison-reports/{id}
POST   /api/v1/comparison-reports/{id}/refresh
GET    /api/v1/comparison-reports/{id}/export/json
GET    /api/v1/comparison-reports/{id}/export/xlsx
DELETE /api/v1/comparison-reports/{id}
```

La exportación Excel contiene hojas para:

```text
Reporte
Experimentos
Rankings
Datasets
Wilcoxon
Parametros
Computacional
```

Los reportes guardan una instantánea de resultados. Si posteriormente se elimina uno de los experimentos originales, la instantánea guardada continúa disponible, aunque no podrá recalcularse hasta que todos los experimentos referenciados vuelvan a existir.

---

## 18. Artefactos de cada corrida

Una corrida completada puede generar:

```text
model.joblib
predictions.csv
metrics.json
model.txt
generation_history.json
test_results.json
experiment.json
```

En clasificación también:

```text
classification_report.json
confusion_matrix.json
```

`metrics.json` contiene métricas Train/Test, validación y métricas de ejecución. `experiment.json` conserva la información necesaria para identificar la configuración efectiva de la corrida.

Las corridas históricas creadas antes de incorporar `Model Size` y `Training Time` como métricas estructuradas pueden mostrar esos campos vacíos. Para obtenerlos de forma homogénea deben volver a ejecutarse con la versión actual.

---

## 19. API principal

### Compatibilidad histórica de ejecuciones

```text
/api/v1/experiments
```

### Corridas

```text
GET    /api/v1/runs
GET    /api/v1/runs/{id}
POST   /api/v1/runs/{id}/rerun
POST   /api/v1/runs/{id}/cancel
DELETE /api/v1/runs/{id}
GET    /api/v1/runs/{id}/generation-history
GET    /api/v1/runs/{id}/test-results
GET    /api/v1/runs/{id}/artifacts/{filename}
```

### Experimentos agrupados

```text
POST   /api/v1/experiment-groups
GET    /api/v1/experiment-groups
GET    /api/v1/experiment-groups/{id}
POST   /api/v1/experiment-groups/{id}/run
POST   /api/v1/experiment-groups/{id}/dispatch
GET    /api/v1/experiment-groups/{id}/results
GET    /api/v1/experiment-groups/{id}/export/json
GET    /api/v1/experiment-groups/{id}/export/xlsx
DELETE /api/v1/experiment-groups/{id}
```

### Predefinidos

```text
GET    /api/v1/parameter-presets
POST   /api/v1/parameter-presets
PUT    /api/v1/parameter-presets/{id}
DELETE /api/v1/parameter-presets/{id}
```

### Lotes

```text
POST /api/v1/batches
GET  /api/v1/batches
GET  /api/v1/batches/{id}
POST /api/v1/batches/{id}/run
```

### Comparativos y reportes

```text
POST   /api/v1/comparison-reports/preview
POST   /api/v1/comparison-reports
GET    /api/v1/comparison-reports
GET    /api/v1/comparison-reports/{id}
POST   /api/v1/comparison-reports/{id}/refresh
GET    /api/v1/comparison-reports/{id}/export/json
GET    /api/v1/comparison-reports/{id}/export/xlsx
DELETE /api/v1/comparison-reports/{id}
```

La especificación completa y actual del servidor siempre puede consultarse en:

```text
http://localhost:8000/docs
```

---

## 20. Rutas principales del frontend

```text
/                       Panel principal
/datasets               Datasets
/experiments            Experimentos
/experiments/new        Nuevo experimento
/experiments/{id}       Resultados agregados e individuales
/runs                   Corridas
/runs/{id}              Detalle de corrida
/batches                Lotes
/parameters             Perfiles y parámetros avanzados
/comparisons             Comparativos y reportes
/comparisons/{id}        Detalle de un comparativo guardado
/resources              Recursos GPU
/about                  Información del proyecto
```

---

## 21. Flujo de uso recomendado

1. Registrar o iniciar sesión con un usuario.
2. Cargar uno o varios datasets CSV/TSV.
3. Revisar su vista previa y seleccionar la variable objetivo.
4. Crear un experimento.
5. Seleccionar regresión o clasificación.
6. Seleccionar un perfil o construir una configuración personalizada.
7. Seleccionar uno o varios datasets.
8. Definir el número de corridas por dataset.
9. Configurar Holdout o K-fold.
10. Guardar o ejecutar el experimento.
11. Supervisar el avance global y el progreso de cada corrida.
12. Revisar resultados agregados por dataset.
13. Abrir las corridas individuales cuando se requiera trazabilidad.
14. Exportar resultados a JSON o `.xlsx`.
15. Abrir **Comparativos** para seleccionar experimentos del mismo tipo, analizar diferencias de parámetros, revisar Wilcoxon y estudiar costo computacional.
16. Guardar y exportar el reporte comparativo cuando se requiera conservar el análisis.
17. Utilizar Lotes cuando deban ejecutarse varios experimentos guardados.

---

## 22. Verificación y pruebas

### 22.1 Verificar estructura

Después de instalar el código M5GP:

```bash
python tools/verify_structure.py --require-source
```

Sin exigir que el motor ya esté instalado:

```bash
python tools/verify_structure.py
```

### 22.2 Comprobar sintaxis Python

```bash
python -m compileall -q backend/src core/src
```

### 22.3 Pruebas del backend

```bash
python -m pip install -e 'backend[test]'
pytest -q backend/tests
```

Para ejecutar únicamente las pruebas asociadas con experimentos agrupados y resultados:

```bash
pytest -q \
  backend/tests/test_experiment_groups.py \
  backend/tests/test_results_exports.py \
  backend/tests/test_comparison_reports.py
```

### 22.4 Compilar el frontend

```bash
cd frontend
npm ci --no-audit --no-fund
npm run build
```

### 22.5 Prueba directa del motor M5GP

Si se instalaron los tests originales:

```bash
cd core/tests
python m5gp_Test.py
```

Esta prueba requiere el entorno GPU/CUDA/RAPIDS/cuML compatible con M5GP.

---

## 23. Docker Compose

Antes de construir las imágenes, el Dockerfile del backend exige que el código fuente original de M5GP esté instalado localmente:

```bash
python tools/install_core_from_github.py --ref main
```

Después:

```bash
docker compose up --build
```

La configuración actual levanta:

- PostgreSQL;
- API en `http://localhost:8000`;
- frontend Nginx en `http://localhost:5173`.

### Consideración importante sobre GPU

El `backend/Dockerfile` incluido parte de `python:3.12-slim` e instala los paquetes Python de `core` y `backend`, pero **no instala por sí mismo un entorno completo CUDA/RAPIDS/cuML**. Por tanto, `docker compose up --build` no debe interpretarse como una imagen GPU final lista para ejecutar M5GP en cualquier equipo.

Para ejecutar M5GP dentro del contenedor se requiere:

- NVIDIA Container Toolkit en el host;
- acceso de Docker a las GPUs;
- una imagen/backend que incluya las versiones compatibles de CUDA, RAPIDS/cuML y demás dependencias requeridas por M5GP.

La sección `deploy.resources.reservations.devices` del Compose solicita GPUs, pero la disponibilidad del dispositivo no sustituye la instalación del entorno de software GPU.

También deben cambiarse las credenciales de PostgreSQL y `GENLAB_SECRET_KEY` incluidas como valores de desarrollo en `docker-compose.yml` antes de un despliegue real.

---

## 24. Integración con SRBench

Para instalar M5GP en una copia de SRBench:

```bash
bash integrations/srbench/install.sh /ruta/srbench --ref main
```

Para fijar una versión reproducible:

```bash
bash integrations/srbench/install.sh /ruta/srbench --ref <tag-o-commit>
```

El instalador crea el adaptador y copia el código M5GP requerido dentro de la estructura esperada por SRBench. No modifica el motor utilizado por la instalación principal de GenLab.

---

## 25. Actualizar una instalación existente

Antes de actualizar:

1. detener backend y frontend;
2. respaldar la base y los directorios `data/`;
3. conservar el commit/tag de M5GP usado en experimentos que deban reproducirse.

Después de actualizar el código de GenLab, active primero el entorno Conda utilizado por M5GP:

```bash
conda activate <NOMBRE_ENTORNO>
git pull
python tools/install_core_from_github.py --ref main --copy-tests
python -m pip install -e core
python -m pip install -e 'backend[test]'
python -m compileall -q backend/src
python tools/verify_structure.py --require-source
pytest -q backend/tests
```

Frontend:

```bash
cd frontend
rm -rf dist node_modules/.vite
npm ci --no-audit --no-fund
npm run build
```

Después reinicie ambos servicios.

Si la actualización se distribuye como paquete incremental con `apply_update.py`, utilice las instrucciones incluidas con ese paquete antes de ejecutar los pasos de verificación anteriores.

---

## 26. Problemas frecuentes

### `source .venv/bin/activate` indica que el archivo no existe

La instalación recomendada actual utiliza el entorno Conda que ya contiene CUDA, RAPIDS/cuML y M5GP. No es necesario crear `.venv`.

Active el entorno correcto:

```bash
conda env list
conda activate <NOMBRE_ENTORNO>
which python
```

Si existe un `.venv` activo de una prueba anterior, salga de él antes de activar Conda:

```bash
deactivate
conda activate <NOMBRE_ENTORNO>
```

### El backend utiliza un Python distinto al de Conda

Compruebe:

```bash
which python
python --version
which uvicorn
```

Los ejecutables deben pertenecer al entorno Conda activo. Si `uvicorn` no está instalado en ese entorno, reinstale el backend con:

```bash
python -m pip install -e 'backend[test]'
```

### La API no inicia

Compruebe:

```bash
python -m compileall -q backend/src
python tools/verify_structure.py
```

Revise también que `.env` tenga una URL de base de datos válida y que el entorno virtual correcto esté activo.

### M5GP no inicia o aparecen errores de `cupy`, `numba`, `cuml` o CUDA

La instalación editable de `core` no instala automáticamente el stack GPU completo. Compruebe primero:

```bash
nvidia-smi
```

Después verifique que el entorno Python utilizado por el backend tenga instaladas las dependencias GPU compatibles con M5GP.

### No aparecen GPUs en GenLab

Compruebe que `nvidia-smi` funcione desde el mismo usuario que ejecuta el backend.

Para una prueba controlada puede establecer explícitamente:

```env
GENLAB_GPU_COUNT=1
```

Esto fuerza el inventario lógico, pero **no crea una GPU ni instala CUDA**; M5GP seguirá necesitando acceso real al dispositivo.

### `Failed to fetch` o error CORS

Compruebe:

```bash
curl -sS http://localhost:8000/health
```

Revise `frontend/.env.local` y `GENLAB_CORS_ORIGINS`.

### El frontend queda en blanco después de actualizar

```bash
cd frontend
rm -rf dist node_modules/.vite
npm ci --no-audit --no-fund
npm run build
npm run dev -- --host 0.0.0.0 --force
```

Realice después una recarga forzada del navegador.

### La compilación npm falla

Realice una instalación limpia:

```bash
cd frontend
rm -rf node_modules dist node_modules/.vite
npm cache verify
npm ci --registry=https://registry.npmjs.org/ --no-audit --no-fund
npm run build
```

### Un experimento agrupado permanece en `queued`

Compruebe la opción **Recursos GPU** y verifique que exista al menos una GPU disponible y que el worker pueda iniciar M5GP. Las corridas pendientes se despachan cuando se libera un dispositivo.

### Una corrida antigua no muestra Model Size o Training Time

Esos campos se almacenan de forma estructurada en las corridas generadas con la versión actual. Una corrida histórica puede no contenerlos. Para obtenerlos debe volver a ejecutarse.

---

## 27. Seguridad y despliegue

Para un despliegue fuera de desarrollo:

- cambie `GENLAB_SECRET_KEY`;
- utilice contraseñas seguras para PostgreSQL;
- limite `GENLAB_CORS_ORIGINS` a dominios autorizados;
- publique la API y el frontend detrás de HTTPS;
- respalde periódicamente base de datos, uploads y artefactos;
- no publique `.env` ni archivos de datos generados;
- fije el commit/tag del motor M5GP para experimentos reproducibles.

Antes de confirmar cambios al repositorio:

```bash
python tools/check_github_repository.py
```

El comando comprueba que archivos sensibles, artefactos y la copia descargada del motor M5GP no estén siendo incluidos accidentalmente en Git.

---

## 28. Consideraciones para experimentación científica

Para conservar reproducibilidad se recomienda registrar en cada estudio:

- commit o tag de M5GP 2.0;
- versión de GenLab;
- dataset y variable objetivo;
- perfil o JSON completo de parámetros;
- número de corridas;
- estrategia Holdout/K-fold;
- proporción Train/Test o número de folds;
- semillas utilizadas;
- hardware GPU;
- versiones relevantes de CUDA/RAPIDS/cuML;
- métricas Train y Test;
- Model Size y Training Time cuando formen parte del análisis.

No debe interpretarse una única mejor corrida como resultado representativo del algoritmo. Para múltiples corridas conviene analizar al menos la media, dispersión y comportamiento por dataset, conservando siempre los resultados individuales.

---

## 29. Referencias del proyecto

La información de versión, autoría, instituciones, referencias científicas y enlaces del proyecto puede consultarse también desde:

```text
GET /api/v1/about
```

Ejemplo:

```bash
curl -sS http://localhost:8000/api/v1/about | python -m json.tool
```

Los términos de uso, modificación y redistribución deben consultarse en el archivo `LICENSE` del repositorio.
