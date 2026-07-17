# Arquitectura GenLab M5GP

```text
Scripts Python ───────────────────────┐
Backend/API (proceso por GPU) ────────┼──> core/src/m5gp (motor original)
                                      │
Frontend React ──REST/JWT──> Backend ─┘

integrations/srbench/install.sh
        └── GitHub M5GP ──> SRBench/experiment/methods/src/m5gp
```

## Fuente única en GenLab

Solo `core/src/m5gp` contiene el motor. La integración SRBench contiene un
adaptador y un instalador, no código fuente duplicado.

## Separación de responsabilidades

- El motor original conserva todo el ciclo evolutivo.
- `core/src/m5gp/runtime.py` solo enumera GPUs para la API.
- El backend administra usuarios, JWT, datasets, experimentos y reservas GPU.
- El worker establece `CUDA_VISIBLE_DEVICES` antes de importar M5GP, de modo que
  la GPU física reservada aparezca como dispositivo lógico 0 y se preserve
  `cudaSetup(0)`.
- El frontend únicamente consume la API.
- SRBench recibe su propia copia desde el repositorio Git porque pertenece a
  otro proyecto y a su estructura `experiment/methods/src`.
