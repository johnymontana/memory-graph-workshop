#!/usr/bin/env python3
"""Test script for message relationship functionality (FIRST_MESSAGE and NEXT_MESSAGE)."""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_first_message_relationship():
    """Test that FIRST_MESSAGE relationship is created for the first message in a thread."""
    print("=" * 80)
    print("TEST 1: FIRST_MESSAGE Relationship")
    print("=" * 80)
    
    try:
        # Set test environment variables
        os.environ['MEMORY_NEO4J_URI'] = os.getenv('MEMORY_NEO4J_URI', 'bolt://localhost:7688')
        os.environ['MEMORY_NEO4J_USERNAME'] = os.getenv('MEMORY_NEO4J_USERNAME', 'neo4j')
        os.environ['MEMORY_NEO4J_PASSWORD'] = os.getenv('MEMORY_NEO4J_PASSWORD', 'memorypass')
        
        from sessions_client import SessionsClient
        
        # Initialize client
        client = SessionsClient()
        print("✓ SessionsClient initialized")
        
        # Create a test thread
        thread_id = client.create_thread(title="First Message Test")
        print(f"✓ Created test thread: {thread_id}")
        
        # Add the first message
        first_msg_id = client.add_message_to_thread(
            thread_id=thread_id,
            text="This is the first message in the thread",
            sender="user"
        )
        print(f"✓ Added first message: {first_msg_id}")
        
        # Verify FIRST_MESSAGE relationship exists
        with client.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})-[:FIRST_MESSAGE]->(m:Message)
                RETURN m.id as message_id, m.text as text
                """,
                {"thread_id": thread_id}
            )
            record = result.single()
            
            if record:
                print(f"✓ FIRST_MESSAGE relationship found")
                print(f"  Message ID: {record['message_id']}")
                print(f"  Message text: {record['text'][:50]}...")
                
                # Verify it points to the correct message
                if record['message_id'] == first_msg_id:
                    print("✓ FIRST_MESSAGE points to the correct message")
                else:
                    print("✗ FIRST_MESSAGE points to wrong message!")
                    return False
            else:
                print("✗ FIRST_MESSAGE relationship not found!")
                return False
        
        # Add a second message to ensure FIRST_MESSAGE doesn't get added again
        second_msg_id = client.add_message_to_thread(
            thread_id=thread_id,
            text="This is the second message",
            sender="agent"
        )
        print(f"✓ Added second message: {second_msg_id}")
        
        # Verify there's still only one FIRST_MESSAGE relationship
        with client.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})-[:FIRST_MESSAGE]->(m:Message)
                RETURN count(m) as first_count, collect(m.id) as message_ids
                """,
                {"thread_id": thread_id}
            )
            record = result.single()
            
            if record['first_count'] == 1:
                print(f"✓ Still only one FIRST_MESSAGE relationship")
                if record['message_ids'][0] == first_msg_id:
                    print("✓ FIRST_MESSAGE still points to the first message")
                else:
                    print("✗ FIRST_MESSAGE changed to different message!")
                    return False
            else:
                print(f"✗ Found {record['first_count']} FIRST_MESSAGE relationships (expected 1)")
                return False
        
        # Clean up
        client.delete_thread(thread_id)
        print("✓ Cleaned up test thread")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_next_message_relationships():
    """Test that NEXT_MESSAGE relationships connect messages in order."""
    print("\n" + "=" * 80)
    print("TEST 2: NEXT_MESSAGE Relationships")
    print("=" * 80)
    
    try:
        os.environ['MEMORY_NEO4J_URI'] = os.getenv('MEMORY_NEO4J_URI', 'bolt://localhost:7688')
        os.environ['MEMORY_NEO4J_USERNAME'] = os.getenv('MEMORY_NEO4J_USERNAME', 'neo4j')
        os.environ['MEMORY_NEO4J_PASSWORD'] = os.getenv('MEMORY_NEO4J_PASSWORD', 'memorypass')
        
        from sessions_client import SessionsClient
        
        client = SessionsClient()
        
        # Create a test thread
        thread_id = client.create_thread(title="Message Chain Test")
        print(f"✓ Created test thread: {thread_id}")
        
        # Add multiple messages to form a chain
        message_ids = []
        messages = [
            ("user", "What are the latest news?"),
            ("agent", "Here are the latest articles..."),
            ("user", "Tell me more about AI"),
            ("agent", "AI news include..."),
            ("user", "Thanks!")
        ]
        
        for sender, text in messages:
            msg_id = client.add_message_to_thread(
                thread_id=thread_id,
                text=text,
                sender=sender
            )
            message_ids.append(msg_id)
            print(f"✓ Added message {len(message_ids)}: {sender}")
        
        # Verify NEXT_MESSAGE chain
        print("\n✓ Verifying NEXT_MESSAGE chain...")
        
        with client.driver.session() as session:
            # Check that we can traverse from first to last message
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})-[:FIRST_MESSAGE]->(first:Message)
                MATCH path = (first)-[:NEXT_MESSAGE*]->(last:Message)
                WHERE NOT (last)-[:NEXT_MESSAGE]->()
                RETURN length(path) as chain_length,
                       [node in nodes(path) | node.id] as message_chain
                """,
                {"thread_id": thread_id}
            )
            record = result.single()
            
            if record:
                chain_length = record['chain_length']
                expected_length = len(messages) - 1  # N messages = N-1 relationships
                
                print(f"  Chain length: {chain_length} (expected {expected_length})")
                
                if chain_length == expected_length:
                    print("✓ Chain length is correct")
                    
                    # Verify the order matches our message_ids
                    message_chain = record['message_chain']
                    if message_chain == message_ids:
                        print("✓ Message chain order is correct")
                    else:
                        print("✗ Message chain order is incorrect!")
                        print(f"  Expected: {message_ids}")
                        print(f"  Got: {message_chain}")
                        return False
                else:
                    print(f"✗ Chain length is incorrect!")
                    return False
            else:
                print("✗ Could not find complete message chain!")
                return False
        
        # Verify each message has at most one NEXT_MESSAGE
        with client.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})-[:HAS_MESSAGE]->(m:Message)
                OPTIONAL MATCH (m)-[next:NEXT_MESSAGE]->()
                WITH m, count(next) as next_count
                WHERE next_count > 1
                RETURN count(m) as messages_with_multiple_next
                """,
                {"thread_id": thread_id}
            )
            record = result.single()
            
            if record['messages_with_multiple_next'] == 0:
                print("✓ Each message has at most one NEXT_MESSAGE relationship")
            else:
                print(f"✗ Found {record['messages_with_multiple_next']} messages with multiple NEXT_MESSAGE!")
                return False
        
        # Clean up
        client.delete_thread(thread_id)
        print("\n✓ Cleaned up test thread")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_message_traversal():
    """Test traversing messages using the new relationships."""
    print("\n" + "=" * 80)
    print("TEST 3: Message Traversal via FIRST_MESSAGE and NEXT_MESSAGE")
    print("=" * 80)
    
    try:
        os.environ['MEMORY_NEO4J_URI'] = os.getenv('MEMORY_NEO4J_URI', 'bolt://localhost:7688')
        os.environ['MEMORY_NEO4J_USERNAME'] = os.getenv('MEMORY_NEO4J_USERNAME', 'neo4j')
        os.environ['MEMORY_NEO4J_PASSWORD'] = os.getenv('MEMORY_NEO4J_PASSWORD', 'memorypass')
        
        from sessions_client import SessionsClient
        
        client = SessionsClient()
        
        # Create a test thread
        thread_id = client.create_thread(title="Traversal Test")
        print(f"✓ Created test thread: {thread_id}")
        
        # Add messages
        messages = [
            "First user message",
            "First agent response",
            "Second user message",
            "Second agent response"
        ]
        
        for i, text in enumerate(messages):
            sender = "user" if i % 2 == 0 else "agent"
            client.add_message_to_thread(
                thread_id=thread_id,
                text=text,
                sender=sender
            )
        
        print(f"✓ Added {len(messages)} messages")
        
        # Traverse messages using FIRST_MESSAGE and NEXT_MESSAGE
        with client.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})-[:FIRST_MESSAGE]->(first:Message)
                MATCH path = (first)-[:NEXT_MESSAGE*0..]->(m:Message)
                WITH m, length(path) as position
                ORDER BY position
                RETURN m.text as text, 
                       m.sender as sender,
                       position
                """,
                {"thread_id": thread_id}
            )
            
            print("\n  Traversed messages (in order):")
            retrieved_messages = []
            for record in result:
                position = record['position']
                sender = record['sender']
                text = record['text']
                retrieved_messages.append(text)
                print(f"    {position + 1}. [{sender}] {text[:40]}...")
            
            # Verify we got all messages in the right order
            if retrieved_messages == messages:
                print("\n✓ All messages retrieved in correct order")
            else:
                print("\n✗ Messages retrieved in wrong order or missing!")
                print(f"  Expected: {messages}")
                print(f"  Got: {retrieved_messages}")
                return False
        
        # Test alternative traversal: get message count via chain
        with client.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})-[:FIRST_MESSAGE]->(first:Message)
                MATCH path = (first)-[:NEXT_MESSAGE*0..]->(m:Message)
                RETURN count(DISTINCT m) as total_messages
                """,
                {"thread_id": thread_id}
            )
            record = result.single()
            
            if record['total_messages'] == len(messages):
                print(f"✓ Message count via chain traversal: {record['total_messages']}")
            else:
                print(f"✗ Message count mismatch: expected {len(messages)}, got {record['total_messages']}")
                return False
        
        # Clean up
        client.delete_thread(thread_id)
        print("\n✓ Cleaned up test thread")
        
        client.close()
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
    print("║" + " " * 18 + "MESSAGE RELATIONSHIPS TEST SUITE" + " " * 28 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    results = []
    
    # Run tests
    results.append(("FIRST_MESSAGE Relationship", test_first_message_relationship()))
    results.append(("NEXT_MESSAGE Relationships", test_next_message_relationships()))
    results.append(("Message Traversal", test_message_traversal()))
    
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

