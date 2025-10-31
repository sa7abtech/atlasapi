.PHONY: help setup install clean run-api run-bot run test docker-build docker-up docker-down logs load-kb

# Default target
help:
	@echo "ATLAS AI Assistant - Available Commands"
	@echo "========================================"
	@echo "setup        - Initial setup (venv, dependencies, .env)"
	@echo "install      - Install dependencies"
	@echo "clean        - Clean Python cache and logs"
	@echo "load-kb      - Load ALL knowledge base files (automated)"
	@echo "run          - Run both API and Bot"
	@echo "run-api      - Run FastAPI backend only"
	@echo "run-bot      - Run Telegram bot only"
	@echo "test         - Run tests"
	@echo "docker-build - Build Docker images"
	@echo "docker-up    - Start Docker containers"
	@echo "docker-down  - Stop Docker containers"
	@echo "logs         - Show Docker logs"
	@echo "process-kb   - Process single file (requires KB_FILE variable)"

# Setup virtual environment and dependencies
setup:
	@./setup.sh

# Install dependencies
install:
	@pip install -r requirements.txt

# Clean cache and logs
clean:
	@echo "Cleaning Python cache and logs..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@rm -f logs/*.log
	@echo "✓ Clean complete"

# Run both services
run:
	@./start.sh

# Run API only
run-api:
	@source venv/bin/activate && python api/app.py

# Run Bot only
run-bot:
	@source venv/bin/activate && python bot/main.py

# Run tests
test:
	@source venv/bin/activate && pytest tests/

# Docker commands
docker-build:
	@cd docker && docker-compose build

docker-up:
	@cd docker && docker-compose up -d
	@echo "✓ Docker containers started"
	@echo "API: http://localhost:8000"

docker-down:
	@cd docker && docker-compose down
	@echo "✓ Docker containers stopped"

logs:
	@cd docker && docker-compose logs -f

# Load ALL knowledge base files (automated)
load-kb:
	@source venv/bin/activate && ./load_knowledge_base.py

# Process single knowledge base file
process-kb:
	@if [ -z "$(KB_FILE)" ]; then \
		echo "Error: KB_FILE variable not set"; \
		echo "Usage: make process-kb KB_FILE=knowledge/data/your_file.md"; \
		exit 1; \
	fi
	@source venv/bin/activate && python knowledge/loader.py $(KB_FILE)

# Code formatting
format:
	@source venv/bin/activate && black . && ruff check .

# Health check
health:
	@curl -s http://localhost:8000/health | python -m json.tool

# View stats
stats:
	@curl -s http://localhost:8000/knowledge/stats | python -m json.tool

# View analytics
analytics:
	@curl -s "http://localhost:8000/analytics?days=7" | python -m json.tool
