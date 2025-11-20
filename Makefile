.PHONY: help backend frontend docker-up docker-down docker-logs install-backend install-frontend install clean setup init-sample-data

# Default target
help:
	@echo "Available commands:"
	@echo "  make backend          - Run the backend application"
	@echo "  make frontend         - Run the frontend application"
	@echo "  make install-backend  - Install backend dependencies"
	@echo "  make install-frontend - Install frontend dependencies"
	@echo "  make install          - Install both backend and frontend dependencies"
	@echo "  make docker-up        - Start Docker services"
	@echo "  make docker-down      - Stop Docker services"
	@echo "  make docker-logs      - View Docker logs"
	@echo "  make setup            - Initialize database and setup preferences"
	@echo "  make init-sample-data - Initialize sample news data in Neo4j"
	@echo "  make clean            - Clean up cache and temporary files"

# Backend commands
backend:
	@echo "Starting backend server..."
	cd backend && ENVIRONMENT=test uv run uvicorn app.main:app --reload

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && uv sync

# Frontend commands
frontend:
	@echo "Starting frontend server..."
	cd frontend && npm run dev

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Combined commands
install: install-backend install-frontend
	@echo "All dependencies installed!"

# Docker commands
docker-up:
	@echo "Starting Docker services..."
	docker-compose up -d

docker-down:
	@echo "Stopping Docker services..."
	docker-compose down

docker-logs:
	docker-compose logs -f

# Setup commands
setup: docker-up
	@echo "Waiting for databases to be ready..."
	@sleep 5
	@echo "Setting up preferences database..."
	cd backend && uv run python setup_preferences_db.py

# Initialize sample data
init-sample-data:
	@echo "Initializing sample news data..."
	cd backend && ENVIRONMENT=development uv run python initialize_sample_data.py

# Cleanup commands
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleanup complete!"

