"""Memory provider for extracting and managing user preferences using LLM."""

import os
import json
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from .preferences_client import PreferencesClient


class Neo4jMemoryProvider:
    """Memory provider that extracts user preferences using LLM and stores them in Neo4j."""

    def __init__(self, preferences_client: Optional[PreferencesClient]):
        """
        Initialize the memory provider.

        Args:
            preferences_client: The Neo4j preferences client (can be None if memory disabled)
        """
        if preferences_client is None:
            raise ValueError("PreferencesClient is required for Neo4jMemoryProvider")
        self.preferences_client = preferences_client
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def extract_preferences(
        self, 
        user_msg: str, 
        agent_response: str
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to analyze conversation and extract user preferences.

        Args:
            user_msg: The user's message
            agent_response: The agent's response

        Returns:
            List of extracted preferences with category, preference, context, and confidence
        """
        extraction_prompt = f"""Analyze the following conversation and extract any user preferences that can be learned.

User: {user_msg}
Assistant: {agent_response}

Extract any preferences the user has expressed. Look for:
- Topics of interest (e.g., "I'm interested in climate change news")
- Detail level preferences (e.g., "Keep it brief", "Give me detailed analysis")
- Writing style preferences (e.g., "Explain like I'm 5", "Use technical terms")
- Topic dislikes (e.g., "I don't care about sports")
- Geographic focus (e.g., "Focus on US news", "International news only")
- News source preferences
- Any other expressed preferences

For each preference found, return a JSON object with:
- category: One of [topics_of_interest, detail_level, writing_style, topic_dislikes, geographic_focus, news_sources, other]
- preference: A clear statement of the preference (e.g., "User is interested in climate change news")
- context: The original user statement that led to this preference
- confidence: A score from 0.0 to 1.0 indicating how confident you are about this preference

Return ONLY a JSON array of preferences, or an empty array [] if no preferences were found.
Do not include any explanation, just the JSON array.

Example output:
[
  {{
    "category": "topics_of_interest",
    "preference": "User is interested in climate change and environmental news",
    "context": "User asked 'What news do you have about climate change?'",
    "confidence": 0.9
  }},
  {{
    "category": "detail_level",
    "preference": "User prefers brief summaries",
    "context": "User said 'Keep it brief'",
    "confidence": 1.0
  }}
]"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Using mini for cost-efficiency
                messages=[
                    {
                        "role": "system",
                        "content": "You are a preference extraction assistant. Extract user preferences from conversations and return them as JSON."
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent extraction
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            try:
                preferences = json.loads(content)
                if isinstance(preferences, list):
                    return preferences
                else:
                    print(f"Warning: Expected list of preferences, got: {type(preferences)}")
                    return []
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse preferences JSON: {e}")
                print(f"Content was: {content}")
                return []

        except Exception as e:
            print(f"Error extracting preferences: {e}")
            return []

    async def store_preferences(self, preferences: List[Dict[str, Any]]) -> int:
        """
        Store newly learned preferences in Neo4j.

        Args:
            preferences: List of preference dictionaries

        Returns:
            Number of preferences stored
        """
        if not self.preferences_client:
            print("Warning: Cannot store preferences - preferences client not available")
            return 0
            
        stored_count = 0
        
        for pref in preferences:
            try:
                category = pref.get("category", "other")
                preference = pref.get("preference", "")
                context = pref.get("context", "")
                confidence = pref.get("confidence", 1.0)
                
                if preference:  # Only store if we have an actual preference
                    self.preferences_client.store_preference(
                        category=category,
                        preference=preference,
                        context=context,
                        confidence=confidence
                    )
                    stored_count += 1
                    print(f"✓ Stored preference: [{category}] {preference[:50]}...")
            except Exception as e:
                print(f"Error storing preference: {e}")
        
        return stored_count

    def get_preference_context(self) -> str:
        """
        Format all stored preferences for agent context.

        Returns:
            Formatted string of preferences to inject into agent's system prompt
        """
        if not self.preferences_client:
            return ""
        return self.preferences_client.format_preferences_for_agent()

    def format_for_agent(self) -> str:
        """
        Format preferences as context string for the agent's system prompt.
        (Alias for get_preference_context for API consistency)

        Returns:
            Formatted string of preferences
        """
        return self.get_preference_context()

    async def process_conversation(
        self, 
        user_msg: str, 
        agent_response: str
    ) -> Dict[str, Any]:
        """
        Process a conversation turn: extract and store preferences.

        Args:
            user_msg: The user's message
            agent_response: The agent's response

        Returns:
            Dictionary with extraction results
        """
        # Extract preferences
        preferences = await self.extract_preferences(user_msg, agent_response)
        
        # Store preferences
        stored_count = await self.store_preferences(preferences)
        
        return {
            "extracted_count": len(preferences),
            "stored_count": stored_count,
            "preferences": preferences
        }

