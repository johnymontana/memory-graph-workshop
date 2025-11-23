"""Test script for geospatial and time-based search functionality."""

import asyncio
import os
from dotenv import load_dotenv
from app.neo4j_client import Neo4jClient
from app.agent import news_agent, NewsDependencies

load_dotenv()


async def test_geospatial_search_direct():
    """Test geospatial search directly through Neo4jClient."""
    print("\n" + "="*80)
    print("=== Testing Geospatial Search (Direct) ===")
    print("="*80 + "\n")
    
    neo4j_client = Neo4jClient()
    
    try:
        # First, create the geospatial index
        print("Creating geospatial index...")
        neo4j_client.create_geospatial_index()
        print("✓ Geospatial index created\n")
        
        # Test 1: Search near the center (0.0, 0.0) - should find "Global" news
        print("Test 1: Searching for news near coordinates (0.0, 0.0) within 1000km...")
        results = neo4j_client.search_news_by_location(
            latitude=0.0,
            longitude=0.0,
            radius_km=1000,
            limit=5
        )
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Location: {article['location_name']} ({article['distance_km']} km away)")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
        
        # Test 2: Search near United States coordinates
        print("\n" + "="*80 + "\n")
        print("Test 2: Searching for news near United States (37.09, -95.71) within 2000km...")
        results = neo4j_client.search_news_by_location(
            latitude=37.09,
            longitude=-95.71,
            radius_km=2000,
            limit=5
        )
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Location: {article['location_name']} ({article['distance_km']} km away)")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
            
    finally:
        neo4j_client.close()


async def test_time_based_search_direct():
    """Test time-based search directly through Neo4jClient."""
    print("\n" + "="*80)
    print("=== Testing Time-Based Search (Direct) ===")
    print("="*80 + "\n")
    
    neo4j_client = Neo4jClient()
    
    try:
        # Test 1: Search with explicit date range
        print("Test 1: Searching for news from 2024-11-01 to 2024-11-10...")
        results = neo4j_client.search_news_by_date_range(
            start_date="2024-11-01",
            end_date="2024-11-10",
            limit=5
        )
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
        
        # Test 2: Search with relative period - last_week
        print("\n" + "="*80 + "\n")
        print("Test 2: Searching for news from 'last_week' to today...")
        results = neo4j_client.search_news_by_date_range(
            start_date="last_week",
            end_date="today",
            limit=5
        )
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
        
        # Test 3: Search with relative period - last_7_days
        print("\n" + "="*80 + "\n")
        print("Test 3: Searching for news from 'last_7_days'...")
        results = neo4j_client.search_news_by_date_range(
            start_date="last_7_days",
            limit=5
        )
        
        print(f"\nFound {len(results)} articles:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Published: {article['published']}")
            print(f"   Topics: {', '.join(article['topics'][:3])}")
            print(f"   URL: {article['url']}\n")
            
    finally:
        neo4j_client.close()


async def test_through_agent():
    """Test geospatial and time-based search through the Pydantic AI agent."""
    print("\n" + "="*80)
    print("=== Testing Through Pydantic AI Agent ===")
    print("="*80 + "\n")
    
    neo4j_client = Neo4jClient()
    
    try:
        # Ensure index is created
        neo4j_client.create_geospatial_index()
        
        deps = NewsDependencies(neo4j_client=neo4j_client)
        
        # Test 1: Geospatial query
        query1 = "What news is happening near the United States?"
        print(f"Query 1: {query1}\n")
        
        result1 = await news_agent.run(query1, deps=deps)
        
        print("Agent Response:")
        print("-" * 80)
        print(result1.output)
        print("-" * 80)
        
        # Test 2: Time-based query
        print("\n" + "="*80 + "\n")
        query2 = "Show me news from the last week"
        print(f"Query 2: {query2}\n")
        
        result2 = await news_agent.run(query2, deps=deps)
        
        print("Agent Response:")
        print("-" * 80)
        print(result2.output)
        print("-" * 80)
        
        # Test 3: Combined query
        print("\n" + "="*80 + "\n")
        query3 = "What's the latest news about climate change from last month?"
        print(f"Query 3: {query3}\n")
        
        result3 = await news_agent.run(query3, deps=deps)
        
        print("Agent Response:")
        print("-" * 80)
        print(result3.output)
        print("-" * 80)
        
    finally:
        neo4j_client.close()


async def main():
    """Run all tests."""
    print("\n")
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + "  Geospatial and Time-Based Search - Test Suite".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)
    
    # Test direct client methods
    await test_geospatial_search_direct()
    await test_time_based_search_direct()
    
    # Test through agent
    await test_through_agent()
    
    print("\n")
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + "  All Tests Complete!".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())


