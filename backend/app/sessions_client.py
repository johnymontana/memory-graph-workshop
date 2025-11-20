"""Neo4j client for managing conversation threads/sessions in a separate Neo4j instance."""

import os
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


class SessionsClient:
    """Client for interacting with Neo4j sessions database (separate instance)."""

    def __init__(self):
        """Initialize Neo4j connection to memory database instance."""
        uri = os.getenv("MEMORY_NEO4J_URI")
        username = os.getenv("MEMORY_NEO4J_USERNAME", "neo4j")
        password = os.getenv("MEMORY_NEO4J_PASSWORD", "password")

        if not uri:
            raise ValueError(
                "MEMORY_NEO4J_URI environment variable is required for sessions client. "
                "Set this to use a separate Neo4j instance for memory/sessions features."
            )

        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self._initialize_schema()
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        print(f"✓ Sessions client initialized using memory Neo4j instance at: {uri}")

    def close(self):
        """Close the database connection."""
        self.driver.close()

    def _initialize_schema(self):
        """Create indexes and constraints for the sessions database."""
        try:
            with self.driver.session() as session:
                try:
                    # Create constraint for Thread id (unique)
                    session.run(
                        "CREATE CONSTRAINT thread_id_unique IF NOT EXISTS "
                        "FOR (t:Thread) REQUIRE t.id IS UNIQUE"
                    )
                    
                    # Create index for Thread last_message_at
                    session.run(
                        "CREATE INDEX thread_last_message_idx IF NOT EXISTS "
                        "FOR (t:Thread) ON (t.last_message_at)"
                    )
                    
                    # Create constraint for Message id (unique)
                    session.run(
                        "CREATE CONSTRAINT message_id_unique IF NOT EXISTS "
                        "FOR (m:Message) REQUIRE m.id IS UNIQUE"
                    )
                    
                    # Create index for Message thread_id
                    session.run(
                        "CREATE INDEX message_thread_idx IF NOT EXISTS "
                        "FOR (m:Message) ON (m.thread_id)"
                    )
                    
                    # Create index for Message timestamp
                    session.run(
                        "CREATE INDEX message_timestamp_idx IF NOT EXISTS "
                        "FOR (m:Message) ON (m.timestamp)"
                    )
                    
                    print(f"✓ Sessions schema initialized in memory database")
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" in error_msg or "equivalent" in error_msg:
                        print(f"✓ Sessions schema already exists in memory database")
                    else:
                        print(f"⚠️  Schema initialization warning: {e}")
        except Exception as e:
            print(f"⚠️  Could not initialize sessions schema: {e}")
            print(f"   Sessions may not work correctly until schema is created")

    def create_thread(self, title: Optional[str] = None) -> str:
        """
        Create a new conversation thread.
        
        Args:
            title: Optional title for the thread (default: "New Conversation")
            
        Returns:
            The ID of the created thread
        """
        thread_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        if title is None:
            title = "New Conversation"
        
        with self.driver.session() as session:
            session.run(
                """
                CREATE (t:Thread {
                    id: $id,
                    title: $title,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at),
                    last_message_at: datetime($last_message_at)
                })
                RETURN t.id as id
                """,
                {
                    "id": thread_id,
                    "title": title,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "last_message_at": now.isoformat()
                }
            )
        
        return thread_id

    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a thread with all its messages.
        
        Args:
            thread_id: ID of the thread
            
        Returns:
            Thread data with messages, or None if not found
        """
        with self.driver.session() as session:
            # Get thread info
            thread_result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})
                RETURN t.id as id,
                       t.title as title,
                       t.created_at as created_at,
                       t.updated_at as updated_at,
                       t.last_message_at as last_message_at
                """,
                {"thread_id": thread_id}
            )
            
            thread_record = thread_result.single()
            if not thread_record:
                return None
            
            # Get messages
            messages_result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})-[:HAS_MESSAGE]->(m:Message)
                RETURN m.id as id,
                       m.text as text,
                       m.sender as sender,
                       m.timestamp as timestamp,
                       m.reasoning_steps as reasoning_steps,
                       m.agent_context as agent_context
                ORDER BY m.timestamp ASC
                """,
                {"thread_id": thread_id}
            )
            
            messages = []
            for msg_record in messages_result:
                # Parse reasoning steps from JSON
                reasoning_steps = None
                if msg_record["reasoning_steps"]:
                    try:
                        reasoning_steps = json.loads(msg_record["reasoning_steps"])
                    except:
                        reasoning_steps = None
                
                # Parse agent context from JSON
                agent_context = None
                if msg_record["agent_context"]:
                    try:
                        agent_context = json.loads(msg_record["agent_context"])
                    except:
                        agent_context = None
                
                messages.append({
                    "id": msg_record["id"],
                    "text": msg_record["text"],
                    "sender": msg_record["sender"],
                    "timestamp": str(msg_record["timestamp"]) if msg_record["timestamp"] else None,
                    "reasoning_steps": reasoning_steps,
                    "agent_context": agent_context
                })
            
            return {
                "id": thread_record["id"],
                "title": thread_record["title"],
                "created_at": str(thread_record["created_at"]) if thread_record["created_at"] else None,
                "updated_at": str(thread_record["updated_at"]) if thread_record["updated_at"] else None,
                "last_message_at": str(thread_record["last_message_at"]) if thread_record["last_message_at"] else None,
                "messages": messages,
                "message_count": len(messages)
            }

    def list_threads(self) -> List[Dict[str, Any]]:
        """
        Get all threads sorted by last message time.
        
        Returns:
            List of threads with basic info
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread)
                OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
                WITH t, count(m) as message_count
                RETURN t.id as id,
                       t.title as title,
                       t.created_at as created_at,
                       t.updated_at as updated_at,
                       t.last_message_at as last_message_at,
                       message_count
                ORDER BY t.last_message_at DESC
                """
            )
            
            threads = []
            for record in result:
                threads.append({
                    "id": record["id"],
                    "title": record["title"],
                    "created_at": str(record["created_at"]) if record["created_at"] else None,
                    "updated_at": str(record["updated_at"]) if record["updated_at"] else None,
                    "last_message_at": str(record["last_message_at"]) if record["last_message_at"] else None,
                    "message_count": record["message_count"]
                })
            
            return threads

    def update_thread_title(self, thread_id: str, title: str) -> bool:
        """
        Update a thread's title.
        
        Args:
            thread_id: ID of the thread
            title: New title
            
        Returns:
            True if updated, False if not found
        """
        now = datetime.utcnow()
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})
                SET t.title = $title,
                    t.updated_at = datetime($updated_at)
                RETURN t.id as id
                """,
                {
                    "thread_id": thread_id,
                    "title": title,
                    "updated_at": now.isoformat()
                }
            )
            
            return result.single() is not None

    def add_message_to_thread(
        self, 
        thread_id: str, 
        text: str, 
        sender: str,
        reasoning_steps: Optional[List[Dict[str, Any]]] = None,
        agent_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a message to a thread.
        
        Args:
            thread_id: ID of the thread
            text: Message text
            sender: 'user' or 'agent'
            reasoning_steps: Optional list of reasoning steps
            agent_context: Optional agent context information
            
        Returns:
            The ID of the created message
        """
        message_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Serialize reasoning steps to JSON
        reasoning_steps_json = None
        if reasoning_steps:
            try:
                reasoning_steps_json = json.dumps(reasoning_steps)
            except:
                reasoning_steps_json = None
        
        # Serialize agent context to JSON
        agent_context_json = None
        if agent_context:
            try:
                agent_context_json = json.dumps(agent_context)
            except:
                agent_context_json = None
        
        with self.driver.session() as session:
            # Create the message and establish relationships
            # This query will:
            # 1. Create the message node
            # 2. Create HAS_MESSAGE relationship from thread to message
            # 3. If this is the first message, create FIRST_MESSAGE relationship
            # 4. If there's a previous message, create NEXT_MESSAGE from previous to current
            session.run(
                """
                MATCH (t:Thread {id: $thread_id})
                
                // Get the last message in the thread (if any)
                OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(prev:Message)
                WITH t, prev
                ORDER BY prev.timestamp DESC
                LIMIT 1
                
                // Create the new message
                CREATE (m:Message {
                    id: $message_id,
                    thread_id: $thread_id,
                    text: $text,
                    sender: $sender,
                    timestamp: datetime($timestamp),
                    reasoning_steps: $reasoning_steps,
                    agent_context: $agent_context
                })
                
                // Create HAS_MESSAGE relationship
                CREATE (t)-[:HAS_MESSAGE]->(m)
                
                // Create FIRST_MESSAGE if this is the first message
                FOREACH (_ IN CASE WHEN prev IS NULL THEN [1] ELSE [] END |
                    CREATE (t)-[:FIRST_MESSAGE]->(m)
                )
                
                // Create NEXT_MESSAGE from previous message to current
                FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
                    CREATE (prev)-[:NEXT_MESSAGE]->(m)
                )
                
                // Update thread timestamps
                SET t.updated_at = datetime($timestamp),
                    t.last_message_at = datetime($timestamp)
                
                RETURN m.id as id
                """,
                {
                    "thread_id": thread_id,
                    "message_id": message_id,
                    "text": text,
                    "sender": sender,
                    "timestamp": now.isoformat(),
                    "reasoning_steps": reasoning_steps_json,
                    "agent_context": agent_context_json
                }
            )
        
        return message_id

    def delete_thread(self, thread_id: str) -> bool:
        """
        Delete a thread and all its messages.
        
        Args:
            thread_id: ID of the thread
            
        Returns:
            True if deleted, False if not found
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread {id: $thread_id})
                OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
                DETACH DELETE t, m
                RETURN count(t) as deleted_count
                """,
                {"thread_id": thread_id}
            )
            
            record = result.single()
            return record["deleted_count"] > 0 if record else False

    def get_last_active_thread(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recently updated thread.
        
        Returns:
            Thread data or None if no threads exist
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Thread)
                OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
                WITH t, count(m) as message_count
                RETURN t.id as id,
                       t.title as title,
                       t.created_at as created_at,
                       t.updated_at as updated_at,
                       t.last_message_at as last_message_at,
                       message_count
                ORDER BY t.last_message_at DESC
                LIMIT 1
                """
            )
            
            record = result.single()
            if not record:
                return None
            
            return {
                "id": record["id"],
                "title": record["title"],
                "created_at": str(record["created_at"]) if record["created_at"] else None,
                "updated_at": str(record["updated_at"]) if record["updated_at"] else None,
                "last_message_at": str(record["last_message_at"]) if record["last_message_at"] else None,
                "message_count": record["message_count"]
            }

    async def generate_thread_title(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate a descriptive title for a thread based on its messages.
        
        Args:
            messages: List of message dictionaries with 'sender' and 'text'
            
        Returns:
            Generated title (3-5 words)
        """
        if not messages:
            return "New Conversation"
        
        # Use first few messages for context
        context_messages = messages[:4]
        conversation_text = "\n".join([
            f"{msg.get('sender', 'unknown').capitalize()}: {msg.get('text', '')}"
            for msg in context_messages
        ])
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise, descriptive titles for conversations. Generate a title that is 3-5 words long and captures the main topic. Do not use quotes or punctuation in the title."
                    },
                    {
                        "role": "user",
                        "content": f"Create a short title (3-5 words) for this conversation:\n\n{conversation_text}"
                    }
                ],
                temperature=0.7,
                max_tokens=20
            )
            
            title = response.choices[0].message.content.strip()
            # Remove quotes if present
            title = title.strip('"').strip("'")
            # Limit length
            if len(title) > 50:
                title = title[:50]
            
            return title
            
        except Exception as e:
            print(f"Error generating thread title: {e}")
            return "New Conversation"

