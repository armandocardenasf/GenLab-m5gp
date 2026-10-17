# Frontend GenLab M5GP

Aplicación React/Vite para datasets, experimentos agrupados, corridas, parámetros avanzados, lotes y recursos GPU.

## Nuevas vistas

```text
/experiments            Experimentos agrupados
/experiments/new        Configuración de experimento
/experiments/{id}       Resultados globales y corridas individuales
/runs                   Corridas
/runs/{id}              Resultados de una corrida
/batches                Lotes de experimentos
/parameters             Predefinidos y parámetros avanzados
```

La vista **Nuevo experimento** permite varios datasets, varias corridas por dataset y Holdout/K-fold. El experimento puede guardarse sin ejecutar para incluirlo posteriormente en un lote.

## Perfiles

La interfaz consume `/parameter-presets` y ofrece Rápida, Estándar e Intensiva. Los predefinidos personalizados se editan como JSON para conservar acceso a todos los parámetros del constructor M5GP.

## Resultados

El detalle de experimento muestra estadísticos agregados y resultados por dataset. Para regresión se incluye una nube de puntos observado/predicho y la correlación de Pearson.

El detalle de corrida conserva historial por generación, métricas Train/Test, modelo simbólico, artefactos, comparación real/predicción y nube de puntos.

## Desarrollo

```bash
npm ci
npm run dev
```

Validación:

```bash
npm run build
```

