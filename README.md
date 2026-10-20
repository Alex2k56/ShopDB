# ShopDB - E-commerce Order Management System

A command-line order management system built with **Python** and **SQLite**.
It handles products, customers, orders, stock and SQL reports, the kind of
backend logic that sits behind an online store.

## Features

- **Products:** add, search and filter, update prices, delete (with validation)
- **Customers:** register, find by email, view order history
- **Orders:** multi-product orders with automatic totals and stock checks
- **Stock management:** add or remove stock, with protection against negative stock
- **Order status workflow:** `pending -> paid -> shipped`, or `cancelled`
  (cancelling an order returns its items to stock)
- **SQL reports:** monthly revenue, top selling products, low stock products,
  orders per customer
- **Automated tests** for valid orders, insufficient stock, rollbacks,
  status rules and stock adjustments

## Technical highlights

- Relational schema with primary keys, foreign keys and `CHECK` / `UNIQUE` constraints
- Parameterized queries everywhere (no string concatenation, so no SQL injection)
- Transactions: an order is saved completely or not at all
- `order_items.unit_price` stores the price at the time of the order,
  so later price changes do not affect past orders
- SQL practice: `JOIN`, `LEFT JOIN`, `GROUP BY`, `SUM`, `COUNT`, `ORDER BY`, `LIMIT`

## Project structure

```
ShopDB/
├── schema.sql        # database tables
├── shopdb.py         # application logic and SQL reports
├── main.py           # interactive command-line menu
├── test_shopdb.py    # automated tests
└── README.md
```

## Database schema

| Table         | Columns                                              |
|---------------|------------------------------------------------------|
| `customers`   | id, name, email (unique), created_at                 |
| `products`    | id, name, price, stock, category                     |
| `orders`      | id, customer_id, status, created_at                  |
| `order_items` | id, order_id, product_id, quantity, unit_price       |

A customer can have many orders, and an order can contain many products.
`order_items` links orders to products.

## Getting started

**Requirements:** Python 3.10 or newer. No external packages are needed,
because SQLite is included in Python.

```bash
git clone https://github.com/Alex2k56/ShopDB.git
cd ShopDB
python main.py
```

The database file `shopdb.sqlite3` is created automatically on the first run.

## Usage

```
=== ShopDB ===
 1. Add product               8. Change order status
 2. List / search products    9. All reports
 3. Update price             10. Manage stock
 4. Add customer             11. Customer order history
 5. Find customer (email)    12. Low stock products
 6. Create order             13. Top selling products
 7. View order               14. Monthly revenue
 0. Exit
```

Typical flow:

1. Add a few products (option 1) and a customer (option 4)
2. Create an order (option 6) and view it (option 7)
3. Change its status to `paid` (option 8)
4. Check the reports (options 9 to 14)

Revenue and top product reports only count orders with the status
`paid` or `shipped`.

## Order status rules

| From        | Allowed next status      |
|-------------|--------------------------|
| `pending`   | `paid`, `cancelled`      |
| `paid`      | `shipped`, `cancelled`   |
| `shipped`   | none                     |
| `cancelled` | none                     |

## Running the tests

```bash
python -m unittest -v
```

## Example SQL report

Top selling products (from `shopdb.py`):

```sql
SELECT p.name, SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN products p ON p.id = oi.product_id
JOIN orders o ON o.id = oi.order_id
WHERE o.status IN ('paid', 'shipped')
GROUP BY p.id, p.name
ORDER BY units_sold DESC
LIMIT 5;
```

## Roadmap

- [ ] REST API with FastAPI
- [ ] SQLAlchemy models
- [ ] Migration from SQLite to PostgreSQL
- [ ] Filtering orders by date range and status
- [ ] Docker setup

## Author

Alexandru Grecu - [GitHub](https://github.com/Alex2k56)
