#!/usr/bin/env python3
"""
Standalone script to initialize sample news data in Neo4j.

This script creates sample news articles, topics, people, organizations,
geographic locations, and photos in the Neo4j database.

WARNING: This script deletes all existing nodes in the database before
creating sample data. It will only run in 'development' or 'test' environments.

Usage:
    python initialize_sample_data.py

Environment Variables:
    NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USERNAME: Neo4j username (default: neo4j)
    NEO4J_PASSWORD: Neo4j password (default: password)
    ENVIRONMENT: Environment setting - must be 'development' or 'test'
"""

import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def initialize_sample_data():
    """Initialize the database with sample news data.

    WARNING: This method deletes all nodes in the database.
    It will only run in 'development' or 'test' environments.
    """
    # Safety check: only allow in development or test environments
    env = os.getenv("ENVIRONMENT", "production")
    if env not in ("development", "test"):
        print(f"ERROR: Refusing to clear database in unsafe environment: '{env}'")
        print("Set ENVIRONMENT to 'development' or 'test' to allow this operation.")
        sys.exit(1)

    # Get connection parameters
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    print(f"Connecting to Neo4j at {uri}...")
    print(f"Environment: {env}")
    print("\nWARNING: This will delete all existing data in the database!")
    
    # Confirm before proceeding
    response = input("Continue? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        print("Cancelled.")
        sys.exit(0)

    try:
        # Connect to Neo4j
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        with driver.session() as session:
            print("\nClearing existing data...")
            session.run("MATCH (n) DETACH DELETE n")
            print("✓ Existing data cleared")

            print("\nCreating sample news data...")
            # Create sample news articles
            session.run(
                """
                CREATE (a1:Article {
                    title: 'Global Climate Summit Reaches Historic Agreement',
                    abstract: 'World leaders have agreed to ambitious new targets for reducing carbon emissions by 2030. The agreement includes commitments from over 190 countries to transition to renewable energy sources and protect natural ecosystems.',
                    published: '2024-11-10',
                    url: 'https://example.com/news/climate-summit-2024',
                    byline: 'By Global News Network'
                })
                CREATE (a2:Article {
                    title: 'Tech Giants Announce AI Safety Initiative',
                    abstract: 'Major technology companies have joined forces to create new safety standards for artificial intelligence development. The initiative aims to ensure AI systems are developed responsibly and with proper oversight.',
                    published: '2024-11-09',
                    url: 'https://example.com/news/ai-safety-initiative',
                    byline: 'By Tech Today'
                })
                CREATE (a3:Article {
                    title: 'International Space Station Welcomes New Crew',
                    abstract: 'A team of astronauts from five different countries has successfully docked at the International Space Station. They will conduct experiments on materials science and study the effects of long-duration spaceflight.',
                    published: '2024-11-08',
                    url: 'https://example.com/news/iss-new-crew',
                    byline: 'By Space News Daily'
                })
                CREATE (a4:Article {
                    title: 'New Trade Agreement Strengthens Economic Ties',
                    abstract: 'Multiple nations have signed a comprehensive trade agreement that will reduce tariffs and promote economic cooperation. Economists predict the deal will boost GDP growth across participating countries.',
                    published: '2024-11-07',
                    url: 'https://example.com/news/trade-agreement',
                    byline: 'By Business Wire'
                })
                CREATE (a5:Article {
                    title: 'Renewable Energy Investment Reaches Record High',
                    abstract: 'Global investment in renewable energy has surpassed $500 billion this year, marking a new record. Solar and wind power projects are leading the growth, with emerging markets showing particularly strong adoption.',
                    published: '2024-11-06',
                    url: 'https://example.com/news/renewable-energy-investment',
                    byline: 'By Energy Review'
                })

                CREATE (t1:Topic {name: 'Climate Change'})
                CREATE (t2:Topic {name: 'Artificial Intelligence'})
                CREATE (t3:Topic {name: 'Space Exploration'})
                CREATE (t4:Topic {name: 'International Trade'})
                CREATE (t5:Topic {name: 'Renewable Energy'})

                CREATE (p1:Person {name: 'John Smith'})
                CREATE (p2:Person {name: 'Sarah Johnson'})
                CREATE (p3:Person {name: 'Michael Chen'})

                CREATE (o1:Organization {name: 'United Nations'})
                CREATE (o2:Organization {name: 'Tech Alliance'})
                CREATE (o3:Organization {name: 'NASA'})

                CREATE (g1:Geo {
                    name: 'Global',
                    location: point({longitude: 0.0, latitude: 0.0})
                })
                CREATE (g2:Geo {
                    name: 'United States',
                    location: point({longitude: -95.7129, latitude: 37.0902})
                })
                CREATE (g3:Geo {
                    name: 'Europe',
                    location: point({longitude: 10.4515, latitude: 51.1657})
                })

                CREATE (ph1:Photo {
                    url: 'https://example.com/images/climate-summit.jpg',
                    caption: 'World leaders at the Climate Summit'
                })
                CREATE (ph2:Photo {
                    url: 'https://example.com/images/ai-safety.jpg',
                    caption: 'Tech executives announce AI safety initiative'
                })
                CREATE (ph3:Photo {
                    url: 'https://example.com/images/iss-crew.jpg',
                    caption: 'New crew members aboard the International Space Station'
                })

                CREATE (a1)-[:HAS_TOPIC]->(t1)
                CREATE (a1)-[:ABOUT_ORGANIZATION]->(o1)
                CREATE (a1)-[:ABOUT_GEO]->(g1)
                CREATE (a1)-[:HAS_PHOTO]->(ph1)

                CREATE (a2)-[:HAS_TOPIC]->(t2)
                CREATE (a2)-[:ABOUT_ORGANIZATION]->(o2)
                CREATE (a2)-[:ABOUT_PERSON]->(p1)
                CREATE (a2)-[:ABOUT_GEO]->(g2)
                CREATE (a2)-[:HAS_PHOTO]->(ph2)

                CREATE (a3)-[:HAS_TOPIC]->(t3)
                CREATE (a3)-[:ABOUT_ORGANIZATION]->(o3)
                CREATE (a3)-[:ABOUT_PERSON]->(p2)
                CREATE (a3)-[:ABOUT_GEO]->(g1)
                CREATE (a3)-[:HAS_PHOTO]->(ph3)

                CREATE (a4)-[:HAS_TOPIC]->(t4)
                CREATE (a4)-[:ABOUT_PERSON]->(p3)
                CREATE (a4)-[:ABOUT_GEO]->(g3)

                CREATE (a5)-[:HAS_TOPIC]->(t5)
                CREATE (a5)-[:ABOUT_GEO]->(g1)
                """
            )
            print("✓ Sample data created")

        driver.close()
        
        print("\n" + "=" * 60)
        print("SUCCESS: Sample data initialized successfully!")
        print("=" * 60)
        print("\nCreated:")
        print("  • 5 news articles")
        print("  • 5 topics")
        print("  • 3 people")
        print("  • 3 organizations")
        print("  • 3 geographic locations")
        print("  • 3 photos")
        print("\nYou can now query the data through the chat interface.")
        
    except Exception as e:
        print(f"\nERROR: Failed to initialize sample data: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    initialize_sample_data()

