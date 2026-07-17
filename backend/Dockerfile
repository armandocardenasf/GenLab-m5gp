FROM python:3.12-slim
WORKDIR /app
COPY core /app/core
COPY backend /app/backend
RUN test -f /app/core/src/m5gp/m5gp.py || (echo "Ejecute tools/install_core_from_github.py antes de construir la imagen" && exit 1)
RUN pip install --no-cache-dir -e /app/core -e /app/backend[postgres]
CMD ["uvicorn","genlab_api.main:app","--app-dir","/app/backend/src","--host","0.0.0.0","--port","8000","--workers","1"]
