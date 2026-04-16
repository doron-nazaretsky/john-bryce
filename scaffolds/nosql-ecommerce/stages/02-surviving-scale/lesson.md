---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Phase 2: Surviving Scale

## The Situation

ShopFlow launched two months ago. Things are going well — almost too well. The team is staring at three problems that didn't exist before traffic arrived:

---

**Problem 1: Product pages are slow.**

The product detail page is the most visited page on the site. Every page load hits the same database to fetch the same product data. Most products don't change for days or weeks. The team ran some numbers: under normal load, `GET /products/{id}` accounts for 60% of all database queries, and the vast majority of those reads are for the same few hundred products.

"We're paying for the same work over and over again," the CTO says.

---

**Problem 2: Inventory checks are slow.**

Every product page and every add-to-cart hits the transactional database to read stock. Under load, these reads compete with order writes for database connections. The team wants a fast-path counter that can answer "is this product in stock?" without touching Postgres.

---

**Problem 3: There's no "recently viewed" feature.**

Marketing wants to surface recently viewed products on the homepage and in email campaigns. The requirement is simple: keep a per-customer ordered list of the last 10 products they viewed. It needs to update instantly and be readable from any service.

"It's basically a queue with a maximum size," the lead engineer says. "Where does something like that live?"

---

## Design Considerations: Where Does This Data Belong?

Consider the following before you start coding:

**On the product cache:**
- What does it mean for a cache to be "correct"? When does stale data become a problem?
- If a product's price changes in the main store, what needs to happen to the cache?
- What should happen on a cache miss? On a cache hit?
- How does your caching solution affect the behavior of `get_product`? Does the API caller need to know the cache exists?

**On inventory:**
- The stock quantity lives in the transactional database. What's the value of also tracking it somewhere else?
- What kind of operation on a number guarantees that two concurrent callers each get a distinct result?
- What happens if the counter in the fast store and the count in the transactional database drift apart? How do you reconcile them?

**On recently viewed:**
- This is an ordered, bounded list updated on every product view. What access patterns does that suggest?
- Does it matter if this list is occasionally lost (e.g., on a restart)? Why or why not?
- Could you store this in the transactional database? What would that cost you?

---

## What You Need to Build

Update `create_order` to DECR the Redis inventory counter for each ordered product after the Postgres transaction succeeds. As an optimization, you can also check the Redis counter before starting the Postgres transaction — if Redis says insufficient stock, fail fast without hitting Postgres. The Postgres transaction remains the authoritative check.

Update `scripts/seed.py` to read all product stock quantities from Postgres and write them to Redis as inventory counters. No migration changes needed — Redis has no schema.

Four methods. Two are additions to existing behavior; two are new capabilities.

---

## Definition of Done

### 1. `get_product` (updated)

**What it enables:** Serving product detail pages without hitting the primary store on every request.

The behavior from Phase 1 is unchanged from the caller's perspective — same inputs, same output shape, same `None` for missing products. Internally, the method now checks a fast cache first. On a miss, it fetches from the primary store and populates the cache for future requests.

When product data is updated, the cache entry must be explicitly removed so the next read fetches fresh data.

**Signature:** (unchanged from Phase 1)
```{code-cell} python
def get_product(self, product_id: int) -> ProductResponse | None:
```

**Accepted when:**
- The first call for a product fetches from the primary store and populates the cache
- A subsequent call for the same product is served from the cache (no primary store read)
- After `invalidate_product_cache(product_id)` is called, the next read goes to the primary store again
- Cache entries expire after 300 seconds without explicit invalidation
- Returns `None` if the product does not exist in either the cache or the primary store

---

### 2. `invalidate_product_cache`

**What it enables:** Keeping the cache consistent when product data changes.

Called whenever a product is updated in the primary store. The next read for that product will go directly to the primary store and repopulate the cache.

**Signature:**
```{code-cell} python
def invalidate_product_cache(self, product_id: int) -> None:
```

**Accepted when:**
- After calling this, the next `get_product` call for the same product reads from the primary store
- No error is raised if no cached entry exists for the product

---

### 3. `record_product_view`

**What it enables:** Maintaining a per-customer history of recently viewed products.

Called every time a customer views a product. The list is bounded: only the 10 most recent views are kept. The most recently viewed product is always first.

**Signature:**
```{code-cell} python
def record_product_view(self, customer_id: int, product_id: int) -> None:
```

**Accepted when:**
- After viewing a product, it appears at the front of the customer's list
- After more than 10 views, only the 10 most recent are retained
- Viewing the same product multiple times moves it to the front each time (duplicates are allowed)

---

### 4. `get_recently_viewed`

**What it enables:** Reading a customer's recent product history.

**Signature:**
```{code-cell} python
def get_recently_viewed(self, customer_id: int) -> list[int]:
```

**Accepted when:**
- Returns up to 10 product IDs, most recently viewed first
- Returns an empty list for a customer with no views recorded
- Returns IDs as integers

---

## Conventions

Tests depend on these exact Redis key patterns:

| Key Pattern | Type | Value | TTL |
|-------------|------|-------|-----|
| `product:{product_id}` | String | JSON-serialized product dict | 300 seconds |
| `inventory:{product_id}` | String | Integer stock count as string | None |
| `recently_viewed:{customer_id}` | List | Product ID strings (head = most recent) | None |

Redis client must be created with `decode_responses=True`.

---

## Step by Step

### Step 1: Update your seed
Open `scripts/seed.py`. After your Phase 1 seeding, add logic to read all products from Postgres and set `inventory:{product_id}` keys in Redis.
Run: `uv run python -m scripts.setup`

### Step 2: Add cache-aside to get_product
Update `get_product` in `db_access.py`:
1. Check Redis key `product:{product_id}` — if present, deserialize and return
2. On miss: fetch from MongoDB, serialize to JSON, SET in Redis with 300-second TTL, return
Run: `uv run pytest tests/test_phase2.py::test_cache_populated_on_first_read -v`

### Step 3: Implement invalidate_product_cache
    uv run pytest tests/test_phase2.py::test_invalidate_clears_cache -v

### Step 4: Implement record_product_view and get_recently_viewed
    uv run pytest tests/test_phase2.py::test_record_and_get_recently_viewed -v

### Step 5: Update create_order for Redis
Add DECR logic for inventory counters after the Postgres transaction succeeds.
    uv run pytest tests/test_phase2.py::test_create_order_decrements_counter -v

### Step 6: Run all Phase 2 tests
    uv run pytest tests/test_phase2.py -v

---

## Before You Move On

With Phase 2 in place, verify the following:

- Call `GET /products/{id}` twice for the same product. Check the logs to see if the second call hit the primary store.
- Call `invalidate_product_cache` for a product, then `GET /products/{id}`. Confirm it fetches from the primary store again.
- View several products as the same customer, then call `GET /customers/{id}/recently-viewed`. View more than 10 products and check what happens to the list.

Consider: if the fast store goes down, does `get_product` still work? Should it? What tradeoffs does that imply?

When you have thought through these tradeoffs, move to Phase 3.
