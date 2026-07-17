# Scripts locales ejecutables

El proyecto incluye `m5gp_Test.py` y reserva todos los nombres de pruebas del
repositorio original. Para instalar las versiones exactas desde el mismo commit
que el motor:

```bash
cd /ruta/GenLab_M5GP
python tools/install_core_from_github.py --ref main --copy-tests
```

Después se ejecutan directamente, sin `python -m` y sin autenticación:

```bash
cd core/tests
python m5gp_Test.py
python m5gp_Test2.py
python m5gp_Test_Classifier.py
python m5gp_Digen.py
python clasificacion_diabetes.py
```

`_bootstrap.py` únicamente agrega `core/src` al camino de importación. No
modifica parámetros, datasets, escalamiento ni el flujo experimental.
