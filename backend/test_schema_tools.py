"""Test script for the new schema and Cypher tools."""

import asyncio
import os
from dotenv import load_dotenv
from app.neo4j_client import Neo4jClient

load_dotenv()


async def test_schema_tools():
    """Test the new schema and Cypher tools."""
    print("=" * 60)
    print("Testing Neo4j Schema and Cypher Tools")
    print("=" * 60)
    
    # Initialize client
    client = Neo4jClient()
    
    try:
        # Test 1: Get database schema
        print("\n1. Testing get_database_schema()...")
        print("-" * 60)
        schema = client.get_database_schema()
        print(f"✓ Node Labels: {', '.join(schema['node_labels'][:5])}...")
        print(f"✓ Relationship Types: {', '.join(schema['relationship_types'][:5])}...")
        print(f"✓ Property Keys: {len(schema['property_keys'])} keys found")
        print(f"✓ Constraints: {len(schema['constraints'])} constraints found")
        print(f"✓ Indexes: {len(schema['indexes'])} indexes found")
        print(f"✓ Relationship Patterns: {len(schema['relationship_patterns'])} patterns found")
        
        # Show some node properties
        print("\nNode Properties (first 3):")
        for i, (label, props) in enumerate(list(schema['node_properties'].items())[:3]):
            print(f"  - {label}: {', '.join(props[:5])}")
        
        # Test 2: Generate Cypher from text
        print("\n2. Testing generate_cypher_from_text()...")
        print("-" * 60)
        test_queries = [
            "Find 5 recent articles about technology",
            "What articles mention climate change?",
            "Show me articles with their topics"
        ]
        
        for query in test_queries:
            print(f"\nNatural Language: '{query}'")
            cypher = client.generate_cypher_from_text(query, schema)
            print(f"Generated Cypher:\n{cypher}\n")
        
        # Test 3: Execute a read query
        print("\n3. Testing execute_read_query()...")
        print("-" * 60)
        
        # Test a simple query
        simple_query = """
        MATCH (a:Article)
        RETURN a.title as title, a.published as published
        ORDER BY a.published DESC
        LIMIT 3
        """
        print(f"Executing query:\n{simple_query}")
        results = client.execute_read_query(simple_query)
        print(f"\n✓ Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['title']} ({result['published']})")
        
        # Test 4: Test write query rejection
        print("\n4. Testing write query rejection...")
        print("-" * 60)
        write_query = "CREATE (n:Test {name: 'test'}) RETURN n"
        try:
            client.execute_read_query(write_query)
            print("✗ FAILED: Write query should have been rejected!")
        except ValueError as e:
            print(f"✓ Write query correctly rejected: {e}")
        
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(test_schema_tools())

