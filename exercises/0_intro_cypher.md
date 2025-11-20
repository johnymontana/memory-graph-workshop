# Cypher Tutorial for Neo4j: News Article Graph

This tutorial uses a real news article database with over 45,000 articles connected to topics, people, organizations, locations, and photos.

## Database Schema Overview

**Nodes:**
- `Article` - News articles (45,376 nodes)
- `Topic` - Article topics/categories (3,991 nodes)
- `Person` - People mentioned in articles (17,564 nodes)
- `Organization` - Organizations mentioned (8,761 nodes)
- `Geo` - Geographic locations (4,079 nodes)
- `Photo` - Article images (44,491 nodes)

**Relationships:**
- `(Article)-[:HAS_TOPIC]->(Topic)`
- `(Article)-[:ABOUT_PERSON]->(Person)`
- `(Article)-[:ABOUT_ORGANIZATION]->(Organization)`
- `(Article)-[:ABOUT_GEO]->(Geo)`
- `(Article)-[:HAS_PHOTO]->(Photo)`

---

## 1. Basic Pattern Matching with MATCH

The `MATCH` clause finds patterns in the graph. Think of it as drawing the shape of what you're looking for.

### Simple Node Query
```cypher
// Find 5 articles
MATCH (a:Article)
RETURN a.title, a.published
LIMIT 5
```

### Finding Relationships
```cypher
// Find articles and their topics
MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
RETURN a.title, t.name
LIMIT 10
```

### Multiple Relationships
```cypher
// Find articles about specific people with their topics
MATCH (a:Article)-[:ABOUT_PERSON]->(p:Person)
MATCH (a)-[:HAS_TOPIC]->(t:Topic)
RETURN a.title, p.name, collect(t.name) as topics
LIMIT 5
```

---

## 2. Filtering with WHERE

The `WHERE` clause filters results based on conditions.

### Property Filtering
```cypher
// Find articles published in 2025
MATCH (a:Article)
WHERE a.published STARTS WITH '2025'
RETURN a.title, a.published
LIMIT 10
```

### Text Search
```cypher
// Find articles with "workout" in the title
MATCH (a:Article)
WHERE toLower(a.title) CONTAINS 'workout'
RETURN a.title, a.published
LIMIT 5
```

### Multiple Conditions
```cypher
// Find 2025 articles about exercise
MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
WHERE a.published STARTS WITH '2025' 
  AND t.name = 'Exercise'
RETURN a.title, a.published
LIMIT 10
```

---

## 3. Aggregation Functions

Cypher provides powerful aggregation to summarize data.

### Counting
```cypher
// Count articles per topic
MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
RETURN t.name, count(a) as article_count
ORDER BY article_count DESC
LIMIT 10
```

### Collecting Values
```cypher
// Get all topics for each article
MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
RETURN a.title, collect(t.name) as all_topics
LIMIT 5
```

### Statistical Functions
```cypher
// Count articles per person, with stats
MATCH (p:Person)<-[:ABOUT_PERSON]-(a:Article)
WITH p.name as person, count(a) as mentions
RETURN min(mentions) as min_mentions,
       max(mentions) as max_mentions,
       avg(mentions) as avg_mentions,
       count(person) as total_people
```

---

## 4. Pattern Complexity

### Variable-Length Paths
```cypher
// Find articles connected through shared topics (2 hops)
MATCH (a1:Article)-[:HAS_TOPIC]->(t:Topic)<-[:HAS_TOPIC]-(a2:Article)
WHERE a1 <> a2
RETURN a1.title, a2.title, t.name as shared_topic
LIMIT 5
```

### Multiple Node Types
```cypher
// Articles mentioning both a person AND organization
MATCH (a:Article)-[:ABOUT_PERSON]->(p:Person)
MATCH (a)-[:ABOUT_ORGANIZATION]->(o:Organization)
RETURN a.title, p.name as person, o.name as organization
LIMIT 10
```

---

## 5. Ordering and Limiting Results

### Basic Ordering
```cypher
// Most recent articles
MATCH (a:Article)
RETURN a.title, a.published
ORDER BY a.published DESC
LIMIT 10
```

### Ordering by Aggregations
```cypher
// Most mentioned people
MATCH (p:Person)<-[:ABOUT_PERSON]-(a:Article)
RETURN p.name, count(a) as mention_count
ORDER BY mention_count DESC
LIMIT 10
```

---

## 6. Working with Collections

### Filtering Collections
```cypher
// Articles with more than 5 topics
MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
WITH a, collect(t.name) as topics
WHERE size(topics) > 5
RETURN a.title, size(topics) as topic_count, topics
LIMIT 5
```

### Unwinding Collections
```cypher
// Find common co-occurring topics
MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
WITH t, collect(a) as articles
WHERE size(articles) > 100
RETURN t.name, size(articles) as article_count
ORDER BY article_count DESC
LIMIT 10
```

---

## 7. Advanced Patterns

### Finding Co-occurrences
```cypher
// Which people are mentioned together in articles?
MATCH (p1:Person)<-[:ABOUT_PERSON]-(a:Article)-[:ABOUT_PERSON]->(p2:Person)
WHERE id(p1) < id(p2)  // Avoid duplicates
RETURN p1.name, p2.name, count(a) as shared_articles
ORDER BY shared_articles DESC
LIMIT 10
```

### Network Analysis
```cypher
// Articles with the most connections (topics + people + orgs)
MATCH (a:Article)-[r]->(entity)
WITH a, count(r) as connection_count
RETURN a.title, a.published, connection_count
ORDER BY connection_count DESC
LIMIT 10
```

---

## 8. Practical Queries

### Content Discovery
```cypher
// Find related articles through shared entities
MATCH (seed:Article {title: 'Find Your Next Favorite Workout'})
MATCH (seed)-[:HAS_TOPIC]->(t:Topic)<-[:HAS_TOPIC]-(related:Article)
WHERE seed <> related
RETURN related.title, related.published, collect(DISTINCT t.name) as shared_topics
LIMIT 5
```

### Timeline Analysis
```cypher
// Articles per month in 2025
MATCH (a:Article)
WHERE a.published STARTS WITH '2025'
WITH substring(a.published, 0, 7) as month, count(a) as count
RETURN month, count
ORDER BY month
```

### Entity Popularity Over Time
```cypher
// Topic trends over time
MATCH (a:Article)-[:HAS_TOPIC]->(t:Topic)
WHERE t.name = 'Exercise' AND a.published STARTS WITH '2025'
WITH substring(a.published, 0, 7) as month, count(a) as articles
RETURN month, articles
ORDER BY month
```

---

## Key Cypher Concepts Summary

1. **MATCH**: Find patterns in the graph
2. **WHERE**: Filter results
3. **RETURN**: Specify what to return
4. **WITH**: Chain query parts together and transform data
5. **COLLECT()**: Aggregate values into lists
6. **COUNT()**: Count occurrences
7. **ORDER BY**: Sort results
8. **LIMIT**: Restrict number of results

## Tips for Writing Good Cypher

- Start with simple patterns and build complexity gradually
- Use `LIMIT` while developing to keep results manageable
- Name your variables descriptively (use `article` not just `a`)
- Break complex queries into smaller WITH clauses
- Use EXPLAIN or PROFILE to understand query performance

---

## Next Steps

Try modifying these queries:
- Change the LIMIT values to see more results
- Combine multiple WHERE conditions
- Create your own patterns using different relationship types
- Experiment with aggregation functions

Happy querying! 🚀
