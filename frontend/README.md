# Frontend GenLab M5GP

Aplicación React/Vite inspirada en la organización visual de plataformas de ciencia de datos: navegación lateral, paneles de recursos, datasets y ejecuciones. El formulario de datasets acepta archivos `.csv` y `.tsv`.

## Desarrollo

```bash
npm install
npm run dev
```

La sesión usa un token de acceso y un refresh token rotativo. El cliente renueva automáticamente la sesión al recibir un `401`.

## Funciones de experimentos

En el detalle de cada experimento se puede:

- consultar la configuración inicial y el dataset utilizado;
- observar una barra de progreso y la generación actual;
- volver a ejecutar el experimento con los mismos parámetros;
- eliminarlo cuando no esté activo;
- descargar artefactos después de finalizar correctamente.

La tabla del historial también permite eliminar experimentos inactivos.


## Selección del tipo de experimento

El formulario permite elegir **Regresión simbólica** o **Clasificación**. Cada
opción presenta únicamente los parámetros correspondientes al estimador
original. En clasificación se puede seleccionar Logistic Regression, SVC,
Random Forest o KNN, junto con métrica y validación cruzada.

## Gráficas de regresión

Cuando una ejecución de regresión tiene historial disponible, el detalle muestra:

1. `Train Fit` por generación;
2. valores reales frente a predicciones del conjunto de prueba.

Las gráficas se dibujan con SVG, sin incorporar una dependencia adicional. Los
datos provienen del endpoint `/experiments/{id}/visualization`. La muestra
visual está limitada a 300 puntos, pero `predictions.csv` contiene todos los
registros del conjunto de prueba.

## Artefactos de clasificación

Además de los artefactos comunes, la interfaz ofrece la descarga de
`classification_report.json` y `confusion_matrix.json` cuando la tarea es de
clasificación.

## Pantalla en blanco al abrir el frontend

Si `http://localhost:5173/` muestra una página completamente en blanco, el
navegador puede conservar una sesión de una versión anterior en
`localStorage`. La versión actual valida y elimina automáticamente valores de
sesión inválidos antes de iniciar React.

Después de actualizar el código, reconstruya y reinicie:

```bash
cd frontend
rm -rf node_modules dist
npm ci
npm run dev -- --host 0.0.0.0
```

Realice una recarga forzada con `Ctrl+Shift+R`. Como limpieza manual inmediata,
abra la consola del navegador y ejecute:

```javascript
localStorage.removeItem('genlab_tokens');
location.reload();
```

Si ocurre otro error de renderizado, la aplicación muestra ahora una pantalla
de diagnóstico en lugar de dejar el documento vacío.


## Previsualización de datasets

En la página **Datasets**, el botón **Previsualizar** consulta las primeras 20
filas del CSV o TSV seleccionado. La interfaz muestra el catálogo de columnas,
sus tipos de datos y una tabla desplazable. Los nombres mostrados son los mismos
que estarán disponibles como variable objetivo en **Nuevo experimento**.

## Idiomas de la interfaz

La interfaz incluye un selector fijo en la esquina superior derecha para cambiar entre **Español** e **English**. La selección se conserva en `localStorage` con la clave `genlab_language` y se aplica a navegación, formularios, tablas, estados, parámetros, artefactos, gráficas, mensajes de progreso y pantallas de error.

En el formulario de acceso, el botón con icono de ojo permite mostrar u ocultar la contraseña capturada sin modificar su valor.

## Vista Acerca de

La opción **Acerca de / About** está disponible en el menú lateral. Consume
`GET /api/v1/about`, adapta los textos al idioma global de la interfaz y ofrece
enlaces para consultar las publicaciones, abrir el repositorio y descargar el
código fuente.
