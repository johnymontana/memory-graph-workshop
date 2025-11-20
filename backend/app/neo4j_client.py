"""Neo4j client for connecting to the database."""

import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from neo4j import GraphDatabase
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class Neo4jClient:
    """Client for interacting with Neo4j database."""

    def __init__(self):
        """Initialize Neo4j connection and OpenAI client."""
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")

        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        
        # Initialize OpenAI client for embeddings
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        self.openai_client = OpenAI(api_key=openai_api_key)

    def close(self):
        """Close the database connection."""
        self.driver.close()

    def search_news(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for news articles matching the query.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of news articles with their properties
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:Article)
                WHERE toLower(a.title) CONTAINS toLower($query)
                   OR toLower(a.abstract) CONTAINS toLower($query)
                   OR toLower(a.byline) CONTAINS toLower($query)
                OPTIONAL MATCH (a)-[:HAS_TOPIC]->(topic:Topic)
                OPTIONAL MATCH (a)-[:ABOUT_PERSON]->(person:Person)
                OPTIONAL MATCH (a)-[:ABOUT_ORGANIZATION]->(org:Organization)
                OPTIONAL MATCH (a)-[:ABOUT_GEO]->(geo:Geo)
                OPTIONAL MATCH (a)-[:HAS_PHOTO]->(photo:Photo)
                RETURN a.title as title,
                       a.abstract as abstract,
                       a.published as published,
                       a.url as url,
                       a.byline as byline,
                       collect(DISTINCT topic.name) as topics,
                       collect(DISTINCT person.name) as people,
                       collect(DISTINCT org.name) as organizations,
                       collect(DISTINCT geo.name) as locations,
                       collect(DISTINCT photo.url) as photoUrls
                ORDER BY a.published DESC
                LIMIT $limit
                """,
                {"query": query, "limit": limit}
            )

            articles = []
            for record in result:
                articles.append({
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "published": record["published"],
                    "url": record["url"],
                    "byline": record["byline"],
                    "topics": [t for t in record["topics"] if t],
                    "people": [p for p in record["people"] if p],
                    "organizations": [o for o in record["organizations"] if o],
                    "locations": [l for l in record["locations"] if l],
                    "photoUrls": [p for p in record["photoUrls"] if p]
                })

            return articles

    def get_recent_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent news articles.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of recent news articles
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:Article)
                OPTIONAL MATCH (a)-[:HAS_TOPIC]->(topic:Topic)
                OPTIONAL MATCH (a)-[:ABOUT_PERSON]->(person:Person)
                OPTIONAL MATCH (a)-[:ABOUT_ORGANIZATION]->(org:Organization)
                OPTIONAL MATCH (a)-[:ABOUT_GEO]->(geo:Geo)
                OPTIONAL MATCH (a)-[:HAS_PHOTO]->(photo:Photo)
                RETURN a.title as title,
                       a.abstract as abstract,
                       a.published as published,
                       a.url as url,
                       a.byline as byline,
                       collect(DISTINCT topic.name) as topics,
                       collect(DISTINCT person.name) as people,
                       collect(DISTINCT org.name) as organizations,
                       collect(DISTINCT geo.name) as locations,
                       collect(DISTINCT photo.url) as photoUrls
                ORDER BY a.published DESC
                LIMIT $limit
                """,
                {"limit": limit}
            )

            articles = []
            for record in result:
                articles.append({
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "published": record["published"],
                    "url": record["url"],
                    "byline": record["byline"],
                    "topics": [t for t in record["topics"] if t],
                    "people": [p for p in record["people"] if p],
                    "organizations": [o for o in record["organizations"] if o],
                    "locations": [l for l in record["locations"] if l],
                    "photoUrls": [p for p in record["photoUrls"] if p]
                })

            return articles

    def get_news_by_topic(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get news articles by topic.

        Args:
            topic: Topic name to filter by
            limit: Maximum number of results to return

        Returns:
            List of news articles about the topic
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:Article)-[:HAS_TOPIC]->(topic:Topic)
                WHERE toLower(topic.name) = toLower($topic)
                OPTIONAL MATCH (a)-[:ABOUT_PERSON]->(person:Person)
                OPTIONAL MATCH (a)-[:ABOUT_ORGANIZATION]->(org:Organization)
                OPTIONAL MATCH (a)-[:ABOUT_GEO]->(geo:Geo)
                OPTIONAL MATCH (a)-[:HAS_PHOTO]->(photo:Photo)
                RETURN a.title as title,
                       a.abstract as abstract,
                       a.published as published,
                       a.url as url,
                       a.byline as byline,
                       collect(DISTINCT topic.name) as topics,
                       collect(DISTINCT person.name) as people,
                       collect(DISTINCT org.name) as organizations,
                       collect(DISTINCT geo.name) as locations,
                       collect(DISTINCT photo.url) as photoUrls
                ORDER BY a.published DESC
                LIMIT $limit
                """,
                {"topic": topic, "limit": limit}
            )

            articles = []
            for record in result:
                articles.append({
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "published": record["published"],
                    "url": record["url"],
                    "byline": record["byline"],
                    "topics": [t for t in record["topics"] if t],
                    "people": [p for p in record["people"] if p],
                    "organizations": [o for o in record["organizations"] if o],
                    "locations": [l for l in record["locations"] if l],
                    "photoUrls": [p for p in record["photoUrls"] if p]
                })

            return articles

    def get_topics(self) -> List[str]:
        """
        Get all available news topics.

        Returns:
            List of topic names
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Topic)
                RETURN DISTINCT t.name as topic
                ORDER BY topic
                """
            )

            return [record["topic"] for record in result if record["topic"]]

    def get_categories(self) -> List[str]:
        """
        Get all available news topics (alias for get_topics for backward compatibility).

        Returns:
            List of topic names
        """
        return self.get_topics()

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for the given text using OpenAI's text-embedding-3-small model.

        Args:
            text: Text to generate embedding for

        Returns:
            List of floats representing the embedding vector
        """
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def vector_search_news(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for news articles using vector similarity search.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of news articles with similarity scores and their properties
        """
        # Generate embedding for the query
        query_embedding = self.generate_embedding(query)

        with self.driver.session() as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes('article_embedding_index', $limit, $embedding)
                YIELD node, score
                WITH node as a, score
                OPTIONAL MATCH (a)-[:HAS_TOPIC]->(topic:Topic)
                OPTIONAL MATCH (a)-[:ABOUT_PERSON]->(person:Person)
                OPTIONAL MATCH (a)-[:ABOUT_ORGANIZATION]->(org:Organization)
                OPTIONAL MATCH (a)-[:ABOUT_GEO]->(geo:Geo)
                OPTIONAL MATCH (a)-[:HAS_PHOTO]->(photo:Photo)
                RETURN a.title as title,
                       a.abstract as abstract,
                       a.published as published,
                       a.url as url,
                       a.byline as byline,
                       score,
                       collect(DISTINCT topic.name) as topics,
                       collect(DISTINCT person.name) as people,
                       collect(DISTINCT org.name) as organizations,
                       collect(DISTINCT geo.name) as locations,
                       collect(DISTINCT photo.url) as photoUrls
                ORDER BY score DESC
                """,
                {"embedding": query_embedding, "limit": limit}
            )

            articles = []
            for record in result:
                articles.append({
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "published": record["published"],
                    "url": record["url"],
                    "byline": record["byline"],
                    "similarity_score": record["score"],
                    "topics": [t for t in record["topics"] if t],
                    "people": [p for p in record["people"] if p],
                    "organizations": [o for o in record["organizations"] if o],
                    "locations": [l for l in record["locations"] if l],
                    "photoUrls": [p for p in record["photoUrls"] if p]
                })

            return articles

    def create_geospatial_index(self) -> None:
        """
        Create a point index on Geo.location for efficient geospatial queries.
        This should be called during database initialization.
        """
        with self.driver.session() as session:
            session.run(
                "CREATE POINT INDEX geo_location_idx IF NOT EXISTS FOR (g:Geo) ON (g.location)"
            )

    def search_news_by_location(
        self, 
        latitude: float, 
        longitude: float, 
        radius_km: float = 100, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for news articles about locations within a specified distance.

        Args:
            latitude: Latitude of the center point
            longitude: Longitude of the center point
            radius_km: Search radius in kilometers (default: 100)
            limit: Maximum number of results to return

        Returns:
            List of news articles with distance information
        """
        with self.driver.session() as session:
            result = session.run(
                """
                WITH point({latitude: $latitude, longitude: $longitude}) AS center
                MATCH (g:Geo)
                WHERE point.distance(g.location, center) <= $radius_meters
                WITH g, point.distance(g.location, center) / 1000.0 AS distance_km
                MATCH (a:Article)-[:ABOUT_GEO]->(g)
                OPTIONAL MATCH (a)-[:HAS_TOPIC]->(topic:Topic)
                OPTIONAL MATCH (a)-[:ABOUT_PERSON]->(person:Person)
                OPTIONAL MATCH (a)-[:ABOUT_ORGANIZATION]->(org:Organization)
                OPTIONAL MATCH (a)-[:HAS_PHOTO]->(photo:Photo)
                WITH a, g, distance_km, 
                     collect(DISTINCT topic.name) as topics,
                     collect(DISTINCT person.name) as people,
                     collect(DISTINCT org.name) as organizations,
                     collect(DISTINCT photo.url) as photoUrls
                RETURN DISTINCT a.title as title,
                       a.abstract as abstract,
                       a.published as published,
                       a.url as url,
                       a.byline as byline,
                       g.name as location_name,
                       distance_km,
                       topics,
                       people,
                       organizations,
                       photoUrls
                ORDER BY distance_km ASC, a.published DESC
                LIMIT $limit
                """,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_meters": radius_km * 1000,  # Convert km to meters
                    "limit": limit
                }
            )

            articles = []
            for record in result:
                articles.append({
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "published": record["published"],
                    "url": record["url"],
                    "byline": record["byline"],
                    "location_name": record["location_name"],
                    "distance_km": round(record["distance_km"], 2),
                    "topics": [t for t in record["topics"] if t],
                    "people": [p for p in record["people"] if p],
                    "organizations": [o for o in record["organizations"] if o],
                    "photoUrls": [p for p in record["photoUrls"] if p]
                })

            return articles

    def _parse_date_input(self, date_input: Union[str, datetime]) -> str:
        """
        Parse date input that can be either an explicit date string or a relative period.

        Args:
            date_input: Date string (YYYY-MM-DD) or relative period 
                       (last_week, last_month, last_7_days, last_30_days, etc.)

        Returns:
            Date string in YYYY-MM-DD format
        """
        if isinstance(date_input, datetime):
            return date_input.strftime("%Y-%m-%d")
        
        date_str = str(date_input).lower().strip()
        
        # If it looks like a date string already, return it
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return date_str
        
        # Parse relative periods
        now = datetime.now()
        
        if date_str == "today":
            return now.strftime("%Y-%m-%d")
        elif date_str == "yesterday":
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")
        elif date_str in ["last_week", "last week"]:
            return (now - timedelta(weeks=1)).strftime("%Y-%m-%d")
        elif date_str in ["last_month", "last month"]:
            return (now - timedelta(days=30)).strftime("%Y-%m-%d")
        elif date_str.startswith("last_") and date_str.endswith("_days"):
            # Extract number from "last_N_days"
            try:
                days = int(date_str.split("_")[1])
                return (now - timedelta(days=days)).strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                pass
        
        # If we can't parse it, return as-is and let the database handle it
        return date_str

    def search_news_by_date_range(
        self,
        start_date: Union[str, datetime, None] = None,
        end_date: Union[str, datetime, None] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for news articles within a date range.

        Args:
            start_date: Start date (YYYY-MM-DD) or relative period (last_week, last_7_days, etc.)
                       If None, no lower bound is applied
            end_date: End date (YYYY-MM-DD) or relative period
                     If None, defaults to today
            limit: Maximum number of results to return

        Returns:
            List of news articles within the date range
        """
        # Parse dates
        if start_date:
            parsed_start = self._parse_date_input(start_date)
        else:
            parsed_start = None
            
        if end_date:
            parsed_end = self._parse_date_input(end_date)
        else:
            parsed_end = datetime.now().strftime("%Y-%m-%d")

        with self.driver.session() as session:
            # Build the query dynamically based on which dates are provided
            if parsed_start and parsed_end:
                where_clause = "WHERE a.published >= $start_date AND a.published <= $end_date"
                params = {"start_date": parsed_start, "end_date": parsed_end, "limit": limit}
            elif parsed_start:
                where_clause = "WHERE a.published >= $start_date"
                params = {"start_date": parsed_start, "limit": limit}
            elif parsed_end:
                where_clause = "WHERE a.published <= $end_date"
                params = {"end_date": parsed_end, "limit": limit}
            else:
                where_clause = ""
                params = {"limit": limit}

            query = f"""
                MATCH (a:Article)
                {where_clause}
                OPTIONAL MATCH (a)-[:HAS_TOPIC]->(topic:Topic)
                OPTIONAL MATCH (a)-[:ABOUT_PERSON]->(person:Person)
                OPTIONAL MATCH (a)-[:ABOUT_ORGANIZATION]->(org:Organization)
                OPTIONAL MATCH (a)-[:ABOUT_GEO]->(geo:Geo)
                OPTIONAL MATCH (a)-[:HAS_PHOTO]->(photo:Photo)
                RETURN a.title as title,
                       a.abstract as abstract,
                       a.published as published,
                       a.url as url,
                       a.byline as byline,
                       collect(DISTINCT topic.name) as topics,
                       collect(DISTINCT person.name) as people,
                       collect(DISTINCT org.name) as organizations,
                       collect(DISTINCT geo.name) as locations,
                       collect(DISTINCT photo.url) as photoUrls
                ORDER BY a.published DESC
                LIMIT $limit
            """

            result = session.run(query, params)

            articles = []
            for record in result:
                articles.append({
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "published": record["published"],
                    "url": record["url"],
                    "byline": record["byline"],
                    "topics": [t for t in record["topics"] if t],
                    "people": [p for p in record["people"] if p],
                    "organizations": [o for o in record["organizations"] if o],
                    "locations": [l for l in record["locations"] if l],
                    "photoUrls": [p for p in record["photoUrls"] if p]
                })

            return articles

    def get_database_schema(self) -> Dict[str, Any]:
        """
        Get the Neo4j database schema including node labels, relationship types,
        properties, and constraints.

        Returns:
            Dictionary containing schema information
        """
        with self.driver.session() as session:
            # Get node labels and their properties
            node_labels_result = session.run("""
                CALL db.labels() YIELD label
                RETURN label
            """)
            labels = [record["label"] for record in node_labels_result]
            
            # Get relationship types
            rel_types_result = session.run("""
                CALL db.relationshipTypes() YIELD relationshipType
                RETURN relationshipType
            """)
            relationship_types = [record["relationshipType"] for record in rel_types_result]
            
            # Get property keys
            property_keys_result = session.run("""
                CALL db.propertyKeys() YIELD propertyKey
                RETURN propertyKey
            """)
            property_keys = [record["propertyKey"] for record in property_keys_result]
            
            # Get constraints
            constraints_result = session.run("""
                SHOW CONSTRAINTS
            """)
            constraints = []
            for record in constraints_result:
                constraints.append({
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "entityType": record.get("entityType"),
                    "labelsOrTypes": record.get("labelsOrTypes"),
                    "properties": record.get("properties")
                })
            
            # Get indexes
            indexes_result = session.run("""
                SHOW INDEXES
            """)
            indexes = []
            for record in indexes_result:
                indexes.append({
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "entityType": record.get("entityType"),
                    "labelsOrTypes": record.get("labelsOrTypes"),
                    "properties": record.get("properties")
                })
            
            # Try to get more detailed schema information
            # Sample each node label to get properties
            node_properties = {}
            for label in labels:
                try:
                    props_result = session.run(f"""
                        MATCH (n:`{label}`)
                        WITH n LIMIT 1
                        RETURN keys(n) as properties
                    """)
                    record = props_result.single()
                    if record:
                        node_properties[label] = record["properties"]
                except Exception:
                    node_properties[label] = []
            
            # Get relationship patterns
            relationship_patterns = []
            try:
                patterns_result = session.run("""
                    MATCH (a)-[r]->(b)
                    WITH DISTINCT labels(a)[0] as fromLabel, type(r) as relType, labels(b)[0] as toLabel
                    RETURN fromLabel, relType, toLabel
                    LIMIT 100
                """)
                for record in patterns_result:
                    if record["fromLabel"] and record["relType"] and record["toLabel"]:
                        relationship_patterns.append({
                            "from": record["fromLabel"],
                            "relationship": record["relType"],
                            "to": record["toLabel"]
                        })
            except Exception:
                pass
            
            schema = {
                "node_labels": labels,
                "relationship_types": relationship_types,
                "property_keys": property_keys,
                "node_properties": node_properties,
                "relationship_patterns": relationship_patterns,
                "constraints": constraints,
                "indexes": indexes
            }
            
            return schema

    def execute_read_query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a read-only Cypher query.
        
        Args:
            cypher: The Cypher query to execute (must be read-only)
            params: Optional parameters for the query
            
        Returns:
            List of result records as dictionaries
            
        Raises:
            ValueError: If the query contains write operations
        """
        # Validate that the query is read-only
        query_upper = cypher.strip().upper()
        
        # Remove comments
        query_lines = []
        for line in query_upper.split('\n'):
            # Remove line comments
            if '//' in line:
                line = line[:line.index('//')]
            query_lines.append(line)
        query_upper = ' '.join(query_lines)
        
        # Check for write operations
        write_keywords = ['CREATE', 'MERGE', 'DELETE', 'REMOVE', 'SET', 'DROP', 'DETACH']
        for keyword in write_keywords:
            # Use word boundaries to avoid false positives (e.g., "CREATE" in a string)
            if f' {keyword} ' in f' {query_upper} ' or query_upper.startswith(f'{keyword} '):
                raise ValueError(f"Query contains write operation '{keyword}'. Only read queries are allowed.")
        
        # Execute the query
        if params is None:
            params = {}
            
        with self.driver.session() as session:
            result = session.run(cypher, params)
            
            # Convert results to list of dictionaries
            records = []
            for record in result:
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    # Handle Neo4j-specific types
                    if hasattr(value, '__dict__'):
                        # For nodes and relationships, convert to dict
                        if hasattr(value, 'items'):
                            record_dict[key] = dict(value.items())
                        else:
                            record_dict[key] = dict(value)
                    elif isinstance(value, list):
                        # Handle lists (might contain nodes/relationships)
                        record_dict[key] = [
                            dict(v.items()) if hasattr(v, 'items') else 
                            dict(v) if hasattr(v, '__dict__') else v
                            for v in value
                        ]
                    else:
                        record_dict[key] = value
                records.append(record_dict)
            
            return records

    def generate_cypher_from_text(self, natural_language_query: str, schema: Dict[str, Any]) -> str:
        """
        Generate a Cypher query from a natural language description using OpenAI.
        
        Args:
            natural_language_query: Natural language description of the query
            schema: Database schema information
            
        Returns:
            Generated Cypher query as a string
        """
        # Build a comprehensive prompt with schema context
        schema_description = f"""
# Neo4j Database Schema

## Node Labels
{', '.join(schema['node_labels'])}

## Relationship Types
{', '.join(schema['relationship_types'])}

## Node Properties by Label
"""
        for label, properties in schema['node_properties'].items():
            schema_description += f"\n### {label}\nProperties: {', '.join(properties)}\n"
        
        if schema['relationship_patterns']:
            schema_description += "\n## Common Relationship Patterns\n"
            for pattern in schema['relationship_patterns'][:20]:  # Limit to first 20
                schema_description += f"- ({pattern['from']})-[:{pattern['relationship']}]->({pattern['to']})\n"
        
        prompt = f"""{schema_description}

# Task
Generate a Cypher query for the following natural language request:
"{natural_language_query}"

# Instructions
- Return ONLY the Cypher query without any explanation or markdown formatting
- Use proper Cypher syntax
- Make the query efficient and follow Neo4j best practices
- Use appropriate MATCH patterns based on the relationship patterns shown above
- Include relevant RETURN clauses to get useful information
- Use LIMIT clauses when appropriate to avoid returning too much data
- If the request involves searching text, use toLower() for case-insensitive matching
- For semantic searches, assume vector search capabilities if needed

Generate the Cypher query:"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Neo4j Cypher query expert. Generate only valid Cypher queries without any additional text or formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        cypher_query = response.choices[0].message.content.strip()
        
        # Clean up the response - remove markdown code blocks if present
        if cypher_query.startswith("```"):
            lines = cypher_query.split('\n')
            # Remove first line (```cypher or similar)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cypher_query = '\n'.join(lines).strip()
        
        return cypher_query
