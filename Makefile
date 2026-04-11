.PHONY: help install install-be install-fe install-root venv dev dev-web dev-api

# Default Python for venv creation (override: make venv PYTHON=python3.12)
PYTHON ?= python3

help:
	@echo "PEAD-tool — common targets"
	@echo ""
	@echo "  make install       Create .venv if missing, pip install -r requirements.txt,"
	@echo "                     npm install in web/, npm install at repo root (concurrently)."
	@echo "  make install-be    Backend only (venv + requirements.txt)"
	@echo "  make install-fe    Frontend only (web/)"
	@echo "  make install-root  Root dev deps only (concurrently for optional npm run dev)"
	@echo "  make venv          Create .venv only (no pip install)"
	@echo "  make dev           FastAPI + Vite (scripts/dev.sh; uses .venv if present)"
	@echo ""
	@echo "First-time setup:  cp .env.sample .env   then   make install   then   make dev"

venv:
	@if [ ! -x .venv/bin/python ]; then \
		echo "==> Creating .venv with $(PYTHON)"; \
		$(PYTHON) -m venv .venv; \
	else \
		echo "==> .venv already exists"; \
	fi

install-be: venv
	@echo "==> pip install (backend)"
	.venv/bin/pip install -U pip setuptools wheel
	.venv/bin/pip install -r requirements.txt

install-fe:
	@echo "==> npm install (web/)"
	cd web && npm install

install-root:
	@echo "==> npm install (repo root — concurrently for optional: npm run dev)"
	npm install

# One-shot: everything needed for scripts/dev.sh and local development
install: install-be install-fe install-root
	@echo ""
	@echo "==> Done. Copy env if needed: cp .env.sample .env"
	@echo "    Then: make dev"

dev:
	bash scripts/dev.sh

dev-web:
	cd web && npm run dev

dev-api:
	@if [ -x .venv/bin/python ]; then \
		.venv/bin/python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000; \
	else \
		$(PYTHON) -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000; \
	fi
