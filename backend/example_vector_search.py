"""
Example usage of vector search functionality.

This script demonstrates how to use the vector search feature
to find semantically similar news articles.
"""

from app.neo4j_client import Neo4jClient


def main():
    """Run vector search examples."""
    # Initialize Neo4j client
    client = Neo4jClient()
    
    print("=" * 70)
    print("Vector Search Examples")
    print("=" * 70)
    
    # Example 1: Climate change query
    print("\n1. Searching for: 'climate change and environmental impact'\n")
    results = client.vector_search_news(
        query="climate change and environmental impact",
        limit=3
    )
    
    for i, article in enumerate(results, 1):
        print(f"{i}. {article['title']}")
        print(f"   Similarity: {article['similarity_score']:.4f}")
        print(f"   Published: {article['published']}")
        if article['topics']:
            print(f"   Topics: {', '.join(article['topics'][:3])}")
        print()
    
    # Example 2: Technology query
    print("-" * 70)
    print("\n2. Searching for: 'breakthroughs in quantum computing'\n")
    results = client.vector_search_news(
        query="breakthroughs in quantum computing",
        limit=3
    )
    
    for i, article in enumerate(results, 1):
        print(f"{i}. {article['title']}")
        print(f"   Similarity: {article['similarity_score']:.4f}")
        print(f"   Published: {article['published']}")
        if article['topics']:
            print(f"   Topics: {', '.join(article['topics'][:3])}")
        print()
    
    # Example 3: Health query
    print("-" * 70)
    print("\n3. Searching for: 'medical advances and healthcare innovation'\n")
    results = client.vector_search_news(
        query="medical advances and healthcare innovation",
        limit=3
    )
    
    for i, article in enumerate(results, 1):
        print(f"{i}. {article['title']}")
        print(f"   Similarity: {article['similarity_score']:.4f}")
        print(f"   Published: {article['published']}")
        if article['abstract']:
            # Print first 100 chars of abstract
            abstract_preview = article['abstract'][:100]
            if len(article['abstract']) > 100:
                abstract_preview += "..."
            print(f"   Summary: {abstract_preview}")
        print()
    
    print("=" * 70)
    
    # Close the connection
    client.close()


if __name__ == "__main__":
    main()

