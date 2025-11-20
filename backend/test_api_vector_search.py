"""
Test vector search through the FastAPI endpoint.

This script demonstrates that vector search works through the entire stack:
- FastAPI endpoint
- Pydantic AI agent
- Neo4j vector search
"""

import asyncio
from app.main import neo4j_client, news_agent, NewsDependencies


async def test_agent_vector_search():
    """Test that the agent can use vector search."""
    print("=" * 70)
    print("Testing Vector Search Through Complete Agent Stack")
    print("=" * 70)
    
    deps = NewsDependencies(neo4j_client=neo4j_client)
    
    test_queries = [
        "Find me articles about climate change and its effects",
        "What's new in artificial intelligence research?",
        "Tell me about recent space discoveries"
    ]
    
    for query in test_queries:
        print(f"\n{'=' * 70}")
        print(f"Query: {query}")
        print('=' * 70)
        
        try:
            result = await news_agent.run(query, deps=deps)
            
            # Check if the agent used vector_search_news tool
            if hasattr(result, '_all_messages'):
                tool_calls = []
                for msg in result._all_messages():
                    if hasattr(msg, 'parts'):
                        for part in msg.parts:
                            if hasattr(part, 'tool_name'):
                                tool_calls.append(part.tool_name)
                
                if 'vector_search_news' in tool_calls:
                    print("\n✓ Agent used vector_search_news tool")
                else:
                    print(f"\n⚠ Agent used other tools: {', '.join(set(tool_calls))}")
            
            # Print response
            print(f"\nResponse:\n{'-' * 70}")
            response = result.output
            # Print first 500 characters of response
            print(response[:500])
            if len(response) > 500:
                print("... (truncated)")
            print('-' * 70)
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)


async def test_direct_client():
    """Test direct Neo4jClient vector search."""
    print("\n" + "=" * 70)
    print("Testing Direct Neo4jClient Vector Search")
    print("=" * 70)
    
    query = "renewable energy and sustainability"
    print(f"\nQuery: {query}\n")
    
    results = neo4j_client.vector_search_news(query, limit=3)
    
    for i, article in enumerate(results, 1):
        print(f"{i}. {article['title']}")
        print(f"   Similarity: {article['similarity_score']:.4f}")
        print(f"   Published: {article['published']}")
        print()
    
    print("✓ Direct vector search working!")


async def main():
    """Run all tests."""
    # Test direct client first
    await test_direct_client()
    
    # Test through agent
    await test_agent_vector_search()


if __name__ == "__main__":
    asyncio.run(main())

