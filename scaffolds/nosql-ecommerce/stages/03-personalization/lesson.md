---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Phase 3: Personalization

## The Situation

ShopFlow is growing. The catalog now has thousands of products. The problem the product team brings to engineering isn't performance or correctness this time — it's discovery.

"Customers can't find things," the Head of Product says. "Search helps when you know what you're looking for. But we want to surface products people didn't know they wanted."

The team has been looking at what other retailers do. The most common approach: *customers who bought this also bought that*. If many orders contain both a laptop and a laptop stand, any customer looking at laptops should be shown laptop stands.

The data to build this already exists. Every order ever placed is in the system. Every order is a signal: these products were wanted by the same person at the same time.

---

## Design Considerations: How Do You Model "Also Bought"?

You have order history. You need to find products that frequently appear together in orders. Consider the following before you start coding.

**Start with the data you have:**
- An order contains a list of product IDs
- Any pair of products in the same order is a signal: "these were bought together"
- The more orders that contain a given pair, the stronger the signal

**Think about what you're trying to query:**
- Given a product, find all other products that frequently appear with it in orders
- "Frequently" means: rank by how often the pair appears together

**Now model it as a data structure:**
- What is a node? What is an edge? What does the edge represent?
- What property on the edge captures the strength of the relationship?
- When the same pair appears in another order, what happens to the edge?

**Consider the query:**
- You start at one product. You want its neighbors, ranked by edge weight.
- How many hops do you need for basic recommendations? What about "customers who bought X → also bought Y → also bought Z"?
- Write out what this query looks like. Now write what the equivalent SQL would look like. Compare.

**Consider scale:**
- With 50 products there are at most 1,225 possible pairs. With 5,000 products, there are ~12 million.
- The query is always: "give me the top N neighbors of this node." Does that query get slower as the graph grows?
- What about the equivalent SQL self-join as the order history grows?

---

## What You Need to Build

You will implement recommendation queries, update your migration and seed scripts for Neo4j, and extend `create_order` to maintain the co-purchase graph.

---

## Definition of Done

### 1. `get_recommendations`

**What it enables:** Returning a ranked list of products to recommend alongside a given product.

Recommendations are ranked by co-purchase frequency: the more often two products appear together in orders, the higher the recommendation score.

**Signature:**
```{code-cell} python
def get_recommendations(self, product_id: int, limit: int = 5) -> list[RecommendationResponse]:
```

See `models/responses.py` for `RecommendationResponse`.

**Accepted when:**
- Returns a list of `RecommendationResponse` objects (each has `product_id`, `name`, and `score`)
- Sorted by `score` descending (highest co-purchase frequency first)
- The queried product itself is never in the results
- Returns at most `limit` results
- Returns an empty list if the product has no co-purchase relationships

---

### 2. Migration update

Update `scripts/migrate.py` to add a Neo4j uniqueness constraint on `Product.id`.

---

### 3. Seed update

Update `scripts/seed.py` to load `seed_data/historical_orders.json`, generate all product pair combinations per order, and build `BOUGHT_TOGETHER` edges in Neo4j.

---

### 4. `create_order` update

Update `create_order` to MERGE co-purchase edges in Neo4j for every pair of products in the order, incrementing the weight.

---

## Conventions

Tests depend on these exact Neo4j labels and types:

**Node label:** `Product`
| Property | Type |
|----------|------|
| `id` | int |
| `name` | str |

**Relationship type:** `BOUGHT_TOGETHER` (undirected)
| Property | Type |
|----------|------|
| `weight` | int |

Use `MERGE` without direction arrows for undirected relationships.

---

## Step by Step

### Step 1: Update your migration
Add a Neo4j uniqueness constraint:
```cypher
CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE
```
Run: `uv run python -m scripts.migrate`

### Step 2: Update your seed
Load `seed_data/historical_orders.json`. For each order, generate all unique product pairs using `itertools.combinations`. For each pair, MERGE Product nodes and MERGE a BOUGHT_TOGETHER edge, incrementing the weight.
Run: `uv run python -m scripts.setup`

### Step 3: Implement get_recommendations
    uv run pytest tests/test_phase3.py::test_get_recommendations_shape -v

### Step 4: Update create_order for Neo4j
After the Postgres transaction and MongoDB snapshot, MERGE co-purchase edges for every pair of products in the new order.
    uv run pytest tests/test_phase3.py::test_create_order_updates_graph -v

### Step 5: Run all Phase 3 tests
    uv run pytest tests/test_phase3.py -v

---

## Before You Move On

With the graph in place, explore it:

- Open the graph database browser and visualize the product network. Which products are the most connected?
- Call `GET /products/{id}/recommendations` for a product that appears in many orders. Then call it for a product that appears in only one order. Compare the results.
- Try to write the equivalent query in SQL (hint: you need a self-join on order line items, grouped by product pair, sorted by count). Compare the Cypher and SQL versions.

Consider: what would it take to extend recommendations to two hops — "customers who bought X also bought Y, which is also bought alongside Z"? How does that change the Cypher query? How does it change the SQL?
