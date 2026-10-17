# Paquete API

- `routers/`: endpoints HTTP, incluidas corridas, experimentos agrupados, predefinidos y lotes.
- `services/`: archivos, GPU, ejecución histórica y servicios de agregación/cola.
- `models.py`: entidades históricas; `Experiment` representa una corrida en el modelo nuevo.
- `lab_models.py`: tablas incrementales de experimentos, asociaciones, predefinidos y lotes.
- `schemas.py`: contratos históricos.
- `lab_schemas.py`: contratos de la nueva capa experimental.
- `worker.py`: proceso que ejecuta una corrida M5GP en una GPU reservada.
