"""
LangChain tools for the supportdb schema.

Tools:
- map_product_name_to_sku(name: str) -> str
    Resolve a product name fragment (ILIKE %name%) to a single SKU; errors on none/ambiguous.
- place_new_order(customer_email: str, items: list[{name: str, quantity: int}]) -> dict
    Create an order with random status, insert items, compute totals.
- get_order_status(order_id: int) -> str
    Fetch the current status of an order.
- update_order_items_if_processing(order_id: int, items: list[{name: str, quantity: int}]) -> dict
    Replace items and totals only when status == 'processing'.
- get_latest_order_id_by_product(email: str, item_name: str) -> int
    Resolve product name via fuzzy match, then fetch the most recent order_id for that customer containing the item.

Item format for order tools: [{"name": "Desk", "quantity": 2}]
"""

from contextlib import contextmanager
import os
import random
from decimal import Decimal
import re
from typing import Iterable, Mapping, Sequence

import psycopg
from langchain.tools import tool
from thefuzz import process

ORDER_STATUSES = ["processing", "shipped", "delivered"]

DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5431"),
    "dbname": os.getenv("DB_NAME", "supportdb"),
    "user": os.getenv("DB_USER", "support_ro"),
    "password": os.getenv("DB_PASSWORD", "support_ro"),
}

SESSION_MAX_AGE_SECONDS = int(os.getenv('SESSION_MAX_AGE_SECONDS', '300'))

def render_graph_image(app):
    png_data = app.get_graph().draw_mermaid_png()
    with open("graph_visualization.png", "wb") as f:
        f.write(png_data)

@contextmanager
def get_db_conn():
  conn = psycopg.connect(**DB_SETTINGS)
  try:
    yield conn
  finally:
    conn.close() # default 5 minutes


def _lookup_product_by_name(name: str) -> dict:
    """
    Purpose: internal helper to resolve a name fragment to one product using fuzzy matching.
    Input: name (str), tolerant of plurals/extra words; strips digits before matching.
    Output: {"sku": str, "product_id": int, "price": Decimal}
    Errors: raises if no confident match.
    """
    cleaned = re.sub(r"\d+", "", name).strip()
    if not cleaned:
        raise ValueError("Product name is empty after cleaning")

    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, sku, product_id, unit_price FROM products")
        rows = cur.fetchall()

    catalog = [r[0] for r in rows]
    match = process.extractOne(cleaned, catalog, score_cutoff=70)
    if not match:
        raise ValueError(f"No products matched '{name}'")

    matched_name = match[0]
    for pname, sku, product_id, price in rows:
        if pname == matched_name:
            return {"sku": sku, "product_id": product_id, "price": Decimal(price)}

    raise ValueError(f"No products matched '{name}'")


@tool
def place_new_order(customer_email: str, items: str) -> Mapping[str, object]:
    """
    Purpose: Create a new order for the given customer and insert line items.
    Inputs:
      - customer_email (str) must exist in customers.email
      - items (str): JSON/list literal string representing [{"name": str, "quantity": int}]
        names will be used as wildcard searches in the form of %name% to obtain correct product names.
    Behavior: assigns a random status, inserts order + items, computes total.
    Returns: {"order_id": int, "status": str, "total": float, "currency": "USD"}
    """
    import json

    try:
        parsed_items = json.loads(items)
    except Exception as exc:
        raise ValueError("items must be a JSON string representing a list of {name, quantity}") from exc

    if not isinstance(parsed_items, list):
        raise ValueError("items must decode to a list")

    resolved = []
    for item in parsed_items:
        qty = int(item.get("quantity", 1))
        if "name" not in item:
            raise ValueError("Each item must include a 'name'")
        product = _lookup_product_by_name(item["name"])
        product["qty"] = qty
        resolved.append(product)
    status = random.choice(ORDER_STATUSES)

    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM customers WHERE email = %s", (customer_email,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Customer not found for email {customer_email}")
        customer_id = row[0]

        cur.execute(
            """
            INSERT INTO orders (customer_id, status, total, currency)
            VALUES (%s, %s, 0, 'USD')
            RETURNING order_id
            """,
            (customer_id, status),
        )
        order_id = cur.fetchone()[0]

        total = Decimal("0")
        for item in resolved:
            cur.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
                """,
                (order_id, item["product_id"], item["qty"], item["price"]),
            )
            total += item["price"] * item["qty"]

        cur.execute("UPDATE orders SET total = %s WHERE order_id = %s", (total, order_id))
        conn.commit()

        return {
            "order_id": order_id,
            "status": status,
            "total": float(total),
            "currency": "USD",
        }


@tool
def get_order_status(order_id: int) -> str:
    """
    Purpose: Return the current status for an order.
    Input: order_id (int)
    Output: status string (e.g., processing, shipped, delivered)
    Errors: raises if order not found.
    """
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Order {order_id} not found")
        return row[0]


@tool
def update_order_items_if_processing(order_id: int, items: str) -> Mapping[str, object]:
    """
    Purpose: Replace all items on an order only if status == 'processing'.
    Inputs:
      - order_id (int)
      - items (str): JSON/list literal string representing [{"name": str, "quantity": int}].
        names will be used as wildcard searches in the form of %name% to obtain correct product names.
    Behavior: deletes existing order_items, inserts new ones, recomputes total.
    Returns: {"order_id": int, "status": str, "total": float, "currency": "USD"}
    Errors: raises if order not found, not processing, or name resolution is ambiguous/missing.
    """
    import json

    try:
        parsed_items = json.loads(items)
    except Exception as exc:
        raise ValueError("items must be a JSON string representing a list of {name, quantity}") from exc

    if not isinstance(parsed_items, list):
        raise ValueError("items must decode to a list")

    resolved = []
    for item in parsed_items:
        qty = int(item.get("quantity", 1))
        if "name" not in item:
            raise ValueError("Each item must include a 'name'")
        product = _lookup_product_by_name(item["name"])
        product["qty"] = qty
        resolved.append(product)

    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Order {order_id} not found")
        status = row[0]
        if status != "processing":
            return {"error": f"Order {order_id} is {status}; changes allowed only in processing."}

        # Clear existing items and insert new ones
        cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))

        total = Decimal("0")
        for item in resolved:
            cur.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
                """,
                (order_id, item["product_id"], item["qty"], item["price"]),
            )
            total += item["price"] * item["qty"]

        cur.execute("UPDATE orders SET total = %s WHERE order_id = %s", (total, order_id))
        conn.commit()

        return {"order_id": order_id, "status": status, "total": float(total), "currency": "USD"}


@tool
def get_latest_order_id_by_product(email: str, item_name: str) -> int:
    """
    Purpose: For a given customer email, find the most recent order containing the named product.
    Inputs: email (str), item_name (str) resolved via fuzzy match.
    Returns: order_id (int) of the latest matching order.
    Errors: raises if customer or product not found, or no matching order.
    """
    product = _lookup_product_by_name(item_name)
    with get_db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM customers WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Customer not found for email {email}")
        customer_id = row[0]

        cur.execute(
            """
            SELECT o.order_id
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.customer_id = %s AND oi.product_id = %s
            ORDER BY o.placed_at DESC NULLS LAST, o.order_id DESC
            LIMIT 1
            """,
            (customer_id, product["product_id"]),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No orders for {email} containing '{item_name}'")
        return row[0]


