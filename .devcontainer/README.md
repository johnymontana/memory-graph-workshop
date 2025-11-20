# GitHub Codespaces Setup

This repository is configured to work seamlessly with GitHub Codespaces.

## Quick Start

1. **Open in Codespaces**
   - Click the "Code" button on GitHub
   - Select "Codespaces" tab
   - Click "Create codespace on main"

2. **Wait for Setup**
   - The devcontainer will automatically:
     - Install `uv` (Python package installer)
     - Install Python and Node.js dependencies
     - Start Neo4j services via Docker Compose
     - Setup the preferences database
     - Initialize sample news data

3. **Configure API Keys**
   - Edit `backend/.env` and add your API keys:
     ```bash
     OPENAI_API_KEY=your_key_here
     ```

4. **Start the Application**
   - Backend: `make backend` (or `cd backend && uv run uvicorn app.main:app --reload`)
   - Frontend: `make frontend` (or `cd frontend && npm run dev`)

## What's Included

### Services
- **Neo4j**: Graph database (ports 7474, 7687)
- **Backend**: FastAPI + Pydantic AI (port 8000)
- **Frontend**: Next.js (port 3000)

### Tools Installed
- Python 3.11 with `uv` package manager
- Node.js 20
- Docker-in-Docker
- VS Code extensions:
  - Python (ms-python.python)
  - Pylance (ms-python.vscode-pylance)
  - Neo4j (neo4j.neo4j-vscode)
  - ESLint (dbaeumer.vscode-eslint)
  - Prettier (esbenp.prettier-vscode)
  - Docker (ms-azuretools.vscode-docker)
  - GitLens (eamodio.gitlens)

### Environment Configuration
- Python dependencies managed via `uv` (see `backend/pyproject.toml`)
- Frontend dependencies via npm (see `frontend/package.json`)
- Neo4j runs in Docker with APOC plugin enabled
- Default credentials: `neo4j/password`

## Manual Setup Steps

If automatic setup fails, you can run these commands manually:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Install dependencies
make install

# Start Docker services
make docker-up

# Setup database
make setup

# Initialize sample data
make init-sample-data
```

## Useful Commands

```bash
# Show all available commands
make help

# Start backend server
make backend

# Start frontend server
make frontend

# View Docker logs
make docker-logs

# Reinitialize sample data
make init-sample-data

# Clean up cache files
make clean
```

## Accessing Services

All ports are automatically forwarded in Codespaces:

- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **Backend Docs**: `http://localhost:8000/docs`
- **Neo4j Browser**: `http://localhost:7474`
  - Username: `neo4j`
  - Password: `password`

## Troubleshooting

### Neo4j not starting
```bash
# Check Docker services
docker ps

# View Neo4j logs
make docker-logs

# Restart services
make docker-down
make docker-up
```

### Python dependencies issues
```bash
# Reinstall backend dependencies
cd backend
uv sync --force
```

### Frontend issues
```bash
# Reinstall frontend dependencies
cd frontend
npm install --force
```

### Sample data not loading
```bash
# Manually initialize sample data
make init-sample-data
```

## Development Workflow

1. **Make changes** to backend or frontend code
2. **Backend**: Auto-reloads on file changes (uvicorn --reload)
3. **Frontend**: Auto-reloads on file changes (Next.js fast refresh)
4. **Test**: Visit the frontend at http://localhost:3000
5. **API Docs**: Check FastAPI docs at http://localhost:8000/docs

## Environment Variables

Create or edit `backend/.env`:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Neo4j connection (defaults work in Codespaces)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Memory database (if using separate instance)
MEMORY_NEO4J_URI=bolt://localhost:7688
MEMORY_NEO4J_USER=neo4j
MEMORY_NEO4J_PASSWORD=memorypass

# Environment
ENVIRONMENT=development
```

## Notes

- The devcontainer uses the `universal` image which includes common development tools
- Docker Compose is used to run Neo4j services
- All setup is automated via `.devcontainer/setup.sh`
- Port forwarding is configured automatically for all services

