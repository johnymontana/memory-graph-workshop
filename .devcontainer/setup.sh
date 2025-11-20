#!/bin/bash

set -e

echo "🚀 Setting up Pydantic AI Neo4j development environment..."

# Install uv (Python package installer)
echo "📦 Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
export PATH="$HOME/.cargo/bin:$PATH"
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.zshrc

# Verify uv installation
echo "✅ Verifying uv installation..."
uv --version

# Start Docker Compose services
# echo "🐳 Starting Docker Compose services..."
# docker-compose up -d

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
uv sync
cd ..

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install
cd ..

# Create .env file from example if it doesn't exist
if [ ! -f backend/.env ]; then
    echo "📝 Creating backend/.env file from backend/.env.example..."
    cp backend/.env.example backend/.env
    echo "⚠️  Please update backend/.env with your API keys"
fi

# Create .env file from example if it doesn't exist
if [ ! -f frontend/.env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp frontend/.env.example frontend/.env
    # echo "⚠️  Please update backend/.env with your API keys"
fi

# Wait for Neo4j to be ready
# echo "⏳ Waiting for Neo4j to be ready..."
# sleep 10

# Setup preferences database
#echo "🗄️  Setting up preferences database..."
#cd backend
#uv run python setup_preferences_db.py || echo "⚠️  Failed to setup preferences database - you may need to run this manually"
#cd ..

# Initialize sample data
# echo "📊 Initializing sample news data..."
#cd backend
#ENVIRONMENT=development uv run python initialize_sample_data.py || echo "⚠️  Failed to initialize sample data - you may need to run this manually"
#cd ..

echo ""
echo "✨ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "  1. Update backend/.env with your API keys (OPENAI_API_KEY, etc.)"
echo "  2. Start the backend: make backend"
echo "  3. Start the frontend: make frontend"
# echo "  4. Open Neo4j Browser at http://localhost:7474 (neo4j/password)"
echo ""
echo "📚 Available commands:"
echo "  - make help           : Show all available commands"
echo "  - make backend        : Run backend server"
echo "  - make frontend       : Run frontend server"
#echo "  - make docker-up      : Start Docker services"
#echo "  - make docker-down    : Stop Docker services"
echo "  - make init-sample-data : Reinitialize sample data"
echo ""

