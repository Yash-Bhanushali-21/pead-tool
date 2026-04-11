.PHONY: dev dev-web dev-api install-web

# Run FastAPI + Vite together (uses scripts/dev.sh — respects .venv if present)
dev:
	bash scripts/dev.sh

# Optional: install web deps only
install-web:
	cd web && npm install
