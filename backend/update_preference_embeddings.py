"""Utility script to update existing user preferences with embeddings."""

import asyncio
import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from app.preferences_client import PreferencesClient
from dotenv import load_dotenv


async def main():
    """Update all preferences that don't have embeddings."""
    load_dotenv()
    
    print("=" * 60)
    print("User Preference Embedding Update Utility")
    print("=" * 60)
    print()
    
    # Check if MEMORY_NEO4J_URI is set
    if not os.getenv("MEMORY_NEO4J_URI"):
        print("❌ Error: MEMORY_NEO4J_URI environment variable is not set")
        print("   Please set this variable to your Neo4j memory database URI")
        return 1
    
    try:
        # Initialize the preferences client
        print("Connecting to Neo4j memory database...")
        preferences_client = PreferencesClient()
        print("✓ Connected successfully")
        print()
        
        # Get current preferences summary
        summary = preferences_client.get_preferences_summary()
        print(f"Found {summary['total_preferences']} total preferences")
        print(f"Categories: {', '.join(summary['categories']) if summary['categories'] else 'None'}")
        print()
        
        if summary['total_preferences'] == 0:
            print("ℹ️  No preferences found. Nothing to update.")
            preferences_client.close()
            return 0
        
        # Update embeddings
        print("Updating preferences with embeddings...")
        print("-" * 60)
        updated_count = await preferences_client.update_preference_embeddings()
        print("-" * 60)
        print()
        
        if updated_count > 0:
            print(f"✓ Successfully updated {updated_count} preferences with embeddings")
        else:
            print("✓ All preferences already have embeddings")
        
        # Close the connection
        preferences_client.close()
        print()
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

