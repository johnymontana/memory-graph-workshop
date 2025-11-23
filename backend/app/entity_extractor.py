"""Entity extraction and resolution for user preferences using LLM and embeddings."""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    """Model for an extracted entity."""
    text: str = Field(description="The entity text as it appears in the preference")
    normalized_text: str = Field(description="Normalized/canonical form of the entity")
    entity_type: str = Field(description="Type of entity: location, person, organization, or topic")
    confidence: float = Field(description="Confidence score 0.0-1.0")
    context: str = Field(description="The context/sentence where the entity was found")


class ExtractedEntities(BaseModel):
    """Model for the complete extraction result."""
    entities: List[ExtractedEntity] = Field(default_factory=list)


class EntityExtractor:
    """Extract and resolve entities from user preferences using LLM and embeddings."""

    def __init__(self):
        """Initialize the entity extractor with OpenAI client."""
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = "text-embedding-3-small"
        self.similarity_threshold = 0.85  # Threshold for entity resolution
    
    async def extract_entities(
        self, 
        preference_text: str, 
        context: str
    ) -> List[Dict[str, Any]]:
        """
        Extract entities from a preference statement using LLM.
        
        Args:
            preference_text: The preference statement
            context: The original user context
            
        Returns:
            List of extracted entities with metadata
        """
        extraction_prompt = f"""Extract entities from this user preference statement.

Preference: {preference_text}
Original Context: {context}

Extract all entities that fall into these categories:
1. **Location**: Cities, countries, regions, geographic places (e.g., "San Francisco", "Europe", "Bay Area")
2. **Person**: Names of people, celebrities, authors, historical figures (e.g., "Elon Musk", "Shakespeare")
3. **Organization**: Companies, institutions, government bodies (e.g., "Google", "NASA", "UN")
4. **Topic**: Subject areas, themes, concepts (e.g., "climate change", "artificial intelligence", "sports")

For each entity:
- Provide the exact text as it appears
- Provide a normalized/canonical form (e.g., "SF" -> "San Francisco")
- Classify the entity type
- Assign confidence score (0.0-1.0)
- Include the surrounding context

Return ONLY a JSON object with this exact structure:
{{
  "entities": [
    {{
      "text": "original text",
      "normalized_text": "canonical form",
      "entity_type": "location|person|organization|topic",
      "confidence": 0.95,
      "context": "the sentence containing this entity"
    }}
  ]
}}

If no entities are found, return: {{"entities": []}}
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert entity extraction system. Extract entities accurately and return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            try:
                result = json.loads(content)
                
                # Validate structure
                if isinstance(result, dict) and "entities" in result:
                    entities = result["entities"]
                    if isinstance(entities, list):
                        # Convert to our expected format
                        extracted = []
                        for entity in entities:
                            if isinstance(entity, dict):
                                extracted.append({
                                    "text": entity.get("text", ""),
                                    "normalized_text": entity.get("normalized_text", entity.get("text", "")),
                                    "entity_type": entity.get("entity_type", "topic"),
                                    "confidence": float(entity.get("confidence", 0.8)),
                                    "context": entity.get("context", context)
                                })
                        return extracted
                
                print(f"Warning: Unexpected entity extraction format: {result}")
                return []
                
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse entity extraction JSON: {e}")
                print(f"Content was: {content}")
                return []

        except Exception as e:
            print(f"Error extracting entities: {e}")
            return []
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using OpenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None on error
        """
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None
    
    def calculate_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0 and 1
        """
        if not embedding1 or not embedding2:
            return 0.0
        
        # Ensure same length
        if len(embedding1) != len(embedding2):
            return 0.0
        
        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        similarity = dot_product / (magnitude1 * magnitude2)
        # Clamp to [0, 1] range
        return max(0.0, min(1.0, similarity))
    
    async def resolve_entity(
        self,
        entity_text: str,
        entity_type: str,
        existing_entities: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], float]:
        """
        Resolve an entity against existing entities using embedding similarity.
        
        Args:
            entity_text: Text of the entity to resolve
            entity_type: Type of entity (location, person, organization, topic)
            existing_entities: List of existing entities with embeddings
            
        Returns:
            Tuple of (matched_entity_id, similarity_score) or (None, 0.0) if no match
        """
        # Generate embedding for new entity
        entity_embedding = await self.generate_embedding(entity_text)
        if not entity_embedding:
            return None, 0.0
        
        # Filter existing entities by type
        candidates = [e for e in existing_entities if e.get("entity_type") == entity_type]
        
        if not candidates:
            return None, 0.0
        
        # Find best match
        best_match = None
        best_similarity = 0.0
        
        for candidate in candidates:
            if not candidate.get("embedding"):
                continue
            
            similarity = self.calculate_similarity(
                entity_embedding,
                candidate["embedding"]
            )
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = candidate
        
        # Return match if above threshold
        if best_similarity >= self.similarity_threshold:
            return best_match.get("id"), best_similarity
        
        return None, 0.0
    
    async def extract_and_resolve(
        self,
        preference_text: str,
        context: str,
        existing_entities_by_type: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Extract entities and resolve them against existing entities.
        
        Args:
            preference_text: The preference statement
            context: The original user context
            existing_entities_by_type: Dict mapping entity_type to list of existing entities
            
        Returns:
            List of entities with resolution information
        """
        # Extract entities
        extracted = await self.extract_entities(preference_text, context)
        
        if not extracted:
            return []
        
        # Resolve each entity
        resolved_entities = []
        for entity in extracted:
            entity_type = entity.get("entity_type", "topic")
            entity_text = entity.get("normalized_text", entity.get("text", ""))
            
            # Get existing entities of this type
            existing = existing_entities_by_type.get(entity_type, [])
            
            # Try to resolve
            matched_id, similarity = await self.resolve_entity(
                entity_text,
                entity_type,
                existing
            )
            
            # Generate embedding for this entity
            embedding = await self.generate_embedding(entity_text)
            
            resolved_entities.append({
                "text": entity.get("text", ""),
                "normalized_text": entity_text,
                "entity_type": entity_type,
                "confidence": entity.get("confidence", 0.8),
                "context": entity.get("context", context),
                "matched_entity_id": matched_id,
                "similarity_score": similarity,
                "is_new": matched_id is None,
                "embedding": embedding
            })
        
        return resolved_entities

