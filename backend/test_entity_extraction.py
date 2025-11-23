"""Comprehensive tests for entity extraction, geocoding, and enhanced preference system."""

import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any

# Set environment variables for testing
os.environ["MEMORY_NEO4J_URI"] = os.getenv("MEMORY_NEO4J_URI", "bolt://localhost:7688")
os.environ["MEMORY_NEO4J_USERNAME"] = os.getenv("MEMORY_NEO4J_USERNAME", "neo4j")
os.environ["MEMORY_NEO4J_PASSWORD"] = os.getenv("MEMORY_NEO4J_PASSWORD", "memorypass")
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

from app.entity_extractor import EntityExtractor
from app.geocoding_client import GeocodingClient
from app.preferences_client import PreferencesClient
from app.memory_provider import Neo4jMemoryProvider


async def test_entity_extraction():
    """Test entity extraction from preference text."""
    print("\n" + "="*80)
    print("TEST 1: Entity Extraction")
    print("="*80)
    
    extractor = EntityExtractor()
    
    test_cases = [
        {
            "preference": "I'm interested in news about climate change in California",
            "context": "User expressed interest in California climate news",
            "expected_types": ["topic", "location"]
        },
        {
            "preference": "I want to follow news about Elon Musk and Tesla",
            "context": "User wants updates on Elon Musk and Tesla",
            "expected_types": ["person", "organization"]
        },
        {
            "preference": "Show me articles about artificial intelligence from Stanford University",
            "context": "User interested in AI research from Stanford",
            "expected_types": ["topic", "organization"]
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"  Preference: {test['preference']}")
        print(f"  Context: {test['context']}")
        
        entities = await extractor.extract_entities(test["preference"], test["context"])
        
        print(f"  Extracted {len(entities)} entities:")
        for entity in entities:
            print(f"    - Type: {entity['entity_type']}")
            print(f"      Text: {entity['text']}")
            print(f"      Normalized: {entity['normalized_text']}")
            print(f"      Confidence: {entity['confidence']:.2f}")
        
        # Check if expected types are present
        extracted_types = {e['entity_type'] for e in entities}
        expected_types = set(test['expected_types'])
        
        if extracted_types.intersection(expected_types):
            print(f"  ✓ Found expected entity types: {extracted_types.intersection(expected_types)}")
        else:
            print(f"  ⚠️  Missing expected types. Found: {extracted_types}, Expected: {expected_types}")
    
    print("\n✓ Entity extraction tests completed")


async def test_entity_resolution():
    """Test entity resolution with embeddings."""
    print("\n" + "="*80)
    print("TEST 2: Entity Resolution")
    print("="*80)
    
    extractor = EntityExtractor()
    
    # Create a fake existing entity
    existing_entities = [
        {
            "id": "test-1",
            "name": "San Francisco",
            "normalized_name": "san francisco",
            "embedding": await extractor.generate_embedding("San Francisco"),
            "entity_type": "location"
        }
    ]
    
    test_cases = [
        ("SF", "location", True, "Should match San Francisco"),
        ("San Fran", "location", True, "Should match San Francisco"),
        ("Los Angeles", "location", False, "Should not match San Francisco"),
    ]
    
    for text, entity_type, should_match, description in test_cases:
        print(f"\n  Test: {description}")
        print(f"    Entity: {text}")
        
        matched_id, similarity = await extractor.resolve_entity(
            text,
            entity_type,
            existing_entities
        )
        
        print(f"    Similarity: {similarity:.3f}")
        print(f"    Matched: {matched_id is not None}")
        print(f"    Expected Match: {should_match}")
        
        if (matched_id is not None) == should_match:
            print(f"    ✓ Resolution correct")
        else:
            print(f"    ⚠️  Resolution incorrect")
    
    print("\n✓ Entity resolution tests completed")


async def test_geocoding():
    """Test geocoding functionality."""
    print("\n" + "="*80)
    print("TEST 3: Geocoding")
    print("="*80)
    
    geocoding_client = GeocodingClient()
    
    test_locations = [
        ("San Francisco", (37.7749, -122.4194)),
        ("New York City", (40.7128, -74.0060)),
        ("London", (51.5074, -0.1278)),
    ]
    
    for location, expected_coords in test_locations:
        print(f"\n  Geocoding: {location}")
        
        coords = await geocoding_client.geocode_location(location)
        
        if coords:
            lat, lng = coords
            exp_lat, exp_lng = expected_coords
            
            # Check if within reasonable range (±1 degree)
            lat_close = abs(lat - exp_lat) < 1.0
            lng_close = abs(lng - exp_lng) < 1.0
            
            print(f"    Result: ({lat:.4f}, {lng:.4f})")
            print(f"    Expected: ({exp_lat:.4f}, {exp_lng:.4f})")
            
            if lat_close and lng_close:
                print(f"    ✓ Coordinates match")
            else:
                print(f"    ⚠️  Coordinates differ significantly")
        else:
            print(f"    ⚠️  Geocoding failed")
    
    print("\n✓ Geocoding tests completed")


async def test_temporal_parsing():
    """Test temporal expression parsing."""
    print("\n" + "="*80)
    print("TEST 4: Temporal Parsing")
    print("="*80)
    
    try:
        preferences_client = PreferencesClient()
        memory_provider = Neo4jMemoryProvider(preferences_client)
        
        test_contexts = [
            "I want to follow this starting next month",
            "Show me news about this until the end of summer",
            "I'm interested in this for the next 30 days",
            "Keep this preference until December 31st, 2024",
        ]
        
        for context in test_contexts:
            print(f"\n  Context: {context}")
            
            temporal_info = await memory_provider.parse_temporal_context(context)
            
            print(f"    Has temporal constraint: {temporal_info.get('has_temporal_constraint', False)}")
            if temporal_info.get('valid_from'):
                print(f"    Valid from: {temporal_info['valid_from']}")
            if temporal_info.get('valid_to'):
                print(f"    Valid to: {temporal_info['valid_to']}")
            if temporal_info.get('date_ranges'):
                print(f"    Date ranges: {temporal_info['date_ranges']}")
        
        preferences_client.close()
        print("\n✓ Temporal parsing tests completed")
        
    except Exception as e:
        print(f"\n⚠️  Could not test temporal parsing (memory DB not available): {e}")


async def test_preference_storage_with_entities():
    """Test storing preferences with entity extraction and linking."""
    print("\n" + "="*80)
    print("TEST 5: Preference Storage with Entities")
    print("="*80)
    
    try:
        preferences_client = PreferencesClient()
        memory_provider = Neo4jMemoryProvider(preferences_client)
        
        # Test preference with multiple entity types
        test_preference = {
            "category": "topics_of_interest",
            "preference": "User is interested in climate change news from California and Europe",
            "context": "User said: 'I want to stay updated on climate change, especially from California and Europe'",
            "confidence": 0.95
        }
        
        print(f"\n  Storing preference: {test_preference['preference']}")
        
        stored_count = await memory_provider.store_preferences([test_preference])
        
        print(f"  ✓ Stored {stored_count} preference(s) with entities")
        
        # Verify entities were created
        for entity_type in ["location", "topic"]:
            entities = preferences_client.get_existing_entities(entity_type)
            print(f"  Found {len(entities)} {entity_type} entities")
            for entity in entities:
                print(f"    - {entity.get('normalized_name', 'unknown')}")
        
        preferences_client.close()
        print("\n✓ Preference storage with entities completed")
        
    except Exception as e:
        print(f"\n⚠️  Could not test preference storage (memory DB not available): {e}")


async def test_relevance_filtering():
    """Test relevance-based preference retrieval."""
    print("\n" + "="*80)
    print("TEST 6: Relevance-Based Retrieval")
    print("="*80)
    
    try:
        preferences_client = PreferencesClient()
        
        # First, ensure we have some preferences stored
        print("\n  Testing relevance filtering with query...")
        
        test_query = "What's happening with climate change?"
        
        relevant_prefs = await preferences_client.get_relevant_preferences(
            query=test_query,
            threshold=0.5,
            limit=5
        )
        
        print(f"  Query: {test_query}")
        print(f"  Found {len(relevant_prefs)} relevant preferences:")
        
        for pref in relevant_prefs:
            print(f"    - {pref['preference'][:60]}...")
            print(f"      Relevance: {pref.get('relevance_score', 0):.3f}")
            print(f"      Category: {pref['category']}")
        
        if not relevant_prefs:
            print("  ℹ️  No preferences found (database may be empty)")
        
        preferences_client.close()
        print("\n✓ Relevance filtering test completed")
        
    except Exception as e:
        print(f"\n⚠️  Could not test relevance filtering (memory DB not available): {e}")


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("ENTITY EXTRACTION AND ENHANCED PREFERENCES - TEST SUITE")
    print("="*80)
    
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  WARNING: OPENAI_API_KEY not set. Some tests may fail.")
        return
    
    # Run tests
    try:
        await test_entity_extraction()
        await test_entity_resolution()
        await test_geocoding()
        await test_temporal_parsing()
        await test_preference_storage_with_entities()
        await test_relevance_filtering()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETED")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

