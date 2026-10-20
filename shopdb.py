"""ShopDB logic: products, customers, orders and reports (Python + SQLite)."""
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# current status -> allowed next statuses
TRANSITIONS = {
    "pending": {"paid", "cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": set(),
    "cancelled": set(),
}


class ShopError(Exception):
    """Business logic error (invalid data, insufficient stock, etc.)."""


def connect(path="shopdb.sqlite3"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


# ---------- Products ----------
def add_product(conn, name, price, stock, category="general"):
    if not name.strip():
        raise ShopError("Product name cannot be empty.")
    if price < 0:
        raise ShopError("Price cannot be negative.")
    if stock < 0:
        raise ShopError("Stock cannot be negative.")
    with conn:
        cur = conn.execute(
            "INSERT INTO products (name, price, stock, category) VALUES (?, ?, ?, ?)",
            (name.strip(), price, stock, category.strip() or "general"),
        )
    return cur.lastrowid


def list_products(conn, search=None, category=None, max_price=None):
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if search:
        sql += " AND name LIKE ?"
        params.append(f"%{search}%")
    if category:
        sql += " AND category = ?"
        params.append(category)
    if max_price is not None:
        sql += " AND price <= ?"
        params.append(max_price)
    return conn.execute(sql + " ORDER BY name", params).fetchall()


def update_price(conn, product_id, new_price):
    if new_price < 0:
        raise ShopError("Price cannot be negative.")
    with conn:
        cur = conn.execute("UPDATE products SET price = ? WHERE id = ?", (new_price, product_id))
    if cur.rowcount == 0:
        raise ShopError(f"Product {product_id} does not exist.")


def delete_product(conn, product_id):
    try:
        with conn:
            cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    except sqlite3.IntegrityError:
        raise ShopError("Product appears in orders and cannot be deleted.")
    if cur.rowcount == 0:
        raise ShopError(f"Product {product_id} does not exist.")


def adjust_stock(conn, product_id, delta):
    """Add (delta > 0) or remove (delta < 0) stock. Stock can never go negative."""
    if delta == 0:
        raise ShopError("Quantity cannot be 0.")
    with conn:
        cur = conn.execute(
            "UPDATE products SET stock = stock + ? WHERE id = ? AND stock + ? >= 0",
            (delta, product_id, delta),
        )
    if cur.rowcount == 0:
        exists = conn.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone()
        if exists is None:
            raise ShopError(f"Product {product_id} does not exist.")
        raise ShopError("Stock cannot become negative.")
    return conn.execute("SELECT stock FROM products WHERE id = ?", (product_id,)).fetchone()["stock"]


# ---------- Customers ----------
def add_customer(conn, name, email):
    if not name.strip() or "@" not in email:
        raise ShopError("Invalid name or email.")
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO customers (name, email) VALUES (?, ?)",
                (name.strip(), email.strip().lower()),
            )
    except sqlite3.IntegrityError:
        raise ShopError("A customer with this email already exists.")
    return cur.lastrowid


def find_customer_by_email(conn, email):
    return conn.execute(
        "SELECT * FROM customers WHERE email = ?", (email.strip().lower(),)
    ).fetchone()


def customer_orders(conn, customer_id):
    return conn.execute(
        """
        SELECT o.id, o.status, o.created_at,
               COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total
        FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.customer_id = ?
        GROUP BY o.id ORDER BY o.id DESC
        """,
        (customer_id,),
    ).fetchall()


# ---------- Orders ----------
def create_order(conn, customer_id, items):
    """items = [(product_id, quantity), ...]. All or nothing (transaction)."""
    if not items:
        raise ShopError("An order must contain at least one product.")
    if conn.execute("SELECT 1 FROM customers WHERE id = ?", (customer_id,)).fetchone() is None:
        raise ShopError(f"Customer {customer_id} does not exist.")

    with conn:  # commit at the end, rollback on any exception
        order_id = conn.execute(
            "INSERT INTO orders (customer_id) VALUES (?)", (customer_id,)
        ).lastrowid
        for product_id, qty in items:
            if qty <= 0:
                raise ShopError("Quantity must be positive.")
            product = conn.execute(
                "SELECT price, name FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if product is None:
                raise ShopError(f"Product {product_id} does not exist.")
            cur = conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (qty, product_id, qty),
            )
            if cur.rowcount == 0:
                raise ShopError(f"Insufficient stock for '{product['name']}'.")
            conn.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                "VALUES (?, ?, ?, ?)",
                (order_id, product_id, qty, product["price"]),
            )
    return order_id


def get_order(conn, order_id):
    order = conn.execute(
        """
        SELECT o.id, o.status, o.created_at, c.name AS customer
        FROM orders o JOIN customers c ON c.id = o.customer_id WHERE o.id = ?
        """,
        (order_id,),
    ).fetchone()
    if order is None:
        raise ShopError(f"Order {order_id} does not exist.")
    items = conn.execute(
        """
        SELECT p.name, oi.quantity, oi.unit_price, oi.quantity * oi.unit_price AS subtotal
        FROM order_items oi JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = ?
        """,
        (order_id,),
    ).fetchall()
    return order, items, sum(i["subtotal"] for i in items)


def set_status(conn, order_id, new_status):
    row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise ShopError(f"Order {order_id} does not exist.")
    if new_status not in TRANSITIONS.get(row["status"], set()):
        raise ShopError(f"Invalid transition: {row['status']} -> {new_status}.")
    with conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        if new_status == "cancelled":  # give the stock back
            conn.execute(
                """
                UPDATE products SET stock = stock + (
                    SELECT SUM(quantity) FROM order_items
                    WHERE order_id = ? AND product_id = products.id)
                WHERE id IN (SELECT product_id FROM order_items WHERE order_id = ?)
                """,
                (order_id, order_id),
            )


# ---------- Reports ----------
def low_stock(conn, threshold=10):
    return conn.execute(
        "SELECT name, price, stock FROM products WHERE stock < ? ORDER BY stock", (threshold,)
    ).fetchall()


def total_revenue(conn):
    row = conn.execute(
        """
        SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        WHERE o.status IN ('paid', 'shipped')
        """
    ).fetchone()
    return row["revenue"]


def monthly_revenue(conn):
    return conn.execute(
        """
        SELECT strftime('%Y-%m', o.created_at) AS month,
               SUM(oi.quantity * oi.unit_price) AS revenue
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        WHERE o.status IN ('paid', 'shipped')
        GROUP BY month ORDER BY month
        """
    ).fetchall()


def top_products(conn, limit=5):
    return conn.execute(
        """
        SELECT p.name, SUM(oi.quantity) AS units_sold
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        JOIN orders o ON o.id = oi.order_id
        WHERE o.status IN ('paid', 'shipped')
        GROUP BY p.id, p.name ORDER BY units_sold DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()


def orders_per_customer(conn):
    return conn.execute(
        """
        SELECT c.name, COUNT(o.id) AS total_orders
        FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
        GROUP BY c.id, c.name ORDER BY total_orders DESC, c.name
        """
    ).fetchall()