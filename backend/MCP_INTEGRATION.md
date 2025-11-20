# MCP Server Integration Guide

This document outlines how to integrate the memory/preference provider as an external MCP (Model Context Protocol) server for use with PydanticAI and other MCP-compatible AI frameworks.

## Overview

The current implementation includes a modular `Neo4jMemoryProvider` that can be extracted and deployed as a standalone MCP server. This would allow:

- Centralized memory management across multiple AI agents
- Standardized interface for preference storage and retrieval
- External scaling and deployment of the memory system
- Reusability across different applications

## Current Architecture

```
┌─────────────────────────┐
│  FastAPI Backend        │
│  ┌──────────────────┐   │
│  │ PydanticAI Agent │   │
│  └────────┬─────────┘   │
│           │             │
│  ┌────────▼─────────┐   │
│  │ Memory Provider  │   │
│  └────────┬─────────┘   │
│           │             │
│  ┌────────▼─────────┐   │
│  │ Preferences      │   │
│  │ Client (Neo4j)   │   │
│  └──────────────────┘   │
└─────────────────────────┘
```

## MCP Server Architecture (Proposed)

```
┌─────────────────────────┐         ┌─────────────────────────┐
│  FastAPI Backend        │         │  MCP Memory Server      │
│  ┌──────────────────┐   │         │  ┌──────────────────┐   │
│  │ PydanticAI Agent │   │  MCP    │  │ Memory Provider  │   │
│  └────────┬─────────┘   │◄───────►│  └────────┬─────────┘   │
│           │             │         │           │             │
│  ┌────────▼─────────┐   │         │  ┌────────▼─────────┐   │
│  │ MCP Client       │   │         │  │ Preferences      │   │
│  └──────────────────┘   │         │  │ Client (Neo4j)   │   │
│                         │         │  └──────────────────┘   │
└─────────────────────────┘         └─────────────────────────┘
```

## Implementation Steps

### 1. Create MCP Server Application

Create a new file `backend/mcp_server.py`:

```python
"""Standalone MCP server for memory/preference management."""

from fastapi import FastAPI
from pydantic_ai.mcp import MCPServer
from app.preferences_client import PreferencesClient
from app.memory_provider import Neo4jMemoryProvider

app = FastAPI(title="Memory MCP Server")
mcp_server = MCPServer(app)

# Initialize clients
preferences_client = PreferencesClient()
memory_provider = Neo4jMemoryProvider(preferences_client)


@mcp_server.tool()
async def get_preferences() -> str:
    """Get all user preferences formatted for agent context."""
    return memory_provider.get_preference_context()


@mcp_server.tool()
async def extract_preferences(user_message: str, agent_response: str) -> dict:
    """Extract and store preferences from conversation."""
    return await memory_provider.process_conversation(user_message, agent_response)


@mcp_server.tool()
async def clear_preferences() -> dict:
    """Clear all stored preferences."""
    count = preferences_client.clear_all_preferences()
    return {"deleted_count": count}


@mcp_server.tool()
async def list_preferences() -> list:
    """List all stored preferences."""
    return preferences_client.get_all_preferences()


@mcp_server.tool()
async def get_preferences_status() -> dict:
    """Get preference statistics."""
    return preferences_client.get_preferences_summary()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### 2. Update Main Application to Use MCP Client

Modify `backend/app/main.py` to connect to the external MCP server:

```python
from pydantic_ai.mcp import MCPServerHTTP

# Connect to external MCP server
memory_mcp_server = MCPServerHTTP(url='http://localhost:8001/mcp')

# Configure agent with MCP server
agent = Agent(
    'openai:gpt-4o',
    deps_type=NewsDependencies,
    mcp_servers=[memory_mcp_server],
    system_prompt=BASE_SYSTEM_PROMPT
)
```

### 3. Deploy MCP Server

Deploy the MCP server as a separate service:

```bash
# Start the MCP server
cd backend
python mcp_server.py
```

The server will run on port 8001 by default.

### 4. Configure PydanticAI Agent

In your agent code, configure it to use the MCP tools:

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerHTTP

# Connect to MCP memory server
memory_server = MCPServerHTTP(url='http://localhost:8001/mcp')

# Create agent with MCP integration
agent = Agent(
    model='openai:gpt-4o',
    mcp_servers=[memory_server],
    system_prompt="You are a helpful assistant with memory capabilities."
)

# The agent can now use MCP tools automatically
result = await agent.run("What are my preferences?")
```

## MCP Protocol Endpoints

The MCP server should expose the following standardized endpoints:

### Tool Endpoints

1. **get_preferences**
   - Description: Retrieve user preferences for agent context
   - Input: None
   - Output: Formatted string of preferences

2. **extract_preferences**
   - Description: Extract preferences from conversation
   - Input: `user_message: str`, `agent_response: str`
   - Output: `{extracted_count: int, stored_count: int, preferences: list}`

3. **clear_preferences**
   - Description: Clear all stored preferences
   - Input: None
   - Output: `{deleted_count: int}`

4. **list_preferences**
   - Description: List all preferences
   - Input: None
   - Output: List of preference objects

5. **get_preferences_status**
   - Description: Get preference statistics
   - Input: None
   - Output: `{total_preferences: int, categories: list}`

### Resource Endpoints

Following MCP resource specification:

```json
{
  "resources": [
    {
      "uri": "memory://preferences",
      "name": "User Preferences",
      "description": "Learned user preferences from conversations",
      "mimeType": "application/json"
    }
  ]
}
```

## Security Considerations

When deploying as an external MCP server:

1. **Authentication**: Implement API key or OAuth authentication
2. **Rate Limiting**: Add rate limiting to prevent abuse
3. **Encryption**: Use HTTPS/TLS for all communications
4. **Access Control**: Implement user-based access control if needed
5. **Input Validation**: Validate all inputs to prevent injection attacks

## Deployment Options

### Docker Deployment

Create `backend/Dockerfile.mcp`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY mcp_server.py .

EXPOSE 8001

CMD ["python", "mcp_server.py"]
```

Add to `docker-compose.yml`:

```yaml
services:
  mcp-memory-server:
    build:
      context: ./backend
      dockerfile: Dockerfile.mcp
    container_name: mcp-memory-server
    ports:
      - "8001:8001"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=password
      - NEO4J_PREFERENCES_DATABASE=preferences
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - neo4j
```

### Kubernetes Deployment

Example Kubernetes manifests:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-memory-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-memory-server
  template:
    metadata:
      labels:
        app: mcp-memory-server
    spec:
      containers:
      - name: mcp-server
        image: your-registry/mcp-memory-server:latest
        ports:
        - containerPort: 8001
        env:
        - name: NEO4J_URI
          valueFrom:
            secretKeyRef:
              name: neo4j-credentials
              key: uri
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-credentials
              key: api-key
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-memory-server
spec:
  selector:
    app: mcp-memory-server
  ports:
  - port: 8001
    targetPort: 8001
  type: LoadBalancer
```

## Benefits of MCP Server Approach

1. **Separation of Concerns**: Memory management is decoupled from the main application
2. **Scalability**: Memory server can be scaled independently
3. **Reusability**: Multiple AI agents can share the same memory system
4. **Maintainability**: Updates to memory system don't require redeploying main app
5. **Standardization**: Follows MCP protocol for compatibility with other tools

## Migration Path

To migrate from the current integrated approach to MCP server:

1. ✅ **Phase 1** (Current): Integrated memory provider
   - Memory provider is part of the main FastAPI application
   - Direct function calls for preference management
   - All components in single deployment

2. 🔄 **Phase 2** (Transition): Dual mode support
   - Keep existing integrated provider
   - Add MCP server as optional alternative
   - Feature flag to switch between modes
   - Test MCP server with existing functionality

3. 🎯 **Phase 3** (Full MCP): External MCP server
   - Deploy memory provider as standalone MCP server
   - Main application uses MCP client exclusively
   - Remove integrated memory provider code
   - Scale and deploy independently

## Testing

Test the MCP server integration:

```python
import asyncio
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerHTTP

async def test_mcp_integration():
    # Connect to MCP server
    memory_server = MCPServerHTTP(url='http://localhost:8001/mcp')
    
    # Create test agent
    agent = Agent(
        model='openai:gpt-4o-mini',
        mcp_servers=[memory_server]
    )
    
    # Test preference storage
    result = await agent.run(
        "I prefer brief summaries about technology news",
        tools=['extract_preferences']
    )
    print("Stored preferences:", result.output)
    
    # Test preference retrieval
    result = await agent.run(
        "What are my preferences?",
        tools=['get_preferences']
    )
    print("Retrieved preferences:", result.output)

if __name__ == "__main__":
    asyncio.run(test_mcp_integration())
```

## Resources

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [PydanticAI MCP Documentation](https://ai.pydantic.dev/mcp/)
- [MCP Server Examples](https://github.com/modelcontextprotocol/servers)

## Next Steps

1. Review the current `Neo4jMemoryProvider` implementation
2. Extract reusable components into MCP server module
3. Implement MCP protocol endpoints
4. Test with PydanticAI agent
5. Deploy as separate service
6. Update main application to use MCP client
7. Monitor and optimize performance

