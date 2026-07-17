# Instalación de M5GP 2.0 en SRBench v2

Esta carpeta contiene **solo** el adaptador y las herramientas de instalación.
No guarda otra copia del motor M5GP.

## Archivos

- `m5gpRegressor.py`: adaptador que SRBench copia a `experiment/methods`.
- `install_into_srbench.py`: clona el repositorio Git de M5GP y copia sus
  módulos a `experiment/methods/src/m5gp`.
- `install.sh`: envoltura de línea de comandos.
- `verify_install.py`: comprueba archivos y contrato `est/model/complexity`.
- `environment.yml`: entorno RAPIDS/CUDA recomendado.
- `requirements.txt`: dependencias Python complementarias.

## Instalación

```bash
cd /ruta/GenLab_M5GP
bash integrations/srbench/install.sh /ruta/srbench --ref main
```

También puede fijarse un tag o commit reproducible:

```bash
python integrations/srbench/install_into_srbench.py \
  --srbench-root /ruta/srbench \
  --ref <tag-o-commit> \
  --force
```

El resultado es:

```text
srbench/experiment/methods/
├── m5gpRegressor.py
└── src/
    ├── __init__.py
    └── m5gp/
        ├── __init__.py
        ├── SOURCE_INFO.json
        ├── m5gp.py
        ├── m5gpGlobals.py
        ├── m5gpCudaMethods.py
        ├── m5gpCumlMethods.py
        ├── m5gpCumlMethods2.py
        ├── m5gpMod1.py
        ├── m5gpMod2.py
        ├── m5gpMod3.py
        └── m5gpSymBuilder.py
```

Los archivos del algoritmo se copian directamente del checkout Git. No se
reescriben `m5gp.py`, `compute_individuals`, los kernels CUDA ni el ciclo
evolutivo.
