# Publicación de GenLab M5GP en GitHub

Repositorio objetivo:

```text
https://github.com/armandocardenasf/GenLab-m5gp
```

## Contenido que sí se publica

- Backend y API REST.
- Frontend React/Vite.
- Autenticación JWT y sesiones.
- Administración de datasets, experimentos, GPU y artefactos.
- Integración e instalador de SRBench.
- Instalador del núcleo M5GP 2.0.
- Pruebas propias, documentación, Docker y archivos de entorno.

## Contenido que no se publica

Los módulos originales de M5GP 2.0 no forman parte de este repositorio:

```text
core/src/m5gp/m5gp.py
core/src/m5gp/m5gpGlobals.py
core/src/m5gp/m5gpCudaMethods.py
core/src/m5gp/m5gpCumlMethods.py
core/src/m5gp/m5gpCumlMethods2.py
core/src/m5gp/m5gpMod1.py
core/src/m5gp/m5gpMod2.py
core/src/m5gp/m5gpMod3.py
core/src/m5gp/m5gpSymBuilder.py
```

Se descargan después de clonar GenLab:

```bash
python tools/install_core_from_github.py --ref main
```

El archivo `.gitignore` impide agregarlos accidentalmente al repositorio GenLab.

## Publicar desde Visual Studio Code

1. Cree en GitHub un repositorio vacío llamado `GenLab-m5gp`. No agregue README, `.gitignore` ni licencia desde la página de creación, porque el proyecto ya contiene estos archivos.
2. Abra `GenLab-m5gp.code-workspace` en VS Code.
3. Abra **Source Control** con `Ctrl+Shift+G`.
4. Seleccione **Initialize Repository** si la carpeta todavía no contiene `.git`.
5. Revise los archivos pendientes. No deben aparecer `.env`, `data/`, `node_modules/` ni los módulos originales de M5GP.
6. Escriba el mensaje `Initial GenLab M5GP release` y seleccione **Commit**.
7. Abra la paleta con `Ctrl+Shift+P` y ejecute **Git: Add Remote**.
8. Use como remoto:

   ```text
   https://github.com/armandocardenasf/GenLab-m5gp.git
   ```

9. Ejecute **Git: Push** o seleccione **Publish Branch**.

## Publicar desde la terminal integrada de VS Code

```bash
cd /ruta/GenLab-m5gp
python tools/check_github_repository.py
git init -b main
git add .
python tools/check_github_repository.py
git commit -m "Initial GenLab M5GP release"
git remote add origin https://github.com/armandocardenasf/GenLab-m5gp.git
git push -u origin main
```

También puede usar:

```bash
bash tools/publish_to_github.sh
```

## Instalar el núcleo después de clonar

```bash
git clone https://github.com/armandocardenasf/GenLab-m5gp.git
cd GenLab-m5gp
python tools/install_core_from_github.py --ref main
python -m pip install -e core
```

Para copiar además las pruebas históricas del repositorio M5GP 2.0:

```bash
python tools/install_core_from_github.py --ref main --copy-tests
```

No confirme esos archivos históricos dentro de GenLab.

## Comprobación previa a cada push

```bash
python tools/check_github_repository.py
git status --short
```

Verifique especialmente que no se publiquen credenciales, datasets, bases de datos, artefactos de experimentos o fuentes originales de M5GP 2.0.
