"""FastAPI backend server for the news chat agent."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple, Union
import os
import json

from .agent import news_agent, NewsDependencies, create_agent_with_preferences, OPENAI_MODEL
from .neo4j_client import Neo4jClient
from .preferences_client import PreferencesClient
from .memory_provider import Neo4jMemoryProvider
from .sessions_client import SessionsClient

app = FastAPI(title="News Chat Agent API")

# Configure CORS to allow any domain by default, while still supporting an override list
allowed_origins_env = os.getenv("CORS_ALLOW_ORIGINS")
if allowed_origins_env:
    allowed_origins_list = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    cors_config = dict(
        allow_origins=allowed_origins_list,
        allow_credentials=True,
    )
else:
    cors_config = dict(
        allow_origins=["*"],
        allow_credentials=False,
    )

app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],
    allow_headers=["*"],
    **cors_config,
)

# Initialize Neo4j clients
neo4j_client = Neo4jClient()

# Initialize memory clients (preferences, sessions, procedural) only if memory Neo4j instance is configured
memory_neo4j_uri = os.getenv("MEMORY_NEO4J_URI")
preferences_client = None
memory_provider = None
sessions_client = None
procedural_memory_client = None

if memory_neo4j_uri:
    print(f"Memory Neo4j instance configured at: {memory_neo4j_uri}")
    # Initialize preferences client
    try:
        preferences_client = PreferencesClient()
        memory_provider = Neo4jMemoryProvider(preferences_client)
        print("✓ Memory and preferences features enabled")
    except Exception as e:
        print(f"⚠️  Error initializing preferences system: {e}")
        print("   The application will start but memory features will not work.")
        preferences_client = None
        memory_provider = None

    # Initialize sessions client for thread management
    try:
        sessions_client = SessionsClient()
        print("✓ Sessions/thread management enabled")
    except Exception as e:
        print(f"⚠️  Error initializing sessions system: {e}")
        print("   The application will start but thread features will not work.")
        sessions_client = None
    
    # Initialize procedural memory client for reasoning steps and tool calls
    try:
        from .procedural_memory_client import ProceduralMemoryClient
        procedural_memory_client = ProceduralMemoryClient()
        print("✓ Procedural memory enabled")
    except Exception as e:
        print(f"⚠️  Error initializing procedural memory system: {e}")
        print("   The application will start but procedural memory features will not work.")
        procedural_memory_client = None
else:
    print("⚠️  MEMORY_NEO4J_URI not set - memory and preferences features are DISABLED")
    print("   Set MEMORY_NEO4J_URI to enable user preferences and conversation threads")


class ChatMessage(BaseModel):
    """Model for chat messages."""
    message: str
    memory_enabled: bool = False
    thread_id: Optional[str] = None


class ToolCall(BaseModel):
    """Model for tool call information."""
    name: str
    arguments: Dict[str, Any]
    output: Any


class ReasoningStep(BaseModel):
    """Model for a reasoning step."""
    step_number: int
    reasoning: Optional[str] = None
    tool_calls: List[ToolCall] = []


class AgentContext(BaseModel):
    """Model for agent context information."""
    system_prompt: str
    memory_enabled: bool
    preferences_applied: Optional[str] = None
    model: str
    available_tools: List[str] = []


class ChatResponse(BaseModel):
    """Model for chat responses."""
    response: str
    reasoning_steps: List[ReasoningStep] = []
    agent_context: Optional[AgentContext] = None
    thread_id: Optional[str] = None
    reasoning_iterations: int = 1
    retries_performed: List[Dict[str, Any]] = []


class ThreadInfo(BaseModel):
    """Model for basic thread information."""
    id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_message_at: Optional[str] = None
    message_count: int = 0


class ThreadDetail(BaseModel):
    """Model for detailed thread with messages."""
    id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_message_at: Optional[str] = None
    messages: List[Dict[str, Any]] = []
    message_count: int = 0


class ThreadCreateRequest(BaseModel):
    """Model for creating a thread."""
    title: Optional[str] = None


class ThreadUpdateRequest(BaseModel):
    """Model for updating a thread title."""
    title: str


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    print("Starting News Chat Agent API...")
    print(f"Neo4j URI: {os.getenv('NEO4J_URI', 'bolt://localhost:7687')}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    neo4j_client.close()
    if preferences_client:
        preferences_client.close()
    if sessions_client:
        sessions_client.close()
    if procedural_memory_client:
        procedural_memory_client.close()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "News Chat Agent API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def serialize_value(value: Any) -> Any:
    """Serialize a value to be JSON-serializable."""
    try:
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, (list, tuple)):
            return [serialize_value(item) for item in value]
        elif isinstance(value, dict):
            return {str(k): serialize_value(v) for k, v in value.items()}
        else:
            # Try to convert to string or JSON
            try:
                return json.loads(json.dumps(value, default=str))
            except:
                return str(value)
    except Exception:
        return str(value)


def extract_reasoning_and_tool_calls(result) -> List[ReasoningStep]:
    """Extract reasoning steps and tool calls from pydantic-ai run result."""
    reasoning_steps = []
    step_number = 0
    
    try:
        print("=" * 80)
        print("EXTRACTING REASONING AND TOOL CALLS")
        print("=" * 80)
        
        # Log result structure
        print(f"Result type: {type(result)}")
        result_attrs = [attr for attr in dir(result) if not attr.startswith('_')]
        print(f"Result attributes: {result_attrs}")
        
        # Try multiple ways to access the run and messages
        messages = []
        run = None
        
        # Method 1: Direct access to run
        if hasattr(result, 'run'):
            run = result.run
            print(f"✓ Found run attribute: {type(run)}")
            run_attrs = [attr for attr in dir(run) if not attr.startswith('_')]
            print(f"Run attributes: {run_attrs}")
        
        # Method 2: Try to get conversation from run
        if run:
            # Check for conversation
            if hasattr(run, 'conversation'):
                conversation = run.conversation
                print(f"✓ Found conversation: {type(conversation)}")
                conv_attrs = [attr for attr in dir(conversation) if not attr.startswith('_')]
                print(f"Conversation attributes: {conv_attrs}")
                
                # Try to get messages from conversation
                if hasattr(conversation, 'all_messages'):
                    try:
                        messages = list(conversation.all_messages())
                        print(f"✓ Got {len(messages)} messages from conversation.all_messages()")
                    except Exception as e:
                        print(f"✗ Error calling conversation.all_messages(): {e}")
                
                if not messages and hasattr(conversation, 'messages'):
                    try:
                        msgs = conversation.messages
                        if msgs:
                            messages = list(msgs) if hasattr(msgs, '__iter__') else [msgs]
                            print(f"✓ Got {len(messages)} messages from conversation.messages")
                    except Exception as e:
                        print(f"✗ Error accessing conversation.messages: {e}")
                
                if not messages and hasattr(conversation, 'message_history'):
                    try:
                        msgs = conversation.message_history
                        if msgs:
                            messages = list(msgs) if hasattr(msgs, '__iter__') else [msgs]
                            print(f"✓ Got {len(messages)} messages from conversation.message_history")
                    except Exception as e:
                        print(f"✗ Error accessing conversation.message_history: {e}")
            
            # Try direct access to messages on run
            if not messages and hasattr(run, 'all_messages'):
                try:
                    messages = list(run.all_messages())
                    print(f"✓ Got {len(messages)} messages from run.all_messages()")
                except Exception as e:
                    print(f"✗ Error calling run.all_messages(): {e}")
            
            if not messages and hasattr(run, 'messages'):
                try:
                    msgs = run.messages
                    if msgs:
                        messages = list(msgs) if hasattr(msgs, '__iter__') else [msgs]
                        print(f"✓ Got {len(messages)} messages from run.messages")
                except Exception as e:
                    print(f"✗ Error accessing run.messages: {e}")
        
        # Method 3: Try result.all_messages() directly
        if not messages and hasattr(result, 'all_messages'):
            try:
                messages = list(result.all_messages())
                print(f"✓ Got {len(messages)} messages from result.all_messages()")
            except Exception as e:
                print(f"✗ Error calling result.all_messages(): {e}")
        
        # Method 4: Try to access data or history
        if not messages:
            for attr in ['data', 'history', 'conversation_history', 'message_history']:
                if hasattr(result, attr):
                    try:
                        data = getattr(result, attr)
                        print(f"Found {attr}: {type(data)}")
                        if isinstance(data, (list, tuple)):
                            messages = list(data)
                            print(f"✓ Using {attr} as messages: {len(messages)} items")
                            break
                    except Exception as e:
                        print(f"✗ Error accessing {attr}: {e}")
        
        if not messages:
            print("✗ WARNING: No messages found in result using any method")
            print(f"Result output: {result.output[:200] if result.output else 'None'}...")
            
            # Last resort: try to inspect the result's internal structure
            if hasattr(result, '__dict__'):
                print(f"Result __dict__ keys: {list(result.__dict__.keys())}")
            if run and hasattr(run, '__dict__'):
                print(f"Run __dict__ keys: {list(run.__dict__.keys())}")
            
            return reasoning_steps
        
        print(f"\nProcessing {len(messages)} messages...")
        
        # Track tool calls and their results by tool_use_id
        tool_call_map = {}  # Maps tool_use_id to tool call info
        
        # First pass: Collect all tool calls and their results from all messages
        for msg_idx, msg in enumerate(messages):
            role = getattr(msg, 'role', None)
            if not role:
                continue
            
            content = getattr(msg, 'content', None)
            if not content:
                continue
            
            # Handle tool result messages (role='tool')
            if role == 'tool':
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'tool_result':
                            tool_use_id = block.get('tool_use_id', '')
                            tool_content = block.get('content', '')
                            if tool_use_id:
                                tool_call_map[tool_use_id] = {
                                    'output': tool_content,
                                    'name': None,  # Will be filled from tool_use
                                    'arguments': None
                                }
                                print(f"Found tool_result for id {tool_use_id} in message {msg_idx}")
        
        # Second pass: Process assistant messages and extract tool calls and reasoning
        for msg_idx, msg in enumerate(messages):
            print(f"\n--- Message {msg_idx} ---")
            print(f"Message type: {type(msg)}")
            print(f"Message attributes: {[attr for attr in dir(msg) if not attr.startswith('_')]}")
            
            # Get message role
            role = getattr(msg, 'role', None)
            if not role:
                # Try to get role from message content
                if hasattr(msg, 'content'):
                    content = msg.content
                    if isinstance(content, str):
                        # Try to infer role from message structure
                        role = 'assistant'  # Default assumption
                else:
                    continue
            
            print(f"Message role: {role}")
            
            # Skip user messages for reasoning steps (but log them)
            if role == 'user':
                user_content = getattr(msg, 'content', '')
                print(f"User message: {user_content[:100]}...")
                continue
            
            # Skip tool messages (we already processed them)
            if role == 'tool':
                continue
            
            # Check for tool_calls attribute directly on the message
            tool_calls_attr = getattr(msg, 'tool_calls', None)
            if tool_calls_attr:
                print(f"Found tool_calls attribute on message: {tool_calls_attr}")
            
            # Get message content
            content = getattr(msg, 'content', None)
            if content is None:
                # If no content but has tool_calls, create a step for tool calls
                if tool_calls_attr:
                    step_number += 1
                    step = ReasoningStep(step_number=step_number, reasoning="Agent invoked tools.")
                    for tc_attr in tool_calls_attr:
                        tool_name = getattr(tc_attr, 'name', '') or getattr(tc_attr, 'function', {}).get('name', '')
                        tool_args = getattr(tc_attr, 'arguments', {}) or getattr(tc_attr, 'function', {}).get('arguments', {})
                        tool_output = getattr(tc_attr, 'result', None) or getattr(tc_attr, 'output', None)
                        if tool_name:
                            step.tool_calls.append(ToolCall(
                                name=tool_name,
                                arguments=serialize_value(tool_args),
                                output=serialize_value(tool_output)
                            ))
                    if step.tool_calls:
                        reasoning_steps.append(step)
                else:
                    print("No content found in message")
                continue
            
            print(f"Content type: {type(content)}")
            
            # Handle different content formats
            if isinstance(content, str):
                print(f"String content: {content[:200]}...")
                step_number += 1
                step = ReasoningStep(
                    step_number=step_number,
                    reasoning=content,
                    tool_calls=[]
                )
                reasoning_steps.append(step)
                
            elif isinstance(content, list):
                print(f"List content with {len(content)} blocks")
                step_number += 1
                step = ReasoningStep(step_number=step_number)
                reasoning_parts = []
                tool_calls_in_step = []
                
                # If message has tool_calls attribute, add them first
                if tool_calls_attr:
                    print(f"Processing {len(tool_calls_attr)} tool calls from message attribute")
                    for tc_attr in tool_calls_attr:
                        tool_name = getattr(tc_attr, 'name', '') or (getattr(tc_attr, 'function', None) and getattr(tc_attr.function, 'name', ''))
                        if not tool_name and isinstance(tc_attr, dict):
                            tool_name = tc_attr.get('name', '') or tc_attr.get('function', {}).get('name', '')
                        
                        tool_args = getattr(tc_attr, 'arguments', {}) or (getattr(tc_attr, 'function', None) and getattr(tc_attr.function, 'arguments', {}))
                        if not tool_args and isinstance(tc_attr, dict):
                            tool_args = tc_attr.get('arguments', {}) or tc_attr.get('function', {}).get('arguments', {})
                        
                        tool_output = getattr(tc_attr, 'result', None) or getattr(tc_attr, 'output', None)
                        if not tool_output and isinstance(tc_attr, dict):
                            tool_output = tc_attr.get('result') or tc_attr.get('output')
                        
                        if tool_name:
                            tool_calls_in_step.append(ToolCall(
                                name=tool_name,
                                arguments=serialize_value(tool_args),
                                output=serialize_value(tool_output)
                            ))
                            print(f"  Added tool call from attribute: {tool_name}")
                
                # Process each content block
                for block_idx, block in enumerate(content):
                    print(f"  Block {block_idx}: type={type(block)}")
                    
                    # Handle dict blocks (Anthropic-style)
                    if isinstance(block, dict):
                        block_type = block.get('type', '')
                        print(f"    Block type: {block_type}")
                        
                        if block_type == 'text':
                            text = block.get('text', '')
                            if text:
                                reasoning_parts.append(text)
                                print(f"    Text: {text[:100]}...")
                        
                        elif block_type == 'tool_use':
                            tool_use_id = block.get('id', '')
                            tool_name = block.get('name', '')
                            tool_input = block.get('input', {})
                            
                            print(f"    Tool use: {tool_name} (id: {tool_use_id})")
                            print(f"    Tool input: {tool_input}")
                            
                            # Get output if we already found it in tool result messages
                            tool_output = None
                            if tool_use_id in tool_call_map:
                                tool_call_map[tool_use_id]['name'] = tool_name
                                tool_call_map[tool_use_id]['arguments'] = tool_input
                                tool_output = tool_call_map[tool_use_id].get('output')
                            else:
                                # Store for potential later matching
                                tool_call_map[tool_use_id] = {
                                    'name': tool_name,
                                    'arguments': tool_input,
                                    'output': None
                                }
                            
                            tool_calls_in_step.append(ToolCall(
                                name=tool_name,
                                arguments=serialize_value(tool_input),
                                output=serialize_value(tool_output) if tool_output is not None else None
                            ))
                            
                            if tool_output is not None:
                                print(f"    Tool output found: {str(tool_output)[:200]}...")
                        
                        elif block_type == 'tool_result':
                            # Tool results in the same message (shouldn't happen but handle it)
                            tool_use_id = block.get('tool_use_id', '')
                            tool_content = block.get('content', '')
                            
                            print(f"    Tool result in same message for id: {tool_use_id}")
                            
                            if tool_use_id in tool_call_map:
                                tool_call_map[tool_use_id]['output'] = tool_content
                                # Update the tool call in the step
                                for tc in tool_calls_in_step:
                                    if tc.name == tool_call_map[tool_use_id].get('name'):
                                        tc.output = serialize_value(tool_content)
                                        break
                    
                    # Handle object-based blocks
                    elif hasattr(block, 'type'):
                        block_type = getattr(block, 'type', '')
                        print(f"    Object block type: {block_type}")
                        
                        if block_type == 'text':
                            text = getattr(block, 'text', '')
                            if text:
                                reasoning_parts.append(text)
                        
                        elif block_type == 'tool_use':
                            tool_use_id = getattr(block, 'id', '')
                            tool_name = getattr(block, 'name', '')
                            tool_input = getattr(block, 'input', {})
                            
                            tool_calls_in_step.append(ToolCall(
                                name=tool_name,
                                arguments=serialize_value(tool_input),
                                output=None
                            ))
                    
                    # Handle string blocks
                    elif isinstance(block, str):
                        reasoning_parts.append(block)
                        print(f"    String block: {block[:100]}...")
                
                # Set reasoning if we have any
                if reasoning_parts:
                    step.reasoning = '\n'.join(reasoning_parts)
                    print(f"  Reasoning: {step.reasoning[:200]}...")
                
                # Update tool call outputs from the map (in case we missed any)
                for tc in tool_calls_in_step:
                    # Try to find matching tool call by name and update output
                    for tool_use_id, tool_info in tool_call_map.items():
                        if tool_info.get('name') == tc.name and tool_info.get('output') is not None:
                            if tc.output is None:
                                tc.output = serialize_value(tool_info['output'])
                                print(f"  Updated tool call {tc.name} with output from map")
                            break
                
                step.tool_calls = tool_calls_in_step
                print(f"  Tool calls: {len(step.tool_calls)}")
                
                # Only add step if it has content
                if step.reasoning or step.tool_calls:
                    reasoning_steps.append(step)
                    print(f"  Added step {step_number} with {len(step.tool_calls)} tool calls")
            
            else:
                print(f"Unknown content type: {type(content)}")
                # Try to convert to string
                try:
                    content_str = str(content)
                    step_number += 1
                    step = ReasoningStep(
                        step_number=step_number,
                        reasoning=content_str[:1000],  # Limit length
                        tool_calls=[]
                    )
                    reasoning_steps.append(step)
                except:
                    pass
        
        print(f"\nExtracted {len(reasoning_steps)} reasoning steps")
        for idx, step in enumerate(reasoning_steps):
            print(f"  Step {idx + 1}: reasoning={bool(step.reasoning)}, tool_calls={len(step.tool_calls)}")
            for tc in step.tool_calls:
                print(f"    Tool: {tc.name}, has_output={tc.output is not None}")
                if tc.output is not None:
                    output_str = str(tc.output)
                    print(f"      Output preview: {output_str[:100]}...")
        
        # If no reasoning steps were extracted but we have tool calls in the map, create a step
        if not reasoning_steps and tool_call_map:
            print("No reasoning steps found, but tool calls exist. Creating step from tool calls...")
            step = ReasoningStep(step_number=1, reasoning="Agent used tools to process the request.")
            for tool_use_id, tool_info in tool_call_map.items():
                if tool_info.get('name'):
                    step.tool_calls.append(ToolCall(
                        name=tool_info['name'],
                        arguments=serialize_value(tool_info.get('arguments', {})),
                        output=serialize_value(tool_info.get('output'))
                    ))
            if step.tool_calls:
                reasoning_steps.append(step)
                print(f"Created step with {len(step.tool_calls)} tool calls")
        
        print("=" * 80)
    
    except Exception as e:
        print(f"ERROR extracting reasoning steps: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return reasoning_steps


# Removed extract_from_stream - using extract_from_stream_events instead


def get_messages_from_result(result: Any) -> List[Any]:
    """Retrieve conversation messages from a pydantic-ai run result."""
    messages: List[Any] = []

    try:
        # Preferred: JSON-friendly messages
        all_messages_json = getattr(result, "all_messages_json", None)
        if callable(all_messages_json):
            try:
                data = all_messages_json()
                if data:
                    messages = list(data)
                    print(f"✓ Retrieved {len(messages)} messages via result.all_messages_json()")
                    if messages:
                        first = messages[0]
                        print(f"First message (json) keys: {list(first.keys()) if isinstance(first, dict) else 'n/a'}")
            except Exception as e:
                print(f"✗ Error calling all_messages_json(): {e}")
                import traceback

                traceback.print_exc()
        elif all_messages_json:
            messages = list(all_messages_json)

        # Fallback: raw message objects
        if not messages:
            all_messages = getattr(result, "all_messages", None)
            if callable(all_messages):
                try:
                    data = all_messages()
                    if data:
                        messages = list(data)
                        print(f"✓ Retrieved {len(messages)} messages via result.all_messages()")
                        if messages:
                            first = messages[0]
                            print(
                                f"First message type: {type(first)}, dir: {[attr for attr in dir(first) if not attr.startswith('_')][:10]}"
                            )
                except Exception as e:
                    print(f"✗ Error calling all_messages(): {e}")
                    import traceback

                    traceback.print_exc()
            elif all_messages:
                messages = list(all_messages)

    except Exception as e:
        print(f"Error retrieving messages from result: {e}")
        import traceback

        traceback.print_exc()

    return messages


def get_message_role(msg: Any) -> Optional[str]:
    """Get role from a message, handling both dict and Pydantic models."""
    # Try as attribute first
    if hasattr(msg, 'role'):
        role = getattr(msg, 'role')
        if role:
            return str(role)
    
    # Try as dict
    if isinstance(msg, dict):
        return msg.get('role')
    
    # Try model_dump if it's a Pydantic model
    if hasattr(msg, 'model_dump'):
        try:
            msg_dict = msg.model_dump()
            return msg_dict.get('role')
        except:
            pass

    # Fallback for pydantic-ai message classes: use kind
    if hasattr(msg, 'kind'):
        kind = getattr(msg, 'kind')
        if kind == 'model_response':
            return 'assistant'
        if kind == 'model_request':
            return 'system'
        if kind == 'tool_result':
            return 'tool'
    
    return None


def get_message_content(msg: Any) -> Any:
    """Get content from a message, handling both dict and Pydantic models."""
    # Try as attribute first
    if hasattr(msg, 'content'):
        return getattr(msg, 'content')
    
    # Try as dict
    if isinstance(msg, dict):
        if 'content' in msg:
            return msg.get('content')
        if 'parts' in msg:
            return msg.get('parts')
        if 'text' in msg:
            return msg.get('text')
    
    # Try model_dump if it's a Pydantic model
    if hasattr(msg, 'model_dump'):
        try:
            msg_dict = msg.model_dump()
            if 'content' in msg_dict:
                return msg_dict.get('content')
            if 'parts' in msg_dict:
                return msg_dict.get('parts')
            if 'text' in msg_dict:
                return msg_dict.get('text')
        except:
            pass

    # For pydantic-ai message classes, `parts` often contain the content
    if hasattr(msg, 'parts'):
        return getattr(msg, 'parts')
    
    return None


def process_messages_to_reasoning_steps(messages: List[Any]) -> List[ReasoningStep]:
    """Process messages to extract reasoning steps and tool calls."""
    reasoning_steps = []
    step_number = 0
    tool_call_map = {}  # Maps tool_use_id to tool call info
    
    print(f"Processing {len(messages)} messages...")
    
    # First pass: collect tool results
    for msg_idx, msg in enumerate(messages):
        role = get_message_role(msg)
        if not role:
            continue
        
        # Collect tool results
        if role == 'tool':
            content = get_message_content(msg)
            if isinstance(content, list):
                for block in content:
                    # Handle both dict and object blocks
                    if isinstance(block, dict):
                        block_type = block.get('type', '')
                    elif hasattr(block, 'type'):
                        block_type = getattr(block, 'type')
                    else:
                        continue
                    
                    if block_type == 'tool_result':
                        # Get tool_use_id
                        if isinstance(block, dict):
                            tool_use_id = block.get('tool_use_id', '')
                            tool_content = block.get('content', '')
                        else:
                            tool_use_id = getattr(block, 'tool_use_id', '')
                            tool_content = getattr(block, 'content', '')
                        
                        if tool_use_id:
                            tool_call_map[tool_use_id] = {
                                'output': tool_content,
                                'name': None,
                                'arguments': None
                            }
                            print(f"Found tool result for id: {tool_use_id}")
    
    # Second pass: process assistant messages
    for msg in messages:
        role = get_message_role(msg)
        if not role or role != 'assistant':
            continue
        
        content = get_message_content(msg)
        if not content:
            continue
        
        step_number += 1
        step = ReasoningStep(step_number=step_number)
        reasoning_parts = []
        tool_calls_in_step = []
        
        # Process content
        if isinstance(content, list):
            for block in content:
                # Handle dict blocks
                if isinstance(block, dict):
                    block_type = block.get('type', '')
                    
                    if block_type == 'text':
                        text = block.get('text', '')
                        if text:
                            reasoning_parts.append(text)
                    
                    elif block_type == 'tool_use':
                        tool_use_id = block.get('id', '')
                        tool_name = block.get('name', '')
                        tool_input = block.get('input', {})
                        
                        print(f"Found tool_use: {tool_name} (id: {tool_use_id})")
                        
                        # Get output if available
                        tool_output = None
                        if tool_use_id in tool_call_map:
                            tool_output = tool_call_map[tool_use_id].get('output')
                            tool_call_map[tool_use_id]['name'] = tool_name
                            tool_call_map[tool_use_id]['arguments'] = tool_input
                        else:
                            tool_call_map[tool_use_id] = {
                                'name': tool_name,
                                'arguments': tool_input,
                                'output': None
                            }
                        
                        tool_calls_in_step.append(ToolCall(
                            name=tool_name,
                            arguments=serialize_value(tool_input),
                            output=serialize_value(tool_output) if tool_output is not None else None
                        ))
                
                # Handle object blocks (Pydantic models)
                elif hasattr(block, 'type'):
                    block_type = getattr(block, 'type')
                    
                    if block_type == 'text':
                        text = getattr(block, 'text', '')
                        if text:
                            reasoning_parts.append(text)
                    
                    elif block_type == 'tool_use':
                        tool_use_id = getattr(block, 'id', '')
                        tool_name = getattr(block, 'name', '')
                        tool_input = getattr(block, 'input', {})
                        
                        print(f"Found tool_use (object): {tool_name} (id: {tool_use_id})")
                        
                        # Get output if available
                        tool_output = None
                        if tool_use_id in tool_call_map:
                            tool_output = tool_call_map[tool_use_id].get('output')
                            tool_call_map[tool_use_id]['name'] = tool_name
                            tool_call_map[tool_use_id]['arguments'] = tool_input
                        else:
                            tool_call_map[tool_use_id] = {
                                'name': tool_name,
                                'arguments': tool_input,
                                'output': None
                            }
                        
                        tool_calls_in_step.append(ToolCall(
                            name=tool_name,
                            arguments=serialize_value(tool_input),
                            output=serialize_value(tool_output) if tool_output is not None else None
                        ))
                
                # Handle string blocks
                elif isinstance(block, str):
                    reasoning_parts.append(block)
        
        elif isinstance(content, str):
            reasoning_parts.append(content)
        
        # Set reasoning
        if reasoning_parts:
            step.reasoning = '\n'.join(reasoning_parts)
        
        # Update tool call outputs
        for tc in tool_calls_in_step:
            # Find matching tool call in map and update output
            for tool_use_id, tool_info in tool_call_map.items():
                if tool_info.get('name') == tc.name and tool_info.get('output') and tc.output is None:
                    tc.output = serialize_value(tool_info['output'])
                    break
        
        step.tool_calls = tool_calls_in_step
        
        # Only add step if it has content
        if step.reasoning or step.tool_calls:
            reasoning_steps.append(step)
            print(f"Added step {step_number} with {len(step.tool_calls)} tool calls")
    
    return reasoning_steps


def extract_from_stream_events(events: List[Any]) -> Tuple[str, List[ReasoningStep]]:
    """Extract final output and reasoning steps from stream events."""
    reasoning_steps = []
    final_output = ""
    step_number = 0
    current_step = None
    tool_call_map = {}
    
    print(f"Processing {len(events)} stream events...")
    
    for event_idx, event in enumerate(events):
        print(f"Event {event_idx}: {type(event)}")
        event_str = str(event)[:200]
        print(f"  Event content: {event_str}...")
        
        # Check event type and attributes
        if hasattr(event, '__dict__'):
            event_dict = event.__dict__
            print(f"  Event attributes: {list(event_dict.keys())}")
        
        # Try to get event type
        event_type = None
        if hasattr(event, 'type'):
            event_type = event.type
        elif hasattr(event, '__class__'):
            event_type = event.__class__.__name__
        
        print(f"  Event type: {event_type}")
        
        # Handle different event types
        if hasattr(event, 'data'):
            data = event.data
            print(f"  Event has data: {type(data)}")
            
            # Check if it's a message
            if hasattr(data, 'role'):
                role = data.role
                content = getattr(data, 'content', None)
                
                print(f"  Message role: {role}")
                
                if role == 'assistant':
                    step_number += 1
                    current_step = ReasoningStep(step_number=step_number)
                    reasoning_parts = []
                    tool_calls_in_step = []
                    
                    # Process content
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                block_type = block.get('type', '')
                                if block_type == 'text':
                                    text = block.get('text', '')
                                    if text:
                                        reasoning_parts.append(text)
                                elif block_type == 'tool_use':
                                    tool_use_id = block.get('id', '')
                                    tool_name = block.get('name', '')
                                    tool_input = block.get('input', {})
                                    
                                    tool_call_map[tool_use_id] = {
                                        'name': tool_name,
                                        'arguments': tool_input,
                                        'output': None
                                    }
                                    
                                    tool_calls_in_step.append(ToolCall(
                                        name=tool_name,
                                        arguments=serialize_value(tool_input),
                                        output=None
                                    ))
                    elif isinstance(content, str):
                        reasoning_parts.append(content)
                    
                    if reasoning_parts:
                        current_step.reasoning = '\n'.join(reasoning_parts)
                    current_step.tool_calls = tool_calls_in_step
                    
                    if current_step.reasoning or current_step.tool_calls:
                        reasoning_steps.append(current_step)
                
                elif role == 'tool':
                    # Tool result
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'tool_result':
                                tool_use_id = block.get('tool_use_id', '')
                                tool_content = block.get('content', '')
                                if tool_use_id in tool_call_map:
                                    tool_call_map[tool_use_id]['output'] = tool_content
                                    # Update the tool call in the latest step
                                    if reasoning_steps:
                                        for tc in reasoning_steps[-1].tool_calls:
                                            if tc.name == tool_call_map[tool_use_id]['name']:
                                                tc.output = serialize_value(tool_content)
                                                break
        
        # Check for final output
        if hasattr(event, 'output'):
            final_output = event.output
            print(f"  Found output: {final_output[:200]}...")
        elif hasattr(event, 'data') and isinstance(event.data, str):
            # Might be the final message
            if not final_output:
                final_output = event.data
    
    # Update tool call outputs
    for step in reasoning_steps:
        for tc in step.tool_calls:
            for tool_use_id, tool_info in tool_call_map.items():
                if tool_info['name'] == tc.name and tool_info.get('output') and tc.output is None:
                    tc.output = serialize_value(tool_info['output'])
    
    return final_output, reasoning_steps


async def build_message_history(thread_messages: List[Dict[str, Any]], max_recent: int = 10) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """
    Build message history for the agent from thread messages.
    For long threads (>max_recent messages), generates a summary of older messages.
    
    Args:
        thread_messages: List of message dicts from thread
        max_recent: Maximum number of recent messages to include directly
        
    Returns:
        Tuple of (message_history, summary_of_old_messages)
    """
    if not thread_messages:
        return [], None
    
    # Convert thread messages to Pydantic AI format
    formatted_messages = []
    for msg in thread_messages:
        role = "user" if msg.get("sender") == "user" else "assistant"
        formatted_messages.append({
            "role": role,
            "content": msg.get("text", "")
        })
    
    # If thread is short enough, return all messages
    if len(formatted_messages) <= max_recent:
        return formatted_messages, None
    
    # For long threads, summarize older messages
    older_messages = formatted_messages[:-max_recent]
    recent_messages = formatted_messages[-max_recent:]
    
    summary = await summarize_old_messages(older_messages)
    
    return recent_messages, summary


async def summarize_old_messages(messages: List[Dict[str, str]]) -> str:
    """
    Generate a summary of older messages in a long conversation.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        
    Returns:
        Summary text
    """
    from openai import AsyncOpenAI
    
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Build conversation text
    conversation_text = "\n".join([
        f"{msg['role'].capitalize()}: {msg['content']}"
        for msg in messages
    ])
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise summaries of conversations. Focus on key topics discussed, important information shared, and any preferences or context established."
                },
                {
                    "role": "user",
                    "content": f"Summarize this earlier conversation (keep it under 200 words):\n\n{conversation_text}"
                }
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        summary = response.choices[0].message.content.strip()
        return f"Earlier conversation summary: {summary}"
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return f"Earlier conversation: {len(messages)} messages exchanged about news topics."


def evaluate_tool_results(tool_calls: List[ToolCall]) -> bool:
    """
    Evaluate if tool results are sufficient.
    
    Args:
        tool_calls: List of ToolCall objects from a reasoning step
        
    Returns:
        True if results are good, False if poor/empty
    """
    if not tool_calls:
        return True  # No tools called, can't evaluate
    
    # Check each tool call's output
    for tc in tool_calls:
        if tc.output is None:
            return False
        if isinstance(tc.output, list) and len(tc.output) == 0:
            return False
        if isinstance(tc.output, str) and tc.output.strip() == "":
            return False
    
    return True


def should_continue_reasoning(iteration: int, tool_results_quality: bool, max_iterations: int = 3) -> bool:
    """
    Decide whether to continue the reasoning loop.
    
    Args:
        iteration: Current iteration number (1-indexed)
        tool_results_quality: Whether the tool results were good quality
        max_iterations: Maximum allowed iterations
        
    Returns:
        True if should continue reasoning, False otherwise
    """
    # Don't exceed max iterations
    if iteration >= max_iterations:
        return False
    
    # Continue if results were poor
    if not tool_results_quality:
        return True
    
    return False


@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Chat endpoint that processes user messages with the news agent.

    Args:
        message: User's chat message

    Returns:
        Agent's response with reasoning steps and tool calls
    """
    try:
        print(f"\n{'='*80}")
        print(f"CHAT REQUEST: {message.message}")
        print(f"MEMORY ENABLED: {message.memory_enabled}")
        print(f"THREAD ID: {message.thread_id}")
        print(f"{'='*80}\n")
        
        # Retrieve conversation history if thread exists
        message_history = []
        history_summary = None
        if message.thread_id and sessions_client:
            try:
                thread_data = sessions_client.get_thread(message.thread_id)
                if thread_data and thread_data.get("messages"):
                    print(f"Loading {len(thread_data['messages'])} messages from thread history...")
                    message_history, history_summary = await build_message_history(
                        thread_data["messages"],
                        max_recent=10
                    )
                    print(f"✓ Loaded {len(message_history)} recent messages")
                    if history_summary:
                        print(f"✓ Generated summary of {len(thread_data['messages']) - len(message_history)} older messages")
            except Exception as hist_err:
                print(f"Warning: Failed to load thread history: {hist_err}")
                message_history = []
                history_summary = None
        
        # Create dependencies
        deps = NewsDependencies(neo4j_client=neo4j_client)
        
        # Select agent based on memory preference and capture context
        preference_context = None
        if message.memory_enabled:
            if not memory_provider:
                print("⚠️  Memory requested but not available, using default agent\n")
                agent = news_agent
            else:
                # Get preferences and create agent with preference context
                preference_context = memory_provider.get_preference_context()
                if preference_context:
                    print(f"Using preferences:\n{preference_context}\n")
                    agent = create_agent_with_preferences(preference_context)
                else:
                    print("Memory enabled but no preferences found, using default agent\n")
                    agent = news_agent
        else:
            agent = news_agent
        
        # Build agent context for response
        # Extract system prompt - it's passed to Agent constructor, not a method
        # For agents created with create_agent_with_preferences, we already have the prompt
        # For the default agent, use the BASE_SYSTEM_PROMPT
        if preference_context:
            # This agent has preferences in its system prompt
            from .agent import build_system_prompt
            system_prompt_value = build_system_prompt(include_preferences=True, preferences=preference_context)
        else:
            # Default agent without preferences
            from .agent import BASE_SYSTEM_PROMPT
            system_prompt_value = BASE_SYSTEM_PROMPT
        
        agent_context = AgentContext(
            system_prompt=system_prompt_value,
            memory_enabled=message.memory_enabled,
            preferences_applied=preference_context if preference_context else None,
            model=OPENAI_MODEL,
            available_tools=[
                "search_news",
                "get_recent_news",
                "get_news_by_topic",
                "get_topics",
                "vector_search_news",
                "search_news_by_location",
                "search_news_by_date_range",
                "get_database_schema",
                "text2cypher",
                "execute_cypher"
            ]
        )

        # Multi-step reasoning loop
        all_reasoning_steps: List[ReasoningStep] = []
        final_output: Optional[str] = None
        max_reasoning_iterations = 1
        current_iteration = 0
        
        # Build initial prompt with history summary if available
        current_prompt = message.message
        if history_summary:
            current_prompt = f"{history_summary}\n\nCurrent question: {message.message}"
        
        # Reasoning loop
        for iteration in range(1, max_reasoning_iterations + 1):
            current_iteration = iteration
            print(f"\n--- Reasoning Iteration {iteration}/{max_reasoning_iterations} ---")
            
            # Stream events to capture reasoning and tool usage
            iteration_reasoning_steps: List[ReasoningStep] = []
            tool_calls_by_id: Dict[str, ToolCall] = {}
            tool_call_args_buffer: Dict[str, str] = {}
            final_output_parts: List[str] = []
            iteration_output: Optional[str] = None
            last_assistant_message: Optional[str] = None
            debug_event_limit = 20
            event_index = 0

            def coalesce_value(source: Any, *keys: str) -> Any:
                if source is None:
                    return None
                if isinstance(source, dict):
                    for key in keys:
                        if key in source and source[key] not in (None, ""):
                            return source[key]
                    return None
                if isinstance(source, (list, tuple)):
                    for item in source:
                        value = coalesce_value(item, *keys)
                        if value not in (None, ""):
                            return value
                    return None
                for key in keys:
                    if hasattr(source, key):
                        value = getattr(source, key)
                        if value not in (None, ""):
                            return value
                return None

            def parse_args(raw: Any) -> Any:
                if isinstance(raw, str):
                    try:
                        return json.loads(raw)
                    except Exception:
                        return raw
                return raw

            try:
                # Prepare message history for agent (if we have history)
                # Pydantic AI accepts message_history parameter
                async for event in agent.run_stream_events(current_prompt, deps=deps, message_history=message_history if message_history else None):
                    event_index += 1
                    event_name = event.__class__.__name__
                    event_dump = event.model_dump() if hasattr(event, "model_dump") else None
                    if event_index <= debug_event_limit:
                        print(f"Stream event #{event_index}: {event_name} -> {event_dump if event_dump is not None else repr(event)}")

                    # Reasoning events
                    if event_name == "ReasoningEvent":
                        text = coalesce_value(event_dump, "text", "content") or getattr(event, "text", None)
                        if text:
                            iteration_reasoning_steps.append(
                                ReasoningStep(
                                    step_number=len(all_reasoning_steps) + len(iteration_reasoning_steps) + 1,
                                    reasoning=str(text),
                                    tool_calls=[],
                                )
                            )
                        continue

                    # Tool call events
                    if event_name == "FunctionToolCallEvent":
                        part = getattr(event, "part", None)
                        part_dump = part.model_dump() if hasattr(part, "model_dump") else None
                        tool_name = coalesce_value(part_dump, "tool_name", "name") or getattr(part, "tool_name", None) or "unknown_tool"
                        raw_args = coalesce_value(part_dump, "args") or getattr(part, "args", None)
                        call_id = coalesce_value(part_dump, "tool_call_id", "id") or getattr(part, "tool_call_id", None)

                        if (not raw_args) and call_id and call_id in tool_call_args_buffer:
                            raw_args = tool_call_args_buffer[call_id]

                        tool_call = ToolCall(
                            name=str(tool_name),
                            arguments=serialize_value(parse_args(raw_args) or {}),
                            output=None,
                        )

                        if iteration_reasoning_steps:
                            iteration_reasoning_steps[-1].tool_calls.append(tool_call)
                        else:
                            iteration_reasoning_steps.append(
                                ReasoningStep(
                                    step_number=len(all_reasoning_steps) + 1,
                                    reasoning=None,
                                    tool_calls=[tool_call],
                                )
                            )

                        if call_id:
                            tool_calls_by_id[str(call_id)] = tool_call
                        continue

                    if event_name == "FunctionToolResultEvent":
                        result = getattr(event, "result", None)
                        result_dump = result.model_dump() if hasattr(result, "model_dump") else None
                        call_id = coalesce_value(result_dump, "tool_call_id", "id") or getattr(result, "tool_call_id", None)
                        output_value = coalesce_value(result_dump, "content", "output", "result") or getattr(result, "content", None)

                        if call_id and str(call_id) in tool_calls_by_id:
                            tool_calls_by_id[str(call_id)].output = serialize_value(output_value)
                        elif output_value and iteration_reasoning_steps:
                            iteration_reasoning_steps[-1].tool_calls.append(
                                ToolCall(name="tool", arguments={}, output=serialize_value(output_value))
                            )
                        continue

                    if event_name == "PartStartEvent":
                        part = getattr(event, "part", None)
                        part_name = part.__class__.__name__ if part is not None else ""
                        if part_name == "TextPart":
                            text = getattr(part, "content", None) or coalesce_value(part.model_dump() if hasattr(part, "model_dump") else None, "content")
                            if text:
                                final_output_parts.append(str(text))
                                last_assistant_message = "".join(final_output_parts)
                        elif part_name == "ToolCallPart":
                            call_id = getattr(part, "tool_call_id", None)
                            args = getattr(part, "args", None)
                            if call_id and args:
                                tool_call_args_buffer[str(call_id)] = args
                        continue

                    if event_name == "PartDeltaEvent":
                        delta = getattr(event, "delta", None)
                        delta_name = delta.__class__.__name__ if delta is not None else ""
                        if delta_name == "TextPartDelta":
                            text_delta = getattr(delta, "content_delta", None) or coalesce_value(delta.model_dump() if hasattr(delta, "model_dump") else None, "content_delta")
                            if text_delta:
                                final_output_parts.append(str(text_delta))
                                last_assistant_message = "".join(final_output_parts)
                        elif delta_name == "ToolCallPartDelta":
                            call_id = getattr(delta, "tool_call_id", None)
                            args_delta = getattr(delta, "args_delta", None)
                            if call_id and args_delta:
                                tool_call_args_buffer[str(call_id)] = tool_call_args_buffer.get(str(call_id), "") + str(args_delta)
                        continue

                    if event_name == "FinalResultEvent":
                        output_value = coalesce_value(event_dump, "output", "result", "content") or getattr(event, "output", None)
                        if output_value:
                            iteration_output = output_value if isinstance(output_value, str) else coalesce_value(output_value, "text", "content") or str(output_value)
                        continue

                    if hasattr(event, "output") and event.output:
                        iteration_output = event.output if isinstance(event.output, str) else str(event.output)
                    if hasattr(event, "text") and event.text:
                        last_assistant_message = str(event.text)
                    if isinstance(event_dump, dict):
                        text_candidate = coalesce_value(event_dump, "text", "content")
                        if text_candidate:
                            last_assistant_message = str(text_candidate)

            except Exception as stream_err:
                print(f"Error streaming agent events: {stream_err}")
                import traceback

                traceback.print_exc()
                iteration_reasoning_steps = []
                iteration_output = None

            # Fallbacks if streaming did not gather everything
            if not iteration_output:
                if final_output_parts:
                    iteration_output = "".join(final_output_parts)
                else:
                    iteration_output = last_assistant_message

            if not iteration_output or not iteration_reasoning_steps:
                try:
                    print("Streaming did not provide complete data; running agent once for fallback...")
                    fallback_result = await agent.run(current_prompt, deps=deps, message_history=message_history if message_history else None)
                    if not iteration_output:
                        iteration_output = fallback_result.output
                    if not iteration_reasoning_steps:
                        iteration_reasoning_steps = extract_reasoning_and_tool_calls(fallback_result)
                except Exception as fallback_err:
                    print(f"Fallback run failed: {fallback_err}")
                    import traceback

                    traceback.print_exc()
            
            # Store iteration output
            final_output = iteration_output
            all_reasoning_steps.extend(iteration_reasoning_steps)
            
            # Print iteration summary
            print(f"\nIteration {iteration} complete:")
            print(f"  - Output length: {len(iteration_output) if iteration_output else 0}")
            print(f"  - Reasoning steps: {len(iteration_reasoning_steps)}")
            
            # Evaluate tool results to decide if we should continue
            tools_had_results = False
            for step in iteration_reasoning_steps:
                if step.tool_calls:
                    tools_had_results = True
                    break
            
            if tools_had_results:
                tool_results_quality = evaluate_tool_results(
                    [tc for step in iteration_reasoning_steps for tc in step.tool_calls]
                )
                print(f"  - Tool results quality: {'GOOD' if tool_results_quality else 'POOR'}")
                
                # Decide whether to continue reasoning
                if should_continue_reasoning(iteration, tool_results_quality, max_reasoning_iterations):
                    print(f"  → Continuing to iteration {iteration + 1} due to poor tool results")
                    # Add reflection message for next iteration
                    current_prompt = f"The previous search returned no results or insufficient information. Please try a different approach or broader search terms to answer: {message.message}"
                    # Update message history with previous iteration's result
                    message_history.append({"role": "assistant", "content": iteration_output})
                    message_history.append({"role": "user", "content": current_prompt})
                    continue  # Continue to next iteration
                else:
                    print(f"  → Stopping: {'Max iterations reached' if iteration >= max_reasoning_iterations else 'Tool results are good'}")
                    break  # Exit loop
            else:
                print(f"  → No tool calls made, stopping")
                break  # No tools were called, no need to continue
 
        # Get retry logs from agent module
        from .agent import get_retry_log
        retry_log = get_retry_log()
        
        # Prepare response
        if not final_output:
            final_output = "I apologize, but I couldn't process your request."
        
        print(f"\nFinal output length: {len(final_output)}")
        print(f"Total reasoning steps count: {len(all_reasoning_steps)}")
        print(f"Reasoning iterations: {current_iteration}")
        print(f"Retries performed: {len(retry_log)}")
        
        response = ChatResponse(
            response=final_output,
            reasoning_steps=all_reasoning_steps,
            agent_context=agent_context,
            reasoning_iterations=current_iteration,
            retries_performed=retry_log
        )
        
        # Log the response structure
        print(f"\nResponse structure:")
        print(f"  - response: {final_output[:100]}...")
        print(f"  - reasoning_steps count: {len(response.reasoning_steps)}")
        print(f"  - reasoning_iterations: {response.reasoning_iterations}")
        print(f"  - retries_performed: {len(response.retries_performed)}")
        for idx, step in enumerate(response.reasoning_steps):
            print(f"    Step {idx + 1}:")
            print(f"      - step_number: {step.step_number}")
            print(f"      - has_reasoning: {bool(step.reasoning)}")
            if step.reasoning:
                print(f"      - reasoning: {step.reasoning[:100]}...")
            print(f"      - tool_calls count: {len(step.tool_calls)}")
            for tc_idx, tc in enumerate(step.tool_calls):
                print(f"        Tool {tc_idx + 1}: {tc.name}")
                print(f"          - arguments: {tc.arguments}")
                print(f"          - has_output: {tc.output is not None}")
        
        print(f"{'='*80}\n")
        
        # Extract and store preferences if memory is enabled
        if message.memory_enabled and final_output and memory_provider:
            try:
                print("Extracting preferences from conversation...")
                extraction_result = await memory_provider.process_conversation(
                    message.message,
                    final_output
                )
                print(f"✓ Extracted {extraction_result['extracted_count']} preferences, "
                      f"stored {extraction_result['stored_count']}")
            except Exception as pref_err:
                print(f"Warning: Failed to extract/store preferences: {pref_err}")
                # Don't fail the request if preference extraction fails
        
        # Handle thread persistence
        active_thread_id = message.thread_id
        if sessions_client:
            try:
                # Create new thread if no thread_id provided
                if not active_thread_id:
                    print("Creating new thread...")
                    active_thread_id = sessions_client.create_thread()
                    print(f"✓ Created thread {active_thread_id}")
                
                # Save user message to thread
                sessions_client.add_message_to_thread(
                    thread_id=active_thread_id,
                    text=message.message,
                    sender="user",
                    reasoning_steps=None
                )
                print(f"✓ Saved user message to thread {active_thread_id}")
                
                # Save agent response to thread with reasoning steps and agent context
                reasoning_steps_serializable = []
                for step in all_reasoning_steps:
                    reasoning_steps_serializable.append({
                        "step_number": step.step_number,
                        "reasoning": step.reasoning,
                        "tool_calls": [
                            {
                                "name": tc.name,
                                "arguments": tc.arguments,
                                "output": tc.output
                            }
                            for tc in step.tool_calls
                        ]
                    })
                
                # Serialize agent context
                agent_context_serializable = None
                if agent_context:
                    agent_context_serializable = {
                        "system_prompt": agent_context.system_prompt,
                        "memory_enabled": agent_context.memory_enabled,
                        "preferences_applied": agent_context.preferences_applied,
                        "model": agent_context.model,
                        "available_tools": agent_context.available_tools
                    }
                
                agent_message_id = sessions_client.add_message_to_thread(
                    thread_id=active_thread_id,
                    text=final_output,
                    sender="agent",
                    reasoning_steps=reasoning_steps_serializable if reasoning_steps_serializable else None,
                    agent_context=agent_context_serializable
                )
                print(f"✓ Saved agent response to thread {active_thread_id}")
                
                # Store procedural memory if memory is enabled
                if message.memory_enabled and procedural_memory_client and reasoning_steps_serializable:
                    try:
                        step_count = procedural_memory_client.store_reasoning_steps(
                            message_id=agent_message_id,
                            thread_id=active_thread_id,
                            reasoning_steps=reasoning_steps_serializable
                        )
                        print(f"✓ Stored {step_count} reasoning steps to procedural memory")
                    except Exception as proc_err:
                        print(f"Warning: Failed to store procedural memory: {proc_err}")
                        import traceback
                        traceback.print_exc()
                        # Don't fail the request if procedural memory storage fails
                
                # Auto-generate title after first exchange
                thread = sessions_client.get_thread(active_thread_id)
                if thread and thread.get("title") == "New Conversation" and thread.get("message_count", 0) >= 2:
                    print("Generating thread title...")
                    try:
                        new_title = await sessions_client.generate_thread_title(thread.get("messages", []))
                        sessions_client.update_thread_title(active_thread_id, new_title)
                        print(f"✓ Updated thread title to: {new_title}")
                    except Exception as title_err:
                        print(f"Warning: Failed to generate thread title: {title_err}")
                
                # Add thread_id to response
                response.thread_id = active_thread_id
                
            except Exception as thread_err:
                print(f"Warning: Failed to save messages to thread: {thread_err}")
                import traceback
                traceback.print_exc()
                # Don't fail the request if thread persistence fails
        
        return response

    except Exception as e:
        print(f"Error processing chat message: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@app.get("/categories")
async def get_categories():
    """
    Get all available news topics (categories).

    Returns:
        List of topics
    """
    try:
        topics = neo4j_client.get_topics()
        return {"categories": topics}

    except Exception as e:
        print(f"Error getting topics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting topics: {str(e)}")


@app.get("/preferences/status")
async def get_preferences_status():
    """
    Get preference statistics.

    Returns:
        Preference statistics including count and categories
    """
    if not preferences_client:
        raise HTTPException(status_code=503, detail="Preferences system not available")
    
    try:
        summary = preferences_client.get_preferences_summary()
        return summary

    except Exception as e:
        print(f"Error getting preferences status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting preferences status: {str(e)}")


@app.get("/preferences/list")
async def get_preferences_list():
    """
    Retrieve all current preferences.

    Returns:
        List of all stored preferences
    """
    if not preferences_client:
        raise HTTPException(status_code=503, detail="Preferences system not available")
    
    try:
        preferences = preferences_client.get_all_preferences()
        return preferences

    except Exception as e:
        print(f"Error getting preferences list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting preferences list: {str(e)}")


@app.post("/preferences/clear")
async def clear_preferences():
    """
    Clear all stored preferences.

    Returns:
        Status message with count of deleted preferences
    """
    if not preferences_client:
        raise HTTPException(status_code=503, detail="Preferences system not available")
    
    try:
        deleted_count = preferences_client.clear_all_preferences()
        return {
            "message": f"Successfully cleared {deleted_count} preferences",
            "deleted_count": deleted_count
        }

    except Exception as e:
        print(f"Error clearing preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing preferences: {str(e)}")


@app.delete("/preferences/{preference_id}")
async def delete_preference(preference_id: str):
    """
    Delete a specific preference by ID.

    Args:
        preference_id: The ID of the preference to delete

    Returns:
        Status message
    """
    if not preferences_client:
        raise HTTPException(status_code=503, detail="Preferences system not available")
    
    try:
        success = preferences_client.delete_preference(preference_id)
        if success:
            return {"message": f"Successfully deleted preference {preference_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"Preference {preference_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting preference: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting preference: {str(e)}")


def convert_neo4j_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Neo4j properties to JSON-serializable format.
    Handles Neo4j DateTime objects by converting them to ISO strings.
    
    Args:
        properties: Dictionary of node/relationship properties
        
    Returns:
        Dictionary with converted properties
    """
    converted = {}
    for key, value in properties.items():
        if value is None:
            converted[key] = None
        elif hasattr(value, 'iso_format'):
            # Neo4j DateTime object
            converted[key] = value.iso_format()
        elif isinstance(value, (str, int, float, bool)):
            converted[key] = value
        elif isinstance(value, list):
            converted[key] = [convert_neo4j_properties({'v': item})['v'] if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            converted[key] = convert_neo4j_properties(value)
        else:
            # Try to convert to string as fallback
            try:
                converted[key] = str(value)
            except:
                converted[key] = None
    return converted


def build_complete_memory_graph() -> Dict[str, Any]:
    """
    Build a complete memory graph combining preferences, threads, messages, and procedural memory.
    
    Returns:
        Dictionary with nodes and relationships in NVL-compatible format
    """
    all_nodes = []
    all_relationships = []
    
    # Check if memory system is available
    if not memory_neo4j_uri:
        return {"nodes": [], "relationships": []}
    
    # Use a single Neo4j session to fetch all memory data efficiently
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            memory_neo4j_uri,
            auth=(
                os.getenv("MEMORY_NEO4J_USERNAME", "neo4j"),
                os.getenv("MEMORY_NEO4J_PASSWORD", "password")
            )
        )
        
        with driver.session() as session:
            # Fetch the complete graph with all node types and relationships
            result = session.run(
                """
                // Match all memory graph patterns
                OPTIONAL MATCH (thread:Thread)
                OPTIONAL MATCH (thread)-[thread_has_msg:HAS_MESSAGE]->(msg:Message)
                OPTIONAL MATCH (thread)-[first_msg:FIRST_MESSAGE]->(first_message:Message)
                OPTIONAL MATCH (msg)-[next_msg:NEXT_MESSAGE]->(next_message:Message)
                OPTIONAL MATCH (msg)-[msg_has_step:HAS_REASONING_STEP]->(step:ReasoningStep)
                OPTIONAL MATCH (step)-[prev_next:NEXT_STEP]->(next_step:ReasoningStep)
                OPTIONAL MATCH (step)-[uses_tool:USES_TOOL]->(tc:ToolCall)
                OPTIONAL MATCH (tc)-[instance_of:INSTANCE_OF]->(tool:Tool)
                OPTIONAL MATCH (pref:UserPreference)-[in_cat:IN_CATEGORY]->(cat:PreferenceCategory)
                
                RETURN 
                    // Threads
                    collect(DISTINCT {
                        id: toString(id(thread)),
                        labels: labels(thread),
                        properties: properties(thread)
                    }) as threads,
                    
                    // Messages
                    collect(DISTINCT {
                        id: toString(id(msg)),
                        labels: labels(msg),
                        properties: properties(msg)
                    }) as messages,
                    
                    // Reasoning Steps
                    collect(DISTINCT {
                        id: toString(id(step)),
                        labels: labels(step),
                        properties: properties(step)
                    }) as reasoning_steps,
                    
                    // Tool Calls
                    collect(DISTINCT {
                        id: toString(id(tc)),
                        labels: labels(tc),
                        properties: properties(tc)
                    }) as tool_calls,
                    
                    // Tools
                    collect(DISTINCT {
                        id: toString(id(tool)),
                        labels: labels(tool),
                        properties: properties(tool)
                    }) as tools,
                    
                    // Preferences
                    collect(DISTINCT {
                        id: toString(id(pref)),
                        labels: labels(pref),
                        properties: properties(pref)
                    }) as preferences,
                    
                    // Categories
                    collect(DISTINCT {
                        id: toString(id(cat)),
                        labels: labels(cat),
                        properties: properties(cat)
                    }) as categories,
                    
                    // Relationships
                    collect(DISTINCT {
                        id: toString(id(thread_has_msg)),
                        from: toString(id(thread)),
                        to: toString(id(msg)),
                        type: type(thread_has_msg),
                        properties: {}
                    }) as thread_msg_rels,
                    
                    collect(DISTINCT {
                        id: toString(id(first_msg)),
                        from: toString(id(thread)),
                        to: toString(id(first_message)),
                        type: type(first_msg),
                        properties: {}
                    }) as thread_first_msg_rels,
                    
                    collect(DISTINCT {
                        id: toString(id(next_msg)),
                        from: toString(id(msg)),
                        to: toString(id(next_message)),
                        type: type(next_msg),
                        properties: {}
                    }) as msg_next_msg_rels,
                    
                    collect(DISTINCT {
                        id: toString(id(msg_has_step)),
                        from: toString(id(msg)),
                        to: toString(id(step)),
                        type: type(msg_has_step),
                        properties: {}
                    }) as msg_step_rels,
                    
                    collect(DISTINCT {
                        id: toString(id(prev_next)),
                        from: toString(id(step)),
                        to: toString(id(next_step)),
                        type: type(prev_next),
                        properties: {}
                    }) as step_next_rels,
                    
                    collect(DISTINCT {
                        id: toString(id(uses_tool)),
                        from: toString(id(step)),
                        to: toString(id(tc)),
                        type: type(uses_tool),
                        properties: {}
                    }) as step_tool_rels,
                    
                    collect(DISTINCT {
                        id: toString(id(instance_of)),
                        from: toString(id(tc)),
                        to: toString(id(tool)),
                        type: type(instance_of),
                        properties: {}
                    }) as toolcall_tool_rels,
                    
                    collect(DISTINCT {
                        id: toString(id(in_cat)),
                        from: toString(id(pref)),
                        to: toString(id(cat)),
                        type: type(in_cat),
                        properties: {}
                    }) as pref_cat_rels
                """
            )
            
            record = result.single()
            if record:
                # Combine all nodes (filter out null entries)
                for node_list in [
                    record["threads"],
                    record["messages"],
                    record["reasoning_steps"],
                    record["tool_calls"],
                    record["tools"],
                    record["preferences"],
                    record["categories"]
                ]:
                    for node in node_list:
                        if node.get("id") and node.get("id") != "null":
                            # Convert properties to handle DateTime objects
                            if "properties" in node and node["properties"]:
                                node["properties"] = convert_neo4j_properties(node["properties"])
                            all_nodes.append(node)
                
                # Combine all relationships (filter out null entries)
                for rel_list in [
                    record["thread_msg_rels"],
                    record["thread_first_msg_rels"],
                    record["msg_next_msg_rels"],
                    record["msg_step_rels"],
                    record["step_next_rels"],
                    record["step_tool_rels"],
                    record["toolcall_tool_rels"],
                    record["pref_cat_rels"]
                ]:
                    for rel in rel_list:
                        if rel.get("id") and rel.get("id") != "null" and rel.get("from") and rel.get("to"):
                            # Convert properties to handle DateTime objects
                            if "properties" in rel and rel["properties"]:
                                rel["properties"] = convert_neo4j_properties(rel["properties"])
                            all_relationships.append(rel)
        
        driver.close()
        
        return {
            "nodes": all_nodes,
            "relationships": all_relationships
        }
    
    except Exception as e:
        print(f"Error building complete memory graph: {e}")
        import traceback
        traceback.print_exc()
        return {"nodes": [], "relationships": []}


@app.get("/preferences/graph")
async def get_memory_graph():
    """
    Get the complete memory graph structure for visualization.
    Includes threads, messages, preferences, and procedural memory (reasoning steps, tool calls).
    
    Returns:
        Graph data with nodes and relationships in NVL-compatible format
    """
    if not memory_neo4j_uri:
        raise HTTPException(status_code=503, detail="Memory system not available")
    
    try:
        graph_data = build_complete_memory_graph()
        return graph_data
    
    except Exception as e:
        print(f"Error getting memory graph: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting memory graph: {str(e)}")


@app.get("/threads", response_model=List[ThreadInfo])
async def list_threads():
    """
    Get all conversation threads.

    Returns:
        List of threads sorted by last message time
    """
    if not sessions_client:
        raise HTTPException(status_code=503, detail="Sessions system not available")
    
    try:
        threads = sessions_client.list_threads()
        return threads

    except Exception as e:
        print(f"Error listing threads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing threads: {str(e)}")


@app.get("/threads/last-active", response_model=Optional[ThreadInfo])
async def get_last_active_thread():
    """
    Get the most recently active thread.

    Returns:
        The last active thread or None if no threads exist
    """
    if not sessions_client:
        raise HTTPException(status_code=503, detail="Sessions system not available")
    
    try:
        thread = sessions_client.get_last_active_thread()
        return thread

    except Exception as e:
        print(f"Error getting last active thread: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting last active thread: {str(e)}")


@app.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread(thread_id: str):
    """
    Get a specific thread with all its messages.

    Args:
        thread_id: The ID of the thread

    Returns:
        Thread details with messages
    """
    if not sessions_client:
        raise HTTPException(status_code=503, detail="Sessions system not available")
    
    try:
        thread = sessions_client.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        return thread

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting thread: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting thread: {str(e)}")


@app.post("/threads", response_model=ThreadInfo)
async def create_thread(request: ThreadCreateRequest):
    """
    Create a new conversation thread.

    Args:
        request: Thread creation request with optional title

    Returns:
        Created thread information
    """
    if not sessions_client:
        raise HTTPException(status_code=503, detail="Sessions system not available")
    
    try:
        thread_id = sessions_client.create_thread(title=request.title)
        thread = sessions_client.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=500, detail="Failed to retrieve created thread")
        return thread

    except Exception as e:
        print(f"Error creating thread: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating thread: {str(e)}")


@app.put("/threads/{thread_id}/title")
async def update_thread_title(thread_id: str, request: ThreadUpdateRequest):
    """
    Update a thread's title.

    Args:
        thread_id: The ID of the thread
        request: Thread update request with new title

    Returns:
        Status message
    """
    if not sessions_client:
        raise HTTPException(status_code=503, detail="Sessions system not available")
    
    try:
        success = sessions_client.update_thread_title(thread_id, request.title)
        if success:
            return {"message": f"Successfully updated thread {thread_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating thread title: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating thread title: {str(e)}")


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """
    Delete a thread and all its messages.

    Args:
        thread_id: The ID of the thread

    Returns:
        Status message
    """
    if not sessions_client:
        raise HTTPException(status_code=503, detail="Sessions system not available")
    
    try:
        success = sessions_client.delete_thread(thread_id)
        if success:
            return {"message": f"Successfully deleted thread {thread_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting thread: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting thread: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
