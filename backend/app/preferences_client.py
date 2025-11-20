"""Neo4j client for managing user preferences in a separate Neo4j instance."""

import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

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
                    # Create constraint for UserPreference id (unique)
                    session.run(
                        "CREATE CONSTRAINT preference_id_unique IF NOT EXISTS "
                        "FOR (p:UserPreference) REQUIRE p.id IS UNIQUE"
                    )
                    
                    # Create composite index for category and preference (for duplicate detection)
                    session.run(
                        "CREATE INDEX preference_category_text_idx IF NOT EXISTS "
                        "FOR (p:UserPreference) ON (p.category, p.preference)"
                    )
                    
                    # Create index for created_at
                    session.run(
                        "CREATE INDEX preference_created_idx IF NOT EXISTS "
                        "FOR (p:UserPreference) ON (p.created_at)"
                    )
                    
                    # Create constraint for PreferenceCategory name (unique)
                    session.run(
                        "CREATE CONSTRAINT category_name_unique IF NOT EXISTS "
                        "FOR (c:PreferenceCategory) REQUIRE c.name IS UNIQUE"
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

    def store_preference(
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
                    pref.created_at = datetime($created_at),
                    pref.last_updated = datetime($created_at)
                ON MATCH SET
                    pref.context = $context,
                    pref.confidence = $confidence,
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
                    "created_at": now.isoformat()
                }
            )
            
            record = result.single()
            return record["id"] if record else str(uuid.uuid4())

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

