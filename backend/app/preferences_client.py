"""Neo4j client for managing user preferences in a separate Neo4j instance."""

import os
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


class PreferencesClient:
    """Client for interacting with Neo4j preferences database (separate instance)."""

    def __init__(self):
        """Initialize Neo4j connection to memory database instance."""
        uri = os.getenv("MEMORY_NEO4J_URI")
        username = os.getenv("MEMORY_NEO4J_USERNAME", "neo4j")
        password = os.getenv("MEMORY_NEO4J_PASSWORD", "password")

        if not uri:
            raise ValueError(
                "MEMORY_NEO4J_URI environment variable is required for preferences client. "
                "Set this to use a separate Neo4j instance for memory/preferences features."
            )

        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = "text-embedding-3-small"
        self._initialize_schema()
        
        print(f"✓ Preferences client initialized using memory Neo4j instance at: {uri}")

    def close(self):
        """Close the database connection."""
        self.driver.close()

    def _initialize_schema(self):
        """Create indexes and constraints for the preferences database."""
        try:
            with self.driver.session() as session:
                try:
                    # UserPreference constraints and indexes
                    session.run(
                        "CREATE CONSTRAINT preference_id_unique IF NOT EXISTS "
                        "FOR (p:UserPreference) REQUIRE p.id IS UNIQUE"
                    )
                    
                    session.run(
                        "CREATE INDEX preference_category_text_idx IF NOT EXISTS "
                        "FOR (p:UserPreference) ON (p.category, p.preference)"
                    )
                    
                    session.run(
                        "CREATE INDEX preference_created_idx IF NOT EXISTS "
                        "FOR (p:UserPreference) ON (p.created_at)"
                    )
                    
                    # Vector index for preference embeddings
                    session.run(
                        "CREATE VECTOR INDEX preference_embedding_idx IF NOT EXISTS "
                        "FOR (p:UserPreference) ON (p.embedding) "
                        "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
                    )
                    
                    # PreferenceCategory constraint
                    session.run(
                        "CREATE CONSTRAINT category_name_unique IF NOT EXISTS "
                        "FOR (c:PreferenceCategory) REQUIRE c.name IS UNIQUE"
                    )
                    
                    # Entity node constraints and indexes
                    # Location entity
                    session.run(
                        "CREATE CONSTRAINT location_id_unique IF NOT EXISTS "
                        "FOR (l:Location) REQUIRE l.id IS UNIQUE"
                    )
                    
                    session.run(
                        "CREATE INDEX location_normalized_name_idx IF NOT EXISTS "
                        "FOR (l:Location) ON (l.normalized_name)"
                    )
                    
                    # Point index for geospatial queries
                    session.run(
                        "CREATE POINT INDEX location_point_idx IF NOT EXISTS "
                        "FOR (l:Location) ON (l.location_point)"
                    )
                    
                    # Vector index for location embeddings
                    session.run(
                        "CREATE VECTOR INDEX location_embedding_idx IF NOT EXISTS "
                        "FOR (l:Location) ON (l.embedding) "
                        "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
                    )
                    
                    # Person entity
                    session.run(
                        "CREATE CONSTRAINT person_id_unique IF NOT EXISTS "
                        "FOR (p:Person) REQUIRE p.id IS UNIQUE"
                    )
                    
                    session.run(
                        "CREATE INDEX person_normalized_name_idx IF NOT EXISTS "
                        "FOR (p:Person) ON (p.normalized_name)"
                    )
                    
                    session.run(
                        "CREATE VECTOR INDEX person_embedding_idx IF NOT EXISTS "
                        "FOR (p:Person) ON (p.embedding) "
                        "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
                    )
                    
                    # Organization entity
                    session.run(
                        "CREATE CONSTRAINT organization_id_unique IF NOT EXISTS "
                        "FOR (o:Organization) REQUIRE o.id IS UNIQUE"
                    )
                    
                    session.run(
                        "CREATE INDEX organization_normalized_name_idx IF NOT EXISTS "
                        "FOR (o:Organization) ON (o.normalized_name)"
                    )
                    
                    session.run(
                        "CREATE VECTOR INDEX organization_embedding_idx IF NOT EXISTS "
                        "FOR (o:Organization) ON (o.embedding) "
                        "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
                    )
                    
                    # Topic entity
                    session.run(
                        "CREATE CONSTRAINT topic_id_unique IF NOT EXISTS "
                        "FOR (t:Topic) REQUIRE t.id IS UNIQUE"
                    )
                    
                    session.run(
                        "CREATE INDEX topic_normalized_name_idx IF NOT EXISTS "
                        "FOR (t:Topic) ON (t.normalized_name)"
                    )
                    
                    session.run(
                        "CREATE VECTOR INDEX topic_embedding_idx IF NOT EXISTS "
                        "FOR (t:Topic) ON (t.embedding) "
                        "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
                    )
                    
                    print(f"✓ Preferences schema initialized in memory database")
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" in error_msg or "equivalent" in error_msg:
                        print(f"✓ Preferences schema already exists in memory database")
                    else:
                        print(f"⚠️  Schema initialization warning: {e}")
        except Exception as e:
            print(f"⚠️  Could not initialize preferences schema: {e}")
            print(f"   Preferences may not work correctly until schema is created")
    
    def initialize_preferences_schema(self):
        """Create indexes and constraints for the preferences database (public method for manual calls)."""
        self._initialize_schema()

    async def store_preference(
        self, 
        category: str, 
        preference: str, 
        context: str, 
        confidence: float = 1.0
    ) -> str:
        """
        Store a learned user preference. If a preference with the same category and text
        already exists, update it instead of creating a duplicate.

        Args:
            category: Category of the preference (e.g., 'topics_of_interest')
            preference: The preference statement
            context: Context in which the preference was learned
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            The ID of the created or updated preference
        """
        now = datetime.utcnow()
        
        # Generate embedding for the preference
        embedding = await self.generate_query_embedding(preference)
        if not embedding:
            print(f"⚠️  Failed to generate embedding for preference, storing without embedding")
        
        with self.driver.session() as session:
            result = session.run(
                """
                // Create or get the category
                MERGE (cat:PreferenceCategory {name: $category})
                ON CREATE SET cat.description = $category
                
                // Merge the preference based on category and preference text
                MERGE (pref:UserPreference {category: $category, preference: $preference})
                ON CREATE SET 
                    pref.id = $id,
                    pref.context = $context,
                    pref.confidence = $confidence,
                    pref.embedding = $embedding,
                    pref.created_at = datetime($created_at),
                    pref.last_updated = datetime($created_at)
                ON MATCH SET
                    pref.context = $context,
                    pref.confidence = $confidence,
                    pref.embedding = $embedding,
                    pref.last_updated = datetime($created_at)
                
                // Create relationship if it doesn't exist
                MERGE (pref)-[:IN_CATEGORY]->(cat)
                
                RETURN pref.id as id
                """,
                {
                    "id": str(uuid.uuid4()),
                    "category": category,
                    "preference": preference,
                    "context": context,
                    "confidence": confidence,
                    "embedding": embedding,
                    "created_at": now.isoformat()
                }
            )
            
            record = result.single()
            return record["id"] if record else str(uuid.uuid4())

    async def update_preference_embeddings(self) -> int:
        """
        Generate and store embeddings for all preferences that don't have them.
        This is useful for updating existing preferences after enabling embedding support.
        
        Returns:
            Number of preferences updated with embeddings
        """
        # Get all preferences without embeddings
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference)
                WHERE pref.embedding IS NULL
                RETURN pref.id as id, pref.preference as preference
                """
            )
            
            preferences_to_update = []
            for record in result:
                preferences_to_update.append({
                    "id": record["id"],
                    "preference": record["preference"]
                })
        
        if not preferences_to_update:
            print("✓ All preferences already have embeddings")
            return 0
        
        print(f"Updating {len(preferences_to_update)} preferences with embeddings...")
        updated_count = 0
        
        for pref_data in preferences_to_update:
            try:
                # Generate embedding for the preference
                embedding = await self.generate_query_embedding(pref_data["preference"])
                
                if embedding:
                    # Update the preference with the embedding
                    with self.driver.session() as session:
                        session.run(
                            """
                            MATCH (pref:UserPreference {id: $id})
                            SET pref.embedding = $embedding,
                                pref.last_updated = datetime($updated_at)
                            """,
                            {
                                "id": pref_data["id"],
                                "embedding": embedding,
                                "updated_at": datetime.utcnow().isoformat()
                            }
                        )
                    updated_count += 1
                    print(f"  ✓ Updated embedding for preference: {pref_data['preference'][:50]}...")
                else:
                    print(f"  ⚠️  Failed to generate embedding for: {pref_data['preference'][:50]}...")
            except Exception as e:
                print(f"  ⚠️  Error updating preference {pref_data['id']}: {e}")
        
        print(f"✓ Updated {updated_count} preferences with embeddings")
        return updated_count

    def get_preferences_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all preferences for a specific category.

        Args:
            category: The category to filter by

        Returns:
            List of preferences in the category
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference {category: $category})
                RETURN pref.id as id,
                       pref.category as category,
                       pref.preference as preference,
                       pref.context as context,
                       pref.confidence as confidence,
                       pref.created_at as created_at,
                       pref.last_updated as last_updated
                ORDER BY pref.created_at DESC
                """,
                {"category": category}
            )
            
            preferences = []
            for record in result:
                preferences.append({
                    "id": record["id"],
                    "category": record["category"],
                    "preference": record["preference"],
                    "context": record["context"],
                    "confidence": record["confidence"],
                    "created_at": record["created_at"],
                    "last_updated": record["last_updated"]
                })
            
            return preferences

    def get_all_preferences(self) -> List[Dict[str, Any]]:
        """
        Retrieve all stored preferences.

        Returns:
            List of all preferences
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference)
                RETURN pref.id as id,
                       pref.category as category,
                       pref.preference as preference,
                       pref.context as context,
                       pref.confidence as confidence,
                       pref.created_at as created_at,
                       pref.last_updated as last_updated
                ORDER BY pref.category, pref.created_at DESC
                """
            )
            
            preferences = []
            for record in result:
                preferences.append({
                    "id": record["id"],
                    "category": record["category"],
                    "preference": record["preference"],
                    "context": record["context"],
                    "confidence": record["confidence"],
                    "created_at": str(record["created_at"]) if record["created_at"] else None,
                    "last_updated": str(record["last_updated"]) if record["last_updated"] else None
                })
            
            return preferences

    def update_preference(
        self, 
        preference_id: str, 
        new_value: str, 
        confidence: float
    ) -> bool:
        """
        Update an existing preference.

        Args:
            preference_id: ID of the preference to update
            new_value: New preference value
            confidence: New confidence score

        Returns:
            True if updated, False if not found
        """
        now = datetime.utcnow()
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference {id: $id})
                SET pref.preference = $new_value,
                    pref.confidence = $confidence,
                    pref.last_updated = datetime($updated_at)
                RETURN pref.id as id
                """,
                {
                    "id": preference_id,
                    "new_value": new_value,
                    "confidence": confidence,
                    "updated_at": now.isoformat()
                }
            )
            
            return result.single() is not None

    def delete_preference(self, preference_id: str) -> bool:
        """
        Remove a specific preference.

        Args:
            preference_id: ID of the preference to delete

        Returns:
            True if deleted, False if not found
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference {id: $id})
                DETACH DELETE pref
                RETURN count(pref) as deleted_count
                """,
                {"id": preference_id}
            )
            
            record = result.single()
            return record["deleted_count"] > 0 if record else False

    def clear_all_preferences(self) -> int:
        """
        Clear all stored preferences.

        Returns:
            Number of preferences deleted
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference)
                DETACH DELETE pref
                RETURN count(pref) as deleted_count
                """
            )
            
            record = result.single()
            return record["deleted_count"] if record else 0

    def get_preferences_summary(self) -> Dict[str, Any]:
        """
        Get statistics about stored preferences.

        Returns:
            Dictionary with preference statistics
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference)
                RETURN count(pref) as total,
                       collect(DISTINCT pref.category) as categories
                """
            )
            
            record = result.single()
            if record:
                return {
                    "total_preferences": record["total"],
                    "categories": sorted(record["categories"]) if record["categories"] else []
                }
            else:
                return {
                    "total_preferences": 0,
                    "categories": []
                }

    def format_preferences_for_agent(self) -> str:
        """
        Format all preferences as a context string for the agent.

        Returns:
            Formatted string of preferences
        """
        preferences = self.get_all_preferences()
        
        if not preferences:
            return ""
        
        # Group preferences by category
        by_category = {}
        for pref in preferences:
            category = pref["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(pref)
        
        # Format as text
        lines = ["User Preferences:"]
        for category, prefs in sorted(by_category.items()):
            lines.append(f"\n{category.replace('_', ' ').title()}:")
            for pref in prefs:
                confidence_str = f" (confidence: {pref['confidence']:.2f})" if pref['confidence'] < 1.0 else ""
                lines.append(f"  - {pref['preference']}{confidence_str}")
        
        return "\n".join(lines)
    
    def get_memory_graph(self) -> Dict[str, Any]:
        """
        Get the memory graph structure for visualization.
        
        Returns:
            Dictionary with nodes and relationships in NVL-compatible format
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (pref:UserPreference)-[r:IN_CATEGORY]->(cat:PreferenceCategory)
                RETURN 
                    collect(DISTINCT {
                        id: toString(id(pref)),
                        labels: ['UserPreference'],
                        properties: {
                            id: pref.id,
                            category: pref.category,
                            preference: pref.preference,
                            context: pref.context,
                            confidence: pref.confidence,
                            created_at: toString(pref.created_at),
                            last_updated: toString(pref.last_updated)
                        }
                    }) as preference_nodes,
                    collect(DISTINCT {
                        id: toString(id(cat)),
                        labels: ['PreferenceCategory'],
                        properties: {
                            name: cat.name,
                            description: cat.description
                        }
                    }) as category_nodes,
                    collect(DISTINCT {
                        id: toString(id(r)),
                        from: toString(id(pref)),
                        to: toString(id(cat)),
                        type: type(r),
                        properties: {}
                    }) as relationships
                """
            )
            
            record = result.single()
            if record:
                # Combine all nodes
                nodes = record["preference_nodes"] + record["category_nodes"]
                relationships = record["relationships"]
                
                return {
                    "nodes": nodes,
                    "relationships": relationships
                }
            else:
                return {
                    "nodes": [],
                    "relationships": []
                }
    
    def get_existing_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get all existing entities of a specific type with their embeddings.
        
        Args:
            entity_type: Type of entity (location, person, organization, topic)
            
        Returns:
            List of entities with id, name, and embedding
        """
        # Map entity type to label
        label_map = {
            "location": "Location",
            "person": "Person",
            "organization": "Organization",
            "topic": "Topic"
        }
        
        label = label_map.get(entity_type.lower())
        if not label:
            return []
        
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (e:{label})
                RETURN e.id as id,
                       e.name as name,
                       e.normalized_name as normalized_name,
                       e.embedding as embedding
                """,
                {}
            )
            
            entities = []
            for record in result:
                entities.append({
                    "id": record["id"],
                    "name": record["name"],
                    "normalized_name": record["normalized_name"],
                    "embedding": record["embedding"],
                    "entity_type": entity_type.lower()
                })
            
            return entities
    
    def store_entity(
        self,
        entity_id: Optional[str],
        entity_type: str,
        name: str,
        normalized_name: str,
        embedding: List[float],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> str:
        """
        Store or update an entity node.
        
        Args:
            entity_id: ID of existing entity (None for new entity)
            entity_type: Type of entity (location, person, organization, topic)
            name: Original name
            normalized_name: Canonical/normalized name
            embedding: Embedding vector
            latitude: Latitude (for locations)
            longitude: Longitude (for locations)
            
        Returns:
            Entity ID
        """
        # Map entity type to label
        label_map = {
            "location": "Location",
            "person": "Person",
            "organization": "Organization",
            "topic": "Topic"
        }
        
        label = label_map.get(entity_type.lower())
        if not label:
            raise ValueError(f"Invalid entity type: {entity_type}")
        
        now = datetime.utcnow()
        
        if entity_id:
            # Update existing entity
            with self.driver.session() as session:
                query = f"""
                    MATCH (e:{label} {{id: $id}})
                    SET e.name = $name,
                        e.normalized_name = $normalized_name,
                        e.embedding = $embedding,
                        e.last_updated = datetime($updated_at)
                """
                
                params = {
                    "id": entity_id,
                    "name": name,
                    "normalized_name": normalized_name,
                    "embedding": embedding,
                    "updated_at": now.isoformat()
                }
                
                # Add location-specific properties
                if label == "Location" and latitude is not None and longitude is not None:
                    query += """,
                        e.latitude = $latitude,
                        e.longitude = $longitude,
                        e.location_point = point({latitude: $latitude, longitude: $longitude})
                    """
                    params["latitude"] = latitude
                    params["longitude"] = longitude
                
                query += " RETURN e.id as id"
                
                result = session.run(query, params)
                record = result.single()
                return record["id"] if record else entity_id
        else:
            # Create new entity
            new_id = str(uuid.uuid4())
            
            with self.driver.session() as session:
                query = f"""
                    CREATE (e:{label})
                    SET e.id = $id,
                        e.name = $name,
                        e.normalized_name = $normalized_name,
                        e.embedding = $embedding,
                        e.created_at = datetime($created_at),
                        e.last_updated = datetime($created_at)
                """
                
                params = {
                    "id": new_id,
                    "name": name,
                    "normalized_name": normalized_name,
                    "embedding": embedding,
                    "created_at": now.isoformat()
                }
                
                # Add location-specific properties
                if label == "Location" and latitude is not None and longitude is not None:
                    query += """,
                        e.latitude = $latitude,
                        e.longitude = $longitude,
                        e.location_point = point({latitude: $latitude, longitude: $longitude})
                    """
                    params["latitude"] = latitude
                    params["longitude"] = longitude
                
                query += " RETURN e.id as id"
                
                result = session.run(query, params)
                record = result.single()
                return record["id"] if record else new_id
    
    def link_preference_to_entity(
        self,
        preference_id: str,
        entity_id: str,
        entity_type: str,
        confidence: float = 1.0,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None,
        date_ranges: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Create a temporal relationship between a preference and an entity.
        
        Args:
            preference_id: ID of the preference
            entity_id: ID of the entity
            entity_type: Type of entity (location, person, organization, topic)
            confidence: Confidence score
            valid_from: Start date for validity
            valid_to: End date for validity (None = ongoing)
            date_ranges: Complex date ranges as JSON
            
        Returns:
            True if successful
        """
        # Map entity type to label and relationship type
        label_map = {
            "location": ("Location", "REFERS_TO_LOCATION"),
            "person": ("Person", "REFERS_TO_PERSON"),
            "organization": ("Organization", "REFERS_TO_ORGANIZATION"),
            "topic": ("Topic", "REFERS_TO_TOPIC")
        }
        
        mapping = label_map.get(entity_type.lower())
        if not mapping:
            raise ValueError(f"Invalid entity type: {entity_type}")
        
        label, rel_type = mapping
        now = datetime.utcnow()
        
        with self.driver.session() as session:
            # Build relationship properties
            rel_props = {
                "confidence": confidence,
                "created_at": "datetime($created_at)"
            }
            
            params = {
                "pref_id": preference_id,
                "entity_id": entity_id,
                "confidence": confidence,
                "created_at": now.isoformat()
            }
            
            if valid_from:
                rel_props["valid_from"] = "datetime($valid_from)"
                params["valid_from"] = valid_from.isoformat()
            
            if valid_to:
                rel_props["valid_to"] = "datetime($valid_to)"
                params["valid_to"] = valid_to.isoformat()
            
            if date_ranges:
                rel_props["date_ranges"] = "$date_ranges"
                params["date_ranges"] = str(date_ranges)  # Store as JSON string
            
            # Build property string for query
            prop_str = ", ".join([f"{k}: {v}" for k, v in rel_props.items()])
            
            query = f"""
                MATCH (pref:UserPreference {{id: $pref_id}})
                MATCH (e:{label} {{id: $entity_id}})
                MERGE (pref)-[r:{rel_type}]->(e)
                SET r = {{{prop_str}}}
                RETURN r
            """
            
            result = session.run(query, params)
            return result.single() is not None
    
    async def generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding for a query string.
        
        Args:
            query: The query text
            
        Returns:
            Embedding vector or None on error
        """
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating query embedding: {e}")
            return None
    
    async def get_relevant_preferences(
        self,
        query: str,
        threshold: float = 0.1,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get preferences relevant to the current query using semantic similarity.
        Filters by temporal validity (only active preferences).
        
        Args:
            query: The current user query
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of preferences to return
            
        Returns:
            List of relevant preferences sorted by relevance score
        """
        # Generate embedding for query
        query_embedding = await self.generate_query_embedding(query)
        if not query_embedding:
            # Fallback to all active preferences
            return self.get_all_preferences()
        
        now = datetime.utcnow()
        
        with self.driver.session() as session:
            # Search preferences by embedding similarity
            # Filter by temporal validity: valid_from <= now AND (valid_to IS NULL OR valid_to >= now)
            result = session.run(
                """
                MATCH (pref:UserPreference)
                WHERE pref.embedding IS NOT NULL
                
                // Optional entity relationships for additional scoring
                OPTIONAL MATCH (pref)-[rel:REFERS_TO_LOCATION|REFERS_TO_PERSON|REFERS_TO_ORGANIZATION|REFERS_TO_TOPIC]->(entity)
                WHERE entity.embedding IS NOT NULL
                
                // Calculate preference similarity
                WITH pref, 
                     collect(DISTINCT {entity: entity, rel: rel, embedding: entity.embedding}) as entities,
                     vector.similarity.cosine(pref.embedding, $query_embedding) as pref_similarity
                
                // Calculate temporal relevance
                WITH pref, entities, pref_similarity,
                     CASE
                        // Check if any entity relationship has temporal constraints
                        WHEN size([e IN entities WHERE e.rel IS NOT NULL]) > 0 THEN
                            reduce(sum = 0.0, e IN [e IN entities WHERE e.rel IS NOT NULL] | 
                                sum + CASE
                                    // Currently valid (no end date or end date in future)
                                    WHEN (e.rel.valid_from IS NULL OR e.rel.valid_from <= datetime($now))
                                         AND (e.rel.valid_to IS NULL OR e.rel.valid_to >= datetime($now))
                                    THEN 1.0
                                    // Recently expired (within last 30 days)
                                    WHEN e.rel.valid_to IS NOT NULL 
                                         AND e.rel.valid_to < datetime($now)
                                         AND duration.between(e.rel.valid_to, datetime($now)).days <= 30
                                    THEN 0.5
                                    // Not yet valid
                                    WHEN e.rel.valid_from IS NOT NULL
                                         AND e.rel.valid_from > datetime($now)
                                    THEN 0.3
                                    ELSE 0.0
                                END
                            ) / toFloat(size([e IN entities WHERE e.rel IS NOT NULL]))
                        ELSE 1.0  // No temporal constraints = always valid
                     END as temporal_relevance
                
                // Calculate entity similarity (if entities exist)
                WITH pref, entities, pref_similarity, temporal_relevance,
                     CASE
                        WHEN size([e IN entities WHERE e.embedding IS NOT NULL]) > 0 THEN
                            reduce(sum = 0.0, e IN [e IN entities WHERE e.embedding IS NOT NULL] | 
                                sum + vector.similarity.cosine(e.embedding, $query_embedding)
                            ) / toFloat(size([e IN entities WHERE e.embedding IS NOT NULL]))
                        ELSE 0.0
                     END as entity_similarity
                
                // Combined relevance score
                WITH pref,
                     (pref_similarity * 0.5 + entity_similarity * 0.3 + temporal_relevance * 0.2) as relevance_score
                
                WHERE relevance_score >= $threshold
                
                RETURN pref.id as id,
                       pref.category as category,
                       pref.preference as preference,
                       pref.context as context,
                       pref.confidence as confidence,
                       pref.created_at as created_at,
                       pref.last_updated as last_updated,
                       relevance_score
                
                ORDER BY relevance_score DESC
                LIMIT $limit
                """,
                {
                    "query_embedding": query_embedding,
                    "threshold": threshold,
                    "limit": limit,
                    "now": now.isoformat()
                }
            )
            
            preferences = []
            for record in result:
                preferences.append({
                    "id": record["id"],
                    "category": record["category"],
                    "preference": record["preference"],
                    "context": record["context"],
                    "confidence": record["confidence"],
                    "created_at": str(record["created_at"]) if record["created_at"] else None,
                    "last_updated": str(record["last_updated"]) if record["last_updated"] else None,
                    "relevance_score": record["relevance_score"]
                })
            
            # If no relevant preferences found, fall back to most recent preferences
            # to ensure at least some preferences are included (if any exist)
            if not preferences:
                fallback_result = session.run(
                    """
                    MATCH (pref:UserPreference)
                    RETURN pref.id as id,
                           pref.category as category,
                           pref.preference as preference,
                           pref.context as context,
                           pref.confidence as confidence,
                           pref.created_at as created_at,
                           pref.last_updated as last_updated
                    ORDER BY pref.created_at DESC
                    LIMIT $limit
                    """,
                    {"limit": min(limit, 3)}  # Return at most 3 as fallback
                )
                
                for record in fallback_result:
                    preferences.append({
                        "id": record["id"],
                        "category": record["category"],
                        "preference": record["preference"],
                        "context": record["context"],
                        "confidence": record["confidence"],
                        "created_at": str(record["created_at"]) if record["created_at"] else None,
                        "last_updated": str(record["last_updated"]) if record["last_updated"] else None,
                        "relevance_score": 0.0  # No relevance score for fallback
                    })
                
                if preferences:
                    print(f"ℹ️  Vector search returned no results, using {len(preferences)} most recent preferences as fallback")
            
            return preferences
    
    async def format_relevant_preferences_for_agent(
        self,
        query: Optional[str] = None,
        threshold: float = 0.1,
        limit: int = 10
    ) -> str:
        """
        Format relevant preferences as a context string for the agent.
        If query is provided, uses relevance-based filtering.
        Otherwise, returns all active preferences.
        
        Args:
            query: Current user query for relevance filtering
            threshold: Minimum similarity threshold
            limit: Maximum number of preferences
            
        Returns:
            Formatted string of preferences
        """
        if query:
            preferences = await self.get_relevant_preferences(query, threshold, limit)
        else:
            preferences = self.get_all_preferences()
        
        if not preferences:
            return ""
        
        # Group preferences by category
        by_category = {}
        for pref in preferences:
            category = pref["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(pref)
        
        # Format as text
        lines = ["User Preferences:"]
        for category, prefs in sorted(by_category.items()):
            lines.append(f"\n{category.replace('_', ' ').title()}:")
            for pref in prefs:
                confidence_str = f" (confidence: {pref['confidence']:.2f})" if pref['confidence'] < 1.0 else ""
                relevance_str = f" [relevance: {pref.get('relevance_score', 1.0):.2f}]" if 'relevance_score' in pref else ""
                lines.append(f"  - {pref['preference']}{confidence_str}{relevance_str}")
        
        return "\n".join(lines)

