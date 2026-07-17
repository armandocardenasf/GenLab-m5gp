# Única fuente M5GP dentro de GenLab

`core/src/m5gp` es la única ubicación del motor utilizado por ejecución local,
backend y API. No existe `core/methods/src`.

Instale la versión original desde GitHub:

```bash
python tools/install_core_from_github.py --ref main --copy-tests
```

El instalador copia sin reescribir la lógica:

- `m5gp.py`
- `m5gpGlobals.py`
- `m5gpCudaMethods.py`
- `m5gpCumlMethods.py`
- `m5gpCumlMethods2.py`
- `m5gpMod1.py`
- `m5gpMod2.py`
- `m5gpMod3.py`
- `m5gpSymBuilder.py`

`runtime.py` es un auxiliar exclusivo de la API para listar GPUs; no participa
en inicialización, `compute_individuals`, evaluación ni ciclo evolutivo.

El adaptador `m5gpRegressor.py` se mantiene solamente en
`integrations/srbench`, porque SRBench lo instala en `experiment/methods`.
