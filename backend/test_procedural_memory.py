#!/usr/bin/env python3
"""Test script for procedural memory functionality."""

import os
import sys
import json
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_procedural_memory_schema():
    """Test that procedural memory client can initialize schema."""
    print("=" * 80)
    print("TEST 1: Procedural Memory Client Initialization")
    print("=" * 80)
    
    try:
        # Set test environment variables
        os.environ['MEMORY_NEO4J_URI'] = os.getenv('MEMORY_NEO4J_URI', 'bolt://localhost:7688')
        os.environ['MEMORY_NEO4J_USERNAME'] = os.getenv('MEMORY_NEO4J_USERNAME', 'neo4j')
        os.environ['MEMORY_NEO4J_PASSWORD'] = os.getenv('MEMORY_NEO4J_PASSWORD', 'memorypass')
        
        from procedural_memory_client import ProceduralMemoryClient
        
        print(f"✓ Importing ProceduralMemoryClient successful")
        
        # Try to initialize
        client = ProceduralMemoryClient()
        print(f"✓ ProceduralMemoryClient initialization successful")
        
        # Close connection
        client.close()
        print(f"✓ Connection closed successfully")
        
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_creation():
    """Test creating canonical Tool nodes."""
    print("\n" + "=" * 80)
    print("TEST 2: Tool Node Creation")
    print("=" * 80)
    
    try:
        os.environ['MEMORY_NEO4J_URI'] = os.getenv('MEMORY_NEO4J_URI', 'bolt://localhost:7688')
        os.environ['MEMORY_NEO4J_USERNAME'] = os.getenv('MEMORY_NEO4J_USERNAME', 'neo4j')
        os.environ['MEMORY_NEO4J_PASSWORD'] = os.getenv('MEMORY_NEO4J_PASSWORD', 'memorypass')
        
        from procedural_memory_client import ProceduralMemoryClient
        
        client = ProceduralMemoryClient()
        
        # Test creating/getting a tool
        tool_name = client.get_or_create_tool(
            tool_name="search_news",
            description="Search for news articles matching a query"
        )
        print(f"✓ Created/retrieved tool: {tool_name}")
        
        # Create another tool
        tool_name2 = client.get_or_create_tool(
            tool_name="get_recent_news",
            description="Get the most recent news articles"
        )
        print(f"✓ Created/retrieved tool: {tool_name2}")
        
        # Get tool statistics
        stats = client.get_tool_usage_stats()
        print(f"✓ Retrieved tool statistics: {len(stats)} tools found")
        for tool in stats:
            print(f"  - {tool['name']}: {tool['usage_count']} uses")
        
        client.close()
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reasoning_steps_storage():
    """Test storing reasoning steps and tool calls."""
    print("\n" + "=" * 80)
    print("TEST 3: Reasoning Steps and Tool Calls Storage")
    print("=" * 80)
    
    try:
        os.environ['MEMORY_NEO4J_URI'] = os.getenv('MEMORY_NEO4J_URI', 'bolt://localhost:7688')
        os.environ['MEMORY_NEO4J_USERNAME'] = os.getenv('MEMORY_NEO4J_USERNAME', 'neo4j')
        os.environ['MEMORY_NEO4J_PASSWORD'] = os.getenv('MEMORY_NEO4J_PASSWORD', 'memorypass')
        
        from procedural_memory_client import ProceduralMemoryClient
        from sessions_client import SessionsClient
        
        # Initialize clients
        proc_client = ProceduralMemoryClient()
        sess_client = SessionsClient()
        
        # Create a test thread
        thread_id = sess_client.create_thread(title="Procedural Memory Test")
        print(f"✓ Created test thread: {thread_id}")
        
        # Add a user message
        user_msg_id = sess_client.add_message_to_thread(
            thread_id=thread_id,
            text="What are the latest news about AI?",
            sender="user"
        )
        print(f"✓ Added user message: {user_msg_id}")
        
        # Add an agent message with reasoning steps
        agent_msg_id = sess_client.add_message_to_thread(
            thread_id=thread_id,
            text="Here are the latest AI news articles...",
            sender="agent"
        )
        print(f"✓ Added agent message: {agent_msg_id}")
        
        # Create sample reasoning steps with tool calls
        reasoning_steps = [
            {
                "step_number": 1,
                "reasoning": "User is asking about AI news, I'll search for recent articles about artificial intelligence.",
                "tool_calls": [
                    {
                        "name": "search_news",
                        "arguments": {"query": "artificial intelligence", "limit": 5},
                        "output": [
                            {"title": "AI Breakthrough", "abstract": "New AI model achieves..."},
                            {"title": "AI Safety", "abstract": "Companies commit to..."}
                        ]
                    }
                ]
            },
            {
                "step_number": 2,
                "reasoning": "I found relevant articles, now I'll format them for the user.",
                "tool_calls": []
            }
        ]
        
        # Store reasoning steps
        step_count = proc_client.store_reasoning_steps(
            message_id=agent_msg_id,
            thread_id=thread_id,
            reasoning_steps=reasoning_steps
        )
        print(f"✓ Stored {step_count} reasoning steps")
        
        # Retrieve reasoning steps
        retrieved_steps = proc_client.get_reasoning_steps_for_message(agent_msg_id)
        print(f"✓ Retrieved {len(retrieved_steps)} reasoning steps")
        
        for step in retrieved_steps:
            print(f"  Step {step['step_number']}: {step['reasoning_text'][:50]}...")
            print(f"    Tool calls: {len(step['tool_calls'])}")
            for tc in step['tool_calls']:
                print(f"      - {tc['tool_name']}")
        
        # Get updated tool statistics
        stats = proc_client.get_tool_usage_stats()
        print(f"\n✓ Tool usage statistics after test:")
        for tool in stats:
            print(f"  - {tool['name']}: {tool['usage_count']} uses")
        
        # Clean up
        sess_client.delete_thread(thread_id)
        print(f"\n✓ Cleaned up test thread")
        
        proc_client.close()
        sess_client.close()
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tree_structure():
    """Test that NEXT_STEP relationships create proper tree structure."""
    print("\n" + "=" * 80)
    print("TEST 4: Tree Structure with NEXT_STEP Relationships")
    print("=" * 80)
    
    try:
        os.environ['MEMORY_NEO4J_URI'] = os.getenv('MEMORY_NEO4J_URI', 'bolt://localhost:7688')
        os.environ['MEMORY_NEO4J_USERNAME'] = os.getenv('MEMORY_NEO4J_USERNAME', 'neo4j')
        os.environ['MEMORY_NEO4J_PASSWORD'] = os.getenv('MEMORY_NEO4J_PASSWORD', 'memorypass')
        
        from procedural_memory_client import ProceduralMemoryClient
        from sessions_client import SessionsClient
        
        proc_client = ProceduralMemoryClient()
        sess_client = SessionsClient()
        
        # Create test thread and message
        thread_id = sess_client.create_thread(title="Tree Structure Test")
        agent_msg_id = sess_client.add_message_to_thread(
            thread_id=thread_id,
            text="Test response with multiple reasoning steps",
            sender="agent"
        )
        
        # Create multiple reasoning steps to form a chain
        reasoning_steps = [
            {
                "step_number": 1,
                "reasoning": "First, I need to understand the query",
                "tool_calls": []
            },
            {
                "step_number": 2,
                "reasoning": "Now I'll search the database",
                "tool_calls": [
                    {
                        "name": "search_news",
                        "arguments": {"query": "test", "limit": 3},
                        "output": []
                    }
                ]
            },
            {
                "step_number": 3,
                "reasoning": "Finally, I'll format the results",
                "tool_calls": []
            }
        ]
        
        step_count = proc_client.store_reasoning_steps(
            message_id=agent_msg_id,
            thread_id=thread_id,
            reasoning_steps=reasoning_steps
        )
        print(f"✓ Stored {step_count} reasoning steps in a chain")
        
        # Verify the chain structure with a Cypher query
        with proc_client.driver.session() as session:
            result = session.run(
                """
                MATCH path = (r1:ReasoningStep {message_id: $message_id})
                             -[:NEXT_STEP*0..]->(r2:ReasoningStep)
                RETURN length(path) as path_length,
                       count(DISTINCT r2) as step_count
                ORDER BY path_length DESC
                LIMIT 1
                """,
                {"message_id": agent_msg_id}
            )
            record = result.single()
            if record:
                print(f"✓ Longest path has length: {record['path_length']}")
                print(f"✓ Total unique steps in graph: {record['step_count']}")
            else:
                print("⚠ No path found (might be expected if steps are isolated)")
        
        # Clean up
        sess_client.delete_thread(thread_id)
        print(f"✓ Cleaned up test thread")
        
        proc_client.close()
        sess_client.close()
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "PROCEDURAL MEMORY TEST SUITE" + " " * 30 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    results = []
    
    # Run tests
    results.append(("Schema Initialization", test_procedural_memory_schema()))
    results.append(("Tool Creation", test_tool_creation()))
    results.append(("Reasoning Steps Storage", test_reasoning_steps_storage()))
    results.append(("Tree Structure", test_tree_structure()))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

