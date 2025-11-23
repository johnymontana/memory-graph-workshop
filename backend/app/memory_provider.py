"""Memory provider for extracting and managing user preferences using LLM."""

import os
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from .preferences_client import PreferencesClient
from .entity_extractor import EntityExtractor
from .geocoding_client import GeocodingClient


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
        self.entity_extractor = EntityExtractor()
        self.geocoding_client = GeocodingClient()

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
    
    async def parse_temporal_context(self, context: str) -> Dict[str, Any]:
        """
        Parse temporal expressions from context to extract validity dates.
        
        Args:
            context: The context string that may contain temporal information
            
        Returns:
            Dictionary with valid_from, valid_to, and date_ranges
        """
        temporal_prompt = f"""Analyze this text for temporal expressions indicating when a preference is valid.

Text: {context}

Extract:
1. **valid_from**: When does this preference start being valid? (date or relative time)
2. **valid_to**: When does this preference stop being valid? (date or relative time, or null for ongoing)
3. **date_ranges**: Any recurring or complex date patterns (e.g., weekends, summer months, specific date ranges)

Return ONLY a JSON object with this structure:
{{
  "valid_from": "YYYY-MM-DD or relative like 'now', 'next_month', null if not specified",
  "valid_to": "YYYY-MM-DD or relative like 'end_of_summer', null if ongoing/not specified",
  "date_ranges": [
    {{"description": "weekends", "pattern": "recurring"}},
    {{"start": "2024-06-01", "end": "2024-08-31"}}
  ],
  "has_temporal_constraint": true/false
}}

If there are no temporal constraints, return:
{{
  "valid_from": null,
  "valid_to": null,
  "date_ranges": null,
  "has_temporal_constraint": false
}}
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a temporal expression parser. Extract date and time information accurately and return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": temporal_prompt
                    }
                ],
                temperature=0.2,
                max_tokens=400,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content.strip()
            
            try:
                result = json.loads(content)
                
                # Convert relative dates to absolute dates
                now = datetime.utcnow()
                
                if result.get("valid_from"):
                    result["valid_from"] = self._parse_date_string(result["valid_from"], now)
                
                if result.get("valid_to"):
                    result["valid_to"] = self._parse_date_string(result["valid_to"], now)
                
                return result
                
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse temporal JSON: {e}")
                return {"valid_from": None, "valid_to": None, "date_ranges": None, "has_temporal_constraint": False}

        except Exception as e:
            print(f"Error parsing temporal context: {e}")
            return {"valid_from": None, "valid_to": None, "date_ranges": None, "has_temporal_constraint": False}
    
    def _parse_date_string(self, date_str: str, reference_date: datetime) -> Optional[datetime]:
        """
        Parse a date string (absolute or relative) into a datetime object.
        
        Args:
            date_str: Date string to parse
            reference_date: Reference date for relative dates
            
        Returns:
            Parsed datetime or None
        """
        if not date_str or date_str == "null":
            return None
        
        # Try to parse as ISO date
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            pass
        
        # Parse relative dates
        date_str_lower = date_str.lower()
        
        if date_str_lower in ["now", "today"]:
            return reference_date
        elif date_str_lower == "yesterday":
            return reference_date - timedelta(days=1)
        elif date_str_lower == "tomorrow":
            return reference_date + timedelta(days=1)
        elif date_str_lower in ["next_week", "next week"]:
            return reference_date + timedelta(weeks=1)
        elif date_str_lower in ["next_month", "next month"]:
            # Approximate: add 30 days
            return reference_date + timedelta(days=30)
        elif date_str_lower in ["next_year", "next year"]:
            return reference_date + timedelta(days=365)
        elif date_str_lower in ["last_week", "last week"]:
            return reference_date - timedelta(weeks=1)
        elif date_str_lower in ["last_month", "last month"]:
            return reference_date - timedelta(days=30)
        elif date_str_lower in ["end_of_summer", "end of summer"]:
            # Approximate: September 1st of current year
            year = reference_date.year
            return datetime(year, 9, 1)
        elif date_str_lower in ["end_of_year", "end of year"]:
            year = reference_date.year
            return datetime(year, 12, 31)
        elif "days" in date_str_lower:
            # Try to extract number of days
            match = re.search(r'(\d+)\s*days?', date_str_lower)
            if match:
                days = int(match.group(1))
                if "ago" in date_str_lower or "last" in date_str_lower:
                    return reference_date - timedelta(days=days)
                else:
                    return reference_date + timedelta(days=days)
        elif "weeks" in date_str_lower:
            match = re.search(r'(\d+)\s*weeks?', date_str_lower)
            if match:
                weeks = int(match.group(1))
                if "ago" in date_str_lower or "last" in date_str_lower:
                    return reference_date - timedelta(weeks=weeks)
                else:
                    return reference_date + timedelta(weeks=weeks)
        elif "months" in date_str_lower:
            match = re.search(r'(\d+)\s*months?', date_str_lower)
            if match:
                months = int(match.group(1))
                days = months * 30  # Approximate
                if "ago" in date_str_lower or "last" in date_str_lower:
                    return reference_date - timedelta(days=days)
                else:
                    return reference_date + timedelta(days=days)
        
        # If we can't parse it, return None
        return None

    async def store_preferences(self, preferences: List[Dict[str, Any]]) -> int:
        """
        Store newly learned preferences in Neo4j with entity extraction and temporal parsing.

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
                    # Store the preference node
                    pref_id = await self.preferences_client.store_preference(
                        category=category,
                        preference=preference,
                        context=context,
                        confidence=confidence
                    )
                    stored_count += 1
                    print(f"✓ Stored preference: [{category}] {preference[:50]}...")
                    
                    # Extract entities from the preference
                    existing_entities_by_type = {
                        "location": self.preferences_client.get_existing_entities("location"),
                        "person": self.preferences_client.get_existing_entities("person"),
                        "organization": self.preferences_client.get_existing_entities("organization"),
                        "topic": self.preferences_client.get_existing_entities("topic")
                    }
                    
                    entities = await self.entity_extractor.extract_and_resolve(
                        preference,
                        context,
                        existing_entities_by_type
                    )
                    
                    # Parse temporal information from context
                    temporal_info = await self.parse_temporal_context(context)
                    
                    # Store each entity and link to preference
                    for entity in entities:
                        try:
                            entity_id = entity.get("matched_entity_id")
                            
                            # If entity is new, create it
                            if entity.get("is_new") or not entity_id:
                                # For locations, geocode first
                                latitude = None
                                longitude = None
                                if entity["entity_type"] == "location":
                                    coords = await self.geocoding_client.geocode_location(
                                        entity["normalized_text"]
                                    )
                                    if coords:
                                        latitude, longitude = coords
                                
                                # Store the entity
                                entity_id = self.preferences_client.store_entity(
                                    entity_id=None,
                                    entity_type=entity["entity_type"],
                                    name=entity["text"],
                                    normalized_name=entity["normalized_text"],
                                    embedding=entity.get("embedding", []),
                                    latitude=latitude,
                                    longitude=longitude
                                )
                                print(f"  ✓ Created new {entity['entity_type']}: {entity['normalized_text']}")
                            else:
                                print(f"  ✓ Matched existing {entity['entity_type']}: {entity['normalized_text']} (similarity: {entity.get('similarity_score', 0):.2f})")
                            
                            # Link preference to entity with temporal information
                            self.preferences_client.link_preference_to_entity(
                                preference_id=pref_id,
                                entity_id=entity_id,
                                entity_type=entity["entity_type"],
                                confidence=entity.get("confidence", 0.8),
                                valid_from=temporal_info.get("valid_from"),
                                valid_to=temporal_info.get("valid_to"),
                                date_ranges=temporal_info.get("date_ranges")
                            )
                            print(f"  ✓ Linked {entity['entity_type']} to preference")
                            
                        except Exception as entity_err:
                            print(f"  ⚠️  Error processing entity {entity.get('text', 'unknown')}: {entity_err}")
                            # Continue with other entities
                    
            except Exception as e:
                print(f"Error storing preference: {e}")
        
        return stored_count

    def get_preference_context(self, current_query: Optional[str] = None) -> str:
        """
        Format all stored preferences for agent context with optional relevance filtering.
        
        Args:
            current_query: Optional query for relevance-based filtering

        Returns:
            Formatted string of preferences to inject into agent's system prompt
        """
        if not self.preferences_client:
            return ""
        
        # Use async wrapper since this might be called from sync context
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we need to use a different approach
                # For now, fall back to synchronous method
                return self.preferences_client.format_preferences_for_agent()
            else:
                # Create new loop and run async method
                return loop.run_until_complete(
                    self.get_preference_context_async(current_query)
                )
        except Exception as e:
            print(f"Error getting preference context: {e}")
            # Fallback to synchronous method
            return self.preferences_client.format_preferences_for_agent()
    
    async def get_preference_context_async(self, current_query: Optional[str] = None) -> str:
        """
        Async version: Format stored preferences for agent context with relevance filtering.
        
        Args:
            current_query: Optional query for relevance-based filtering

        Returns:
            Formatted string of preferences
        """
        if not self.preferences_client:
            return ""
        
        # Try with lower threshold for better recall
        result = await self.preferences_client.format_relevant_preferences_for_agent(
            query=current_query,
            threshold=0.35,
            limit=10
        )
        
        # If no relevant preferences found but query was provided, 
        # try with an even lower threshold to ensure at least one preference is included
        if not result and current_query:
            result = await self.preferences_client.format_relevant_preferences_for_agent(
                query=current_query,
                threshold=0.1,
                limit=5
            )
        
        # If still no results, fall back to all preferences (if any exist)
        if not result:
            result = self.preferences_client.format_preferences_for_agent()
        
        return result

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

