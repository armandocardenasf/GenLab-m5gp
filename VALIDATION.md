# Validación

Se verificó la funcionalidad solicitada para la página **Datasets**:

- La sección se denomina **Datasets cargados**.
- Al hacer clic sobre una fila se consulta `GET /api/v1/datasets/{id}/preview`.
- La fila seleccionada queda resaltada.
- La selección funciona con teclado mediante `Enter` y barra espaciadora.
- El botón **Previsualizar** continúa disponible.
- Después de cargar un CSV o TSV, el dataset creado se selecciona y previsualiza automáticamente.
- Se muestran nombres de columnas, tipos de datos y las primeras 20 filas.
- TypeScript: PASS.
- Vite build: PASS.
- Módulos transformados: 1785.
