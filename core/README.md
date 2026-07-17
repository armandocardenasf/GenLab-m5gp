# Core M5GP

`core/src/m5gp` es la única ubicación del motor. El paquete expone:

```python
from m5gp import m5gpRegressor, m5gpClassifier
```

## Preparación

```bash
cd /ruta/GenLab_M5GP
python tools/install_core_from_github.py --ref main --copy-tests
python -m pip install -e core
```

## Pruebas directas

```bash
cd core/tests
python m5gp_Test.py
python m5gp_Test2.py
python m5gp_Test_Classifier.py
```

Los scripts conservan la lógica del repositorio original; el instalador solo
agrega un bloque de ruta para que puedan ejecutarse desde `core/tests`.
