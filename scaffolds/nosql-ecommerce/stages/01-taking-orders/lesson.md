---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Phase 1: Taking Orders

## The Situation

ShopFlow is three weeks from launch. The product team has finalized the catalog: ~50 products across five categories — electronics, clothing, books, food, and home goods. Each category has its own set of attributes: electronics have CPU specs and RAM, clothing has sizes and colors, books have ISBNs and authors. Food and home goods have their own distinct fields too.

The launch requirements are straightforward:

1. Customers can browse and search the product catalog
2. Customers can place orders
3. The business can see which product categories are generating revenue
4. Customer service can look up any order, past or present

**Consider the following before you start coding.**

---

## Design Considerations: Where Does the Data Live?

You need to store two fundamentally different things:

**Orders** — A customer placed an order. Products were reserved. Money will change hands. This must be correct. If a product has 1 unit in stock and two customers order it simultaneously, exactly one should succeed. If something fails halfway through placing an order, it must be as if the order never happened.

**Products** — An electronics product has CPU, RAM, and storage specs. A clothing product has sizes and colors. A book has an ISBN and an author. These fields don't exist for all categories. How do you store them? In the same place as orders? Separately? What happens when you want to show a product page and need all the fields at once?

Consider:
- What consistency guarantees does each kind of data need?
- How do queries differ between the two? Looking up a product vs. aggregating order revenue?
- What happens to your storage design when you add a sixth category with completely different attributes?
- Which of your choices still hold when you have 5 million products and 10 million orders?

---

## What You Need to Build

You will implement the following capabilities. Each maps to a specific method in `db_access.py` — open that file and read the signature and docstring for each before implementing.

---

## Definition of Done

### 1. `create_order`

**What it enables:** A customer places an order.

The operation must be atomic: if any requested product does not have enough stock, the entire order is rejected — no stock is reduced, no order is recorded. If the order succeeds, inventory is reduced for every item in the order, exactly once, even if two orders arrive at the same moment.

When an order completes, a complete snapshot of the order is saved — customer details, product names, prices — exactly as they were at the moment of purchase. This snapshot must be retrievable later even if product prices or names change.

**Signature:**
```{code-cell} python
def create_order(self, customer_id: int, items: list[OrderItemRequest]) -> OrderResponse:
```

See `models/requests.py` for `OrderItemRequest` and `models/responses.py` for `OrderResponse`.

**Accepted when:**
- An order with valid stock reduces `stock_quantity` for every product involved
- Two concurrent orders for the last unit of a product result in exactly one success
- An order for a product with insufficient stock raises `ValueError` and no data is modified
- A successful order returns an `OrderResponse` (see `models/responses.py` for the full shape)
- A snapshot of the order is persisted and retrievable via `get_order` after creation

---

### 2. `get_product`

**What it enables:** A customer views a product detail page.

The response must include all category-specific fields — a single call must return everything needed to render the page, regardless of category.

**Signature:**
```{code-cell} python
def get_product(self, product_id: int) -> ProductResponse | None:
```

See `models/responses.py` for `ProductResponse`.

**Accepted when:**
- Returns a `ProductResponse` with the product's fields and `category_fields`
- `category_fields` contains the correct category-specific attributes (e.g., `cpu`/`ram_gb` for electronics, `sizes`/`colors` for clothing)
- Returns `None` if the product does not exist

---

### 3. `search_products`

**What it enables:** A customer searches or filters the catalog.

Filtering can be by category, by a text match on product name, or both. Results from all categories are returned in a single response.

**Signature:**
```{code-cell} python
def search_products(self, category: str | None = None, q: str | None = None) -> list[ProductResponse]:
```

**Accepted when:**
- Returns all products when called with no arguments
- Filters by exact `category` when provided
- Filters by case-insensitive substring match on product name when `q` is provided
- Both filters can be applied together (AND semantics)
- Each result is a `ProductResponse` (same shape as `get_product`)

---

### 4. `save_order_snapshot`

**What it enables:** Preserving a complete, denormalized record of an order at the time it was placed.

This method is called internally by `create_order` — it is not exposed directly as an API endpoint. The snapshot must embed customer details and product information as they existed at the moment of the order, so the historical record is immutable even if prices or names change later.

**Signature:**
```{code-cell} python
def save_order_snapshot(
    self,
    order_id: int,
    customer: OrderCustomerEmbed,
    items: list[OrderItemResponse],
    total_amount: float,
    status: str,
    created_at: str,
) -> str:
```

See `models/responses.py` for `OrderCustomerEmbed` and `OrderItemResponse`.

**Accepted when:**
- Persists the snapshot so that `get_order(order_id)` returns the correct data
- Returns a string identifier for the stored document

---

### 5. `get_order`

**What it enables:** Customer service looks up a specific order.

**Signature:**
```{code-cell} python
def get_order(self, order_id: int) -> OrderSnapshotResponse | None:
```

See `models/responses.py` for `OrderSnapshotResponse`.

**Accepted when:**
- Returns an `OrderSnapshotResponse` with the full snapshot (order_id, customer embed, items list, total_amount, status, created_at)
- Returns `None` if no order with that ID exists

---

### 6. `get_order_history`

**What it enables:** A customer views all their past orders.

**Signature:**
```{code-cell} python
def get_order_history(self, customer_id: int) -> list[OrderSnapshotResponse]:
```

**Accepted when:**
- Returns all order snapshots for the given customer
- Ordered most recent first
- Returns an empty list if the customer has no orders

---

### 7. `revenue_by_category`

**What it enables:** The business sees which product categories are generating revenue, to inform inventory and marketing decisions.

**Signature:**
```{code-cell} python
def revenue_by_category(self) -> list[CategoryRevenueResponse]:
```

See `models/responses.py` for `CategoryRevenueResponse`.

**Accepted when:**
- Returns a list of `CategoryRevenueResponse` objects (each has `category` and `total_revenue`)
- Sorted by `total_revenue` descending
- Covers all categories that have completed orders — no hardcoded category list

---

## Conventions

Tests depend on these exact names:

**MongoDB collections:**
- `product_catalog` — stores product documents
- `order_snapshots` — stores order snapshot documents

**PostgreSQL:** You design your own schema. No table names or column names are prescribed.
The method signatures and acceptance criteria define what your code must do — you decide how to structure the tables that support it.

---

## Step by Step

### Step 1: Design your database schemas
Read through all the method signatures and acceptance criteria above.
From those, determine what data needs to live in PostgreSQL and what in MongoDB.
Open `postgres_models.py` and define your ORM classes.

### Step 2: Write your migration
Open `scripts/migrate.py`. Implement the `migrate()` function.
For Postgres: use `Base.metadata.create_all(engine)` to create tables from your ORM models.
For MongoDB: create any indexes your queries will need.
Run: `uv run python -m scripts.migrate`
Verify: connect to Postgres and confirm your tables exist.

### Step 3: Write your seed
Open `scripts/seed.py`. Implement the `seed()` function.
Load `seed_data/products.json` and `seed_data/customers.json`.
Insert the data into your databases using the schemas you designed.
Run: `uv run python -m scripts.seed`
Verify: start the API and try `GET /products` — you should see your seeded products.

### Step 4: Implement and test one method at a time
Start with `get_product` (reads a single product from MongoDB):
    uv run pytest tests/test_phase1.py::test_get_product_found -v

Then `search_products`:
    uv run pytest tests/test_phase1.py::test_search_products_by_category -v

Then `save_order_snapshot`, `get_order`, `get_order_history`:
    uv run pytest tests/test_phase1.py::test_save_order_snapshot -v

Then `create_order` (ACID transaction — reads from Postgres, writes snapshot to MongoDB):
    uv run pytest tests/test_phase1.py::test_create_order_success -v

Finally `revenue_by_category`:
    uv run pytest tests/test_phase1.py::test_revenue_by_category -v

### Step 5: Run all Phase 1 tests
    uv run pytest tests/test_phase1.py -v

### Step 6: Try it in the browser
    uv run python -m scripts.setup
    uv run uvicorn ecommerce_pipeline.api.app:app --reload
    Open http://localhost:8000/docs

---

## Before You Move On

Once all seven methods pass their tests, verify the following:

- Place an order for a product with 1 unit in stock. Then try to place the same order again. What happens?
- Search products by category and by name. Think about what the equivalent query would require in raw SQL.
- Pull the revenue report. Add another order and pull it again.

When you have internalized why each storage choice exists, move to Phase 2.
