.PHONY: source install api frontend test verify srbench-install

source:
	python tools/install_core_from_github.py --ref main --copy-tests

install: source
	python -m pip install -e core
	python -m pip install -e backend

api:
	uvicorn genlab_api.main:app --app-dir backend/src --host 0.0.0.0 --port 8000 --workers 1

frontend:
	cd frontend && npm install && npm run dev

test:
	python tools/verify_structure.py
	python core/tests/test_imports.py

verify:
	python tools/verify_structure.py --require-source

srbench-install:
	@echo "Use: python integrations/srbench/install_into_srbench.py --srbench-root /ruta/srbench"
