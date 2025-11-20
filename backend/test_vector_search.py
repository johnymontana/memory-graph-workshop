"""Test script for vector search functionality."""

import asyncio
import os
from dotenv import load_dotenv
from app.neo4j_client import Neo4jClient
from app.agent import news_agent, NewsDependencies

load_dotenv()


async def test_vector_search_direct():
    """Test vector search directly through Neo4jClient."""
    print("\n=== Testing Vector Search (Direct) ===\n")
    
    neo4j_client = Neo4jClient()
    
    try:
        # Test 1: Search for climate-related articles
        print("Test 1: Searching for 'climate change and global warming'...")
        results = neo4j_client.vector_search_news("climate change and global warming", limit=3)
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Similarity Score: {article['similarity_score']:.4f}")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
        
        # Test 2: Search for AI-related articles
        print("\n" + "="*60 + "\n")
        print("Test 2: Searching for 'artificial intelligence and machine learning'...")
        results = neo4j_client.vector_search_news("artificial intelligence and machine learning", limit=3)
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Similarity Score: {article['similarity_score']:.4f}")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
        
        # Test 3: Search for space exploration
        print("\n" + "="*60 + "\n")
        print("Test 3: Searching for 'space exploration and astronomy'...")
        results = neo4j_client.vector_search_news("space exploration and astronomy", limit=3)
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Similarity Score: {article['similarity_score']:.4f}")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
            
    finally:
        neo4j_client.close()


async def test_vector_search_with_agent():
    """Test vector search through the Pydantic AI agent."""
    print("\n" + "="*60)
    print("=== Testing Vector Search (Through Agent) ===")
    print("="*60 + "\n")
    
    neo4j_client = Neo4jClient()
    
    try:
        deps = NewsDependencies(neo4j_client=neo4j_client)
        
        # Test agent with a semantic query
        query = "Tell me about recent developments in renewable energy and sustainability"
        print(f"Query: {query}\n")
        
        result = await news_agent.run(query, deps=deps)
        
        print("Agent Response:")
        print("-" * 60)
        print(result.output)
        print("-" * 60)
        
    finally:
        neo4j_client.close()


async def main():
    """Run all tests."""
    # Test direct vector search
    await test_vector_search_direct()
    
    # Test vector search through agent
    await test_vector_search_with_agent()


if __name__ == "__main__":
    asyncio.run(main())

