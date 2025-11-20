"""Neo4j client for managing procedural memory (reasoning steps and tool calls) in a separate Neo4j instance."""

import os
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


class ProceduralMemoryClient:
    """Client for interacting with Neo4j procedural memory database (separate instance)."""

    def __init__(self):
        """Initialize Neo4j connection to memory database instance."""
        uri = os.getenv("MEMORY_NEO4J_URI")
        username = os.getenv("MEMORY_NEO4J_USERNAME", "neo4j")
        password = os.getenv("MEMORY_NEO4J_PASSWORD", "password")

        if not uri:
            raise ValueError(
                "MEMORY_NEO4J_URI environment variable is required for procedural memory client. "
                "Set this to use a separate Neo4j instance for memory/procedural features."
            )

        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self._initialize_schema()
        
        print(f"✓ Procedural memory client initialized using memory Neo4j instance at: {uri}")

    def close(self):
        """Close the database connection."""
        self.driver.close()

    def _initialize_schema(self):
        """Create indexes and constraints for the procedural memory database."""
        try:
            with self.driver.session() as session:
                try:
                    # Create constraint for Tool name (unique)
                    session.run(
                        "CREATE CONSTRAINT tool_name_unique IF NOT EXISTS "
                        "FOR (t:Tool) REQUIRE t.name IS UNIQUE"
                    )
                    
                    # Create constraint for ReasoningStep id (unique)
                    session.run(
                        "CREATE CONSTRAINT reasoning_step_id_unique IF NOT EXISTS "
                        "FOR (r:ReasoningStep) REQUIRE r.id IS UNIQUE"
                    )
                    
                    # Create constraint for ToolCall id (unique)
                    session.run(
                        "CREATE CONSTRAINT tool_call_id_unique IF NOT EXISTS "
                        "FOR (tc:ToolCall) REQUIRE tc.id IS UNIQUE"
                    )
                    
                    # Create index for ReasoningStep message_id
                    session.run(
                        "CREATE INDEX reasoning_step_message_idx IF NOT EXISTS "
                        "FOR (r:ReasoningStep) ON (r.message_id)"
                    )
                    
                    # Create index for ReasoningStep thread_id
                    session.run(
                        "CREATE INDEX reasoning_step_thread_idx IF NOT EXISTS "
                        "FOR (r:ReasoningStep) ON (r.thread_id)"
                    )
                    
                    # Create index for ToolCall step_id
                    session.run(
                        "CREATE INDEX tool_call_step_idx IF NOT EXISTS "
                        "FOR (tc:ToolCall) ON (tc.step_id)"
                    )
                    
                    print(f"✓ Procedural memory schema initialized in memory database")
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" in error_msg or "equivalent" in error_msg:
                        print(f"✓ Procedural memory schema already exists in memory database")
                    else:
                        print(f"⚠️  Schema initialization warning: {e}")
        except Exception as e:
            print(f"⚠️  Could not initialize procedural memory schema: {e}")
            print(f"   Procedural memory may not work correctly until schema is created")

    def get_or_create_tool(self, tool_name: str, description: Optional[str] = None) -> str:
        """
        Get or create a canonical Tool node.
        
        Args:
            tool_name: Name of the tool
            description: Optional description of the tool
            
        Returns:
            The name of the tool (which serves as its ID)
        """
        now = datetime.utcnow()
        
        with self.driver.session() as session:
            result = session.run(
                """
                MERGE (t:Tool {name: $name})
                ON CREATE SET 
                    t.description = $description,
                    t.created_at = datetime($created_at),
                    t.last_used_at = datetime($last_used_at),
                    t.usage_count = 1
                ON MATCH SET
                    t.last_used_at = datetime($last_used_at),
                    t.usage_count = COALESCE(t.usage_count, 0) + 1
                RETURN t.name as name
                """,
                {
                    "name": tool_name,
                    "description": description or f"Tool: {tool_name}",
                    "created_at": now.isoformat(),
                    "last_used_at": now.isoformat()
                }
            )
            
            record = result.single()
            return record["name"] if record else tool_name

    def store_tool_call(
        self,
        step_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        output: Any,
        tool_description: Optional[str] = None
    ) -> str:
        """
        Store a tool call and link it to its canonical Tool node.
        
        Args:
            step_id: ID of the ReasoningStep this tool call belongs to
            tool_name: Name of the tool being called
            arguments: Tool call arguments
            output: Tool call output/result
            tool_description: Optional description of the tool
            
        Returns:
            The ID of the created ToolCall node
        """
        tool_call_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Ensure canonical Tool exists
        self.get_or_create_tool(tool_name, tool_description)
        
        # Serialize arguments and output to JSON strings
        arguments_json = json.dumps(arguments) if arguments else None
        output_json = json.dumps(output) if output is not None else None
        
        with self.driver.session() as session:
            session.run(
                """
                MATCH (r:ReasoningStep {id: $step_id})
                MATCH (t:Tool {name: $tool_name})
                CREATE (tc:ToolCall {
                    id: $tool_call_id,
                    step_id: $step_id,
                    timestamp: datetime($timestamp),
                    arguments: $arguments,
                    output: $output
                })
                CREATE (r)-[:USES_TOOL]->(tc)
                CREATE (tc)-[:INSTANCE_OF]->(t)
                RETURN tc.id as id
                """,
                {
                    "step_id": step_id,
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "timestamp": now.isoformat(),
                    "arguments": arguments_json,
                    "output": output_json
                }
            )
        
        return tool_call_id

    def store_reasoning_steps(
        self,
        message_id: str,
        thread_id: str,
        reasoning_steps: List[Dict[str, Any]]
    ) -> int:
        """
        Store reasoning steps and tool calls for a message, creating a tree structure.
        
        Args:
            message_id: ID of the Message node this reasoning belongs to
            thread_id: ID of the Thread
            reasoning_steps: List of reasoning step dictionaries with structure:
                {
                    "step_number": int,
                    "reasoning": str (optional),
                    "tool_calls": [
                        {
                            "name": str,
                            "arguments": dict,
                            "output": any
                        }
                    ]
                }
                
        Returns:
            Number of reasoning steps stored
        """
        if not reasoning_steps:
            return 0
        
        stored_count = 0
        previous_step_id = None
        
        for step_data in reasoning_steps:
            try:
                step_id = str(uuid.uuid4())
                now = datetime.utcnow()
                
                step_number = step_data.get("step_number", 0)
                reasoning_text = step_data.get("reasoning", "")
                tool_calls = step_data.get("tool_calls", [])
                
                # Create ReasoningStep node and link to Message
                with self.driver.session() as session:
                    session.run(
                        """
                        MATCH (m:Message {id: $message_id})
                        CREATE (r:ReasoningStep {
                            id: $step_id,
                            step_number: $step_number,
                            reasoning_text: $reasoning_text,
                            timestamp: datetime($timestamp),
                            message_id: $message_id,
                            thread_id: $thread_id
                        })
                        CREATE (m)-[:HAS_REASONING_STEP]->(r)
                        RETURN r.id as id
                        """,
                        {
                            "message_id": message_id,
                            "step_id": step_id,
                            "step_number": step_number,
                            "reasoning_text": reasoning_text or "",
                            "timestamp": now.isoformat(),
                            "thread_id": thread_id
                        }
                    )
                
                # Link to previous step if exists (sequential flow)
                if previous_step_id:
                    with self.driver.session() as session:
                        session.run(
                            """
                            MATCH (prev:ReasoningStep {id: $prev_id})
                            MATCH (curr:ReasoningStep {id: $curr_id})
                            CREATE (prev)-[:NEXT_STEP]->(curr)
                            """,
                            {
                                "prev_id": previous_step_id,
                                "curr_id": step_id
                            }
                        )
                
                # Store tool calls for this step (supports multiple for parallel calls)
                for tool_call_data in tool_calls:
                    try:
                        tool_name = tool_call_data.get("name", "unknown_tool")
                        arguments = tool_call_data.get("arguments", {})
                        output = tool_call_data.get("output")
                        
                        self.store_tool_call(
                            step_id=step_id,
                            tool_name=tool_name,
                            arguments=arguments,
                            output=output
                        )
                    except Exception as tc_err:
                        print(f"Warning: Failed to store tool call {tool_name}: {tc_err}")
                
                stored_count += 1
                previous_step_id = step_id
                
            except Exception as step_err:
                print(f"Warning: Failed to store reasoning step {step_data.get('step_number', '?')}: {step_err}")
        
        return stored_count

    def get_reasoning_steps_for_message(self, message_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all reasoning steps for a message in order.
        
        Args:
            message_id: ID of the message
            
        Returns:
            List of reasoning step dictionaries with tool calls
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (m:Message {id: $message_id})-[:HAS_REASONING_STEP]->(r:ReasoningStep)
                OPTIONAL MATCH (r)-[:USES_TOOL]->(tc:ToolCall)-[:INSTANCE_OF]->(t:Tool)
                WITH r, 
                     collect({
                         id: tc.id,
                         tool_name: t.name,
                         arguments: tc.arguments,
                         output: tc.output,
                         timestamp: tc.timestamp
                     }) as tool_calls
                RETURN r.id as id,
                       r.step_number as step_number,
                       r.reasoning_text as reasoning_text,
                       r.timestamp as timestamp,
                       tool_calls
                ORDER BY r.step_number ASC
                """,
                {"message_id": message_id}
            )
            
            steps = []
            for record in result:
                # Parse JSON strings back to objects
                tool_calls = []
                for tc in record["tool_calls"]:
                    if tc["id"]:  # Only include if tool call exists
                        tool_call = {
                            "id": tc["id"],
                            "tool_name": tc["tool_name"],
                            "timestamp": str(tc["timestamp"]) if tc["timestamp"] else None
                        }
                        
                        # Parse JSON arguments and output
                        if tc["arguments"]:
                            try:
                                tool_call["arguments"] = json.loads(tc["arguments"])
                            except:
                                tool_call["arguments"] = tc["arguments"]
                        else:
                            tool_call["arguments"] = {}
                        
                        if tc["output"]:
                            try:
                                tool_call["output"] = json.loads(tc["output"])
                            except:
                                tool_call["output"] = tc["output"]
                        else:
                            tool_call["output"] = None
                        
                        tool_calls.append(tool_call)
                
                steps.append({
                    "id": record["id"],
                    "step_number": record["step_number"],
                    "reasoning_text": record["reasoning_text"],
                    "timestamp": str(record["timestamp"]) if record["timestamp"] else None,
                    "tool_calls": tool_calls
                })
            
            return steps

    def get_tool_usage_stats(self) -> List[Dict[str, Any]]:
        """
        Get usage statistics for all tools.
        
        Returns:
            List of tool statistics
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Tool)
                RETURN t.name as name,
                       t.description as description,
                       t.usage_count as usage_count,
                       t.created_at as created_at,
                       t.last_used_at as last_used_at
                ORDER BY t.usage_count DESC
                """
            )
            
            tools = []
            for record in result:
                tools.append({
                    "name": record["name"],
                    "description": record["description"],
                    "usage_count": record["usage_count"] or 0,
                    "created_at": str(record["created_at"]) if record["created_at"] else None,
                    "last_used_at": str(record["last_used_at"]) if record["last_used_at"] else None
                })
            
            return tools

