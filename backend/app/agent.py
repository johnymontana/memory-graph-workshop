"""Pydantic AI agent for querying world news from Neo4j."""

import os
from typing import List, Dict, Any, Optional, Callable
from functools import wraps
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from .neo4j_client import Neo4jClient


# Global retry tracking for transparency
_retry_log: List[Dict[str, Any]] = []


def get_retry_log() -> List[Dict[str, Any]]:
    """Get the current retry log and clear it."""
    global _retry_log
    log = _retry_log.copy()
    _retry_log.clear()
    return log


def is_result_empty_or_poor(result: Any) -> bool:
    """
    Check if a tool result is empty or of poor quality.
    
    Args:
        result: The tool result to evaluate
        
    Returns:
        True if result is empty/poor, False otherwise
    """
    if result is None:
        return True
    if isinstance(result, list) and len(result) == 0:
        return True
    if isinstance(result, dict) and len(result) == 0:
        return True
    if isinstance(result, str) and result.strip() == "":
        return True
    return False


def suggest_parameter_adjustments(tool_name: str, attempt: int, **kwargs) -> Dict[str, Any]:
    """
    Suggest parameter adjustments for retry attempts.
    
    Args:
        tool_name: Name of the tool being retried
        attempt: Current attempt number (1-indexed)
        **kwargs: Current parameters
        
    Returns:
        Adjusted parameters
    """
    adjusted = kwargs.copy()
    
    # Strategy 1: Increase limit if available
    if 'limit' in adjusted and attempt == 2:
        adjusted['limit'] = min(adjusted['limit'] * 2, 20)
        print(f"  Retry strategy: Increasing limit to {adjusted['limit']}")
    
    # Strategy 2: For search/vector search, try broadening
    if 'query' in adjusted and attempt == 3:
        # Keep the original query but the agent might have learned from first attempts
        print(f"  Retry strategy: Keeping query but agent may adjust approach")
    
    return adjusted


def tool_with_retry(max_retries: int = 3):
    """
    Decorator to add retry logic to tool functions.
    Retries on empty/poor results with parameter adjustments.
    
    Args:
        max_retries: Maximum number of total attempts (default 3)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            global _retry_log
            tool_name = func.__name__
            
            for attempt in range(1, max_retries + 1):
                try:
                    # Adjust parameters for retry attempts
                    if attempt > 1:
                        kwargs = suggest_parameter_adjustments(tool_name, attempt, **kwargs)
                    
                    # Call the original function
                    result = await func(*args, **kwargs)
                    
                    # Check if result is empty/poor
                    if is_result_empty_or_poor(result):
                        if attempt < max_retries:
                            retry_info = {
                                "tool": tool_name,
                                "attempt": attempt,
                                "reason": "empty_result",
                                "parameters": {k: v for k, v in kwargs.items() if k != 'ctx'}
                            }
                            _retry_log.append(retry_info)
                            print(f"⚠️  {tool_name} returned empty results on attempt {attempt}/{max_retries}, retrying...")
                            continue
                        else:
                            # Final attempt also failed
                            retry_info = {
                                "tool": tool_name,
                                "attempt": attempt,
                                "reason": "empty_result_final",
                                "parameters": {k: v for k, v in kwargs.items() if k != 'ctx'}
                            }
                            _retry_log.append(retry_info)
                            print(f"⚠️  {tool_name} returned empty results after {max_retries} attempts")
                            return result
                    else:
                        # Success
                        if attempt > 1:
                            print(f"✓ {tool_name} succeeded on attempt {attempt}")
                        return result
                        
                except Exception as e:
                    if attempt < max_retries:
                        retry_info = {
                            "tool": tool_name,
                            "attempt": attempt,
                            "reason": "exception",
                            "error": str(e),
                            "parameters": {k: v for k, v in kwargs.items() if k != 'ctx'}
                        }
                        _retry_log.append(retry_info)
                        print(f"⚠️  {tool_name} failed on attempt {attempt}/{max_retries}: {e}, retrying...")
                        continue
                    else:
                        # Final attempt failed with exception
                        retry_info = {
                            "tool": tool_name,
                            "attempt": attempt,
                            "reason": "exception_final",
                            "error": str(e),
                            "parameters": {k: v for k, v in kwargs.items() if k != 'ctx'}
                        }
                        _retry_log.append(retry_info)
                        print(f"⚠️  {tool_name} failed after {max_retries} attempts: {e}")
                        raise
            
            # Should never reach here
            return None
            
        return wrapper
    return decorator


class NewsQuery(BaseModel):
    """Model for news query parameters."""
    query: str = Field(description="The search query for news articles")
    limit: int = Field(default=5, description="Maximum number of results to return")


class NewsDependencies(BaseModel):
    """Dependencies for the news agent."""
    neo4j_client: Neo4jClient

    class Config:
        arbitrary_types_allowed = True


# Base system prompt (without preferences)
BASE_SYSTEM_PROMPT = """You are a helpful news assistant that helps users find and learn about world news.
You have access to a Neo4j database containing news articles about various topics including technology,
science, environment, business, and more.

When users ask about news, you should:
1. Search the database for relevant articles using:
   - Vector search (semantic search) for finding articles by meaning and concept
   - Keyword search for exact text matches
   - Topic filtering for specific categories
   - Geospatial search for finding news near specific locations (by latitude/longitude and radius)
   - Time-based search for filtering articles by date ranges (supports both explicit dates like '2024-11-01' 
     and relative periods like 'last_week', 'last_month', 'last_7_days')
   - Database schema inspection to understand the data structure
   - Natural language to Cypher query generation for complex custom queries
   - Direct Cypher query execution for advanced data exploration (read-only)
2. Present the information in a clear, conversational way
3. Highlight key details like the title, abstract, published date, byline, and URL
4. Provide context and explain connections between different news items when relevant
5. Mention related topics, people, organizations, and locations when available

For conceptual or semantic queries, prefer using vector search which finds articles by meaning.
For specific keywords or names, use the regular keyword search.
If users ask about specific topics (climate change, artificial intelligence, space exploration, etc.),
you can filter news by those topics.
For location-based queries (e.g., "news near San Francisco", "what's happening around London"),
use geospatial search with appropriate coordinates and radius.
For time-based queries (e.g., "news from last week", "articles from November 2024"),
use date range search with appropriate start and end dates.

For advanced or complex queries that don't fit the standard search tools:
- Use get_database_schema to understand the database structure
- Use text2cypher to convert natural language questions into Cypher queries
- Use execute_cypher to run custom read-only Cypher queries for complex data needs

Be conversational, informative, and helpful."""


def build_system_prompt(include_preferences: bool = False, preferences: Optional[str] = None) -> str:
    """
    Build the system prompt with optional user preferences.

    Args:
        include_preferences: Whether to include preference context
        preferences: Formatted preference string to inject

    Returns:
        Complete system prompt
    """
    if include_preferences and preferences:
        return f"""{BASE_SYSTEM_PROMPT}

--- User Preferences ---
{preferences}

Please take these preferences into account when responding to the user.
"""
    return BASE_SYSTEM_PROMPT


# Get OpenAI model from environment variable
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


# Create the default news agent (without preferences)
news_agent = Agent(
    f'openai:{OPENAI_MODEL}',
    deps_type=NewsDependencies,
    system_prompt=BASE_SYSTEM_PROMPT
)


# Tool functions that can be registered on any agent
@tool_with_retry(max_retries=3)
async def search_news(ctx: RunContext[NewsDependencies], query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for news articles matching the query.

    Args:
        ctx: The run context with Neo4j client
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of matching news articles
    """
    articles = ctx.deps.neo4j_client.search_news(query, limit)
    return articles


@tool_with_retry(max_retries=3)
async def get_recent_news(ctx: RunContext[NewsDependencies], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent news articles.

    Args:
        ctx: The run context with Neo4j client
        limit: Maximum number of results

    Returns:
        List of recent news articles
    """
    articles = ctx.deps.neo4j_client.get_recent_news(limit)
    return articles


@tool_with_retry(max_retries=3)
async def get_news_by_topic(ctx: RunContext[NewsDependencies], topic: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get news articles from a specific topic.

    Args:
        ctx: The run context with Neo4j client
        topic: Topic name (e.g., 'Climate Change', 'Artificial Intelligence', 'Space Exploration')
        limit: Maximum number of results

    Returns:
        List of news articles about the topic
    """
    articles = ctx.deps.neo4j_client.get_news_by_topic(topic, limit)
    return articles


async def get_topics(ctx: RunContext[NewsDependencies]) -> List[str]:
    """
    Get all available news topics.

    Args:
        ctx: The run context with Neo4j client

    Returns:
        List of topic names
    """
    topics = ctx.deps.neo4j_client.get_topics()
    return topics


@tool_with_retry(max_retries=3)
async def vector_search_news(ctx: RunContext[NewsDependencies], query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for news articles using semantic vector search.
    This finds articles by meaning rather than exact keyword matches.

    Args:
        ctx: The run context with Neo4j client
        query: Search query string (will be converted to an embedding)
        limit: Maximum number of results

    Returns:
        List of news articles with similarity scores
    """
    articles = ctx.deps.neo4j_client.vector_search_news(query, limit)
    return articles


@tool_with_retry(max_retries=3)
async def search_news_by_location(
    ctx: RunContext[NewsDependencies], 
    latitude: float, 
    longitude: float, 
    radius_km: float = 100, 
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Search for news articles about locations within a specified distance from a geographic point.
    This is useful for finding news near a specific location.

    Args:
        ctx: The run context with Neo4j client
        latitude: Latitude of the center point (e.g., 37.7749 for San Francisco)
        longitude: Longitude of the center point (e.g., -122.4194 for San Francisco)
        radius_km: Search radius in kilometers (default: 100)
        limit: Maximum number of results

    Returns:
        List of news articles with distance information
    """
    articles = ctx.deps.neo4j_client.search_news_by_location(latitude, longitude, radius_km, limit)
    return articles


@tool_with_retry(max_retries=3)
async def search_news_by_date_range(
    ctx: RunContext[NewsDependencies],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Search for news articles within a specific date range.
    Supports both explicit dates (YYYY-MM-DD) and relative periods.

    Args:
        ctx: The run context with Neo4j client
        start_date: Start date (YYYY-MM-DD) or relative period 
                   (e.g., 'last_week', 'last_month', 'last_7_days', 'last_30_days')
                   If None, no lower bound is applied
        end_date: End date (YYYY-MM-DD) or relative period (e.g., 'today', 'yesterday')
                 If None, defaults to today
        limit: Maximum number of results

    Returns:
        List of news articles within the date range
    """
    articles = ctx.deps.neo4j_client.search_news_by_date_range(start_date, end_date, limit)
    return articles


async def get_database_schema(ctx: RunContext[NewsDependencies]) -> Dict[str, Any]:
    """
    Get the Neo4j database schema including node labels, relationship types,
    properties, constraints, and indexes.

    Args:
        ctx: The run context with Neo4j client

    Returns:
        Dictionary containing comprehensive schema information
    """
    schema = ctx.deps.neo4j_client.get_database_schema()
    return schema


async def text2cypher(ctx: RunContext[NewsDependencies], query: str) -> Dict[str, str]:
    """
    Generate a Cypher query from a natural language description.
    This tool uses the database schema and AI to convert your question into a Cypher query.

    Args:
        ctx: The run context with Neo4j client
        query: Natural language description of what you want to query

    Returns:
        Dictionary containing the generated Cypher query and explanation
    """
    # First get the database schema
    schema = ctx.deps.neo4j_client.get_database_schema()
    
    # Generate Cypher query from natural language
    cypher_query = ctx.deps.neo4j_client.generate_cypher_from_text(query, schema)
    
    return {
        "query": cypher_query,
        "explanation": f"Generated Cypher query for: '{query}'",
        "note": "Use the execute_cypher tool to run this query"
    }


@tool_with_retry(max_retries=3)
async def execute_cypher(ctx: RunContext[NewsDependencies], cypher: str) -> List[Dict[str, Any]]:
    """
    Execute a read-only Cypher query against the Neo4j database.
    This is useful for custom queries and advanced data exploration.
    
    IMPORTANT: Only read queries are allowed (MATCH, RETURN, WITH, etc.).
    Write operations (CREATE, MERGE, DELETE, SET, etc.) will be rejected.

    Args:
        ctx: The run context with Neo4j client
        cypher: The Cypher query to execute (must be read-only)

    Returns:
        List of query results as dictionaries
    """
    results = ctx.deps.neo4j_client.execute_read_query(cypher)
    return results


# Register tools on the default news agent
news_agent.tool(search_news)
news_agent.tool(get_recent_news)
news_agent.tool(get_news_by_topic)
news_agent.tool(get_topics)
news_agent.tool(vector_search_news)
news_agent.tool(search_news_by_location)
news_agent.tool(search_news_by_date_range)
news_agent.tool(get_database_schema)
news_agent.tool(text2cypher)
news_agent.tool(execute_cypher)


def create_agent_with_preferences(preferences: str) -> Agent:
    """
    Create a news agent with user preferences injected into the system prompt.
    This agent has all the same tools as the default agent.

    Args:
        preferences: Formatted preference string

    Returns:
        Agent configured with preferences and all tools registered
    """
    agent = Agent(
        f'openai:{OPENAI_MODEL}',
        deps_type=NewsDependencies,
        system_prompt=build_system_prompt(include_preferences=True, preferences=preferences)
    )
    
    # Register all the same tools on this agent
    agent.tool(search_news)
    agent.tool(get_recent_news)
    agent.tool(get_news_by_topic)
    agent.tool(get_topics)
    agent.tool(vector_search_news)
    agent.tool(search_news_by_location)
    agent.tool(search_news_by_date_range)
    agent.tool(get_database_schema)
    agent.tool(text2cypher)
    agent.tool(execute_cypher)
    
    return agent
