#!/usr/bin/env python3
"""Script to set up the preferences database in Neo4j."""

import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def create_preferences_database():
    """Create the preferences database in Neo4j."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database_name = os.getenv("NEO4J_PREFERENCES_DATABASE", "preferences")
    
    print(f"Connecting to Neo4j at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    try:
        # Check if we can connect
        with driver.session(database="system") as session:
            # Check Neo4j edition
            result = session.run("CALL dbms.components() YIELD edition RETURN edition")
            record = result.single()
            edition = record["edition"] if record else "unknown"
            
            print(f"Neo4j edition: {edition}")
            
            # Create the database if it doesn't exist
            # Note: This requires Neo4j Enterprise or Aura
            # For Community edition, a single database is used
            try:
                print(f"\nAttempting to create database '{database_name}'...")
                session.run(f"CREATE DATABASE {database_name} IF NOT EXISTS")
                print(f"✓ Database '{database_name}' created successfully")
            except Exception as e:
                error_msg = str(e)
                if "CREATE DATABASE" in error_msg or "Unsupported" in error_msg:
                    print(f"\n⚠️  Note: Your Neo4j edition ({edition}) may not support multiple databases.")
                    print(f"   Multi-database support requires Neo4j Enterprise or AuraDB.")
                    print(f"\n   For Community Edition:")
                    print(f"   - All data (news and preferences) will be stored in the default 'neo4j' database")
                    print(f"   - The application will still work correctly")
                    print(f"   - You can use node labels to separate news and preferences data")
                    print(f"\n   To use multi-database features:")
                    print(f"   - Upgrade to Neo4j Enterprise Edition")
                    print(f"   - Or use Neo4j AuraDB (cloud)")
                else:
                    print(f"✗ Error creating database: {e}")
                    raise
        
        # Test connection to preferences database
        print(f"\nTesting connection to '{database_name}' database...")
        with driver.session(database=database_name) as session:
            result = session.run("RETURN 1 as test")
            if result.single():
                print(f"✓ Successfully connected to '{database_name}' database")
        
        print("\n✓ Setup complete!")
        print(f"\nYour preferences will be stored in: {database_name}")
        
    except Exception as e:
        print(f"\n✗ Error during setup: {e}")
        print("\nPlease ensure:")
        print("1. Neo4j is running")
        print("2. Connection details in .env are correct")
        print("3. You have admin privileges")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Neo4j Preferences Database Setup")
    print("=" * 60)
    create_preferences_database()

