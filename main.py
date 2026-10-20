"""ShopDB - command-line interface."""
import shopdb

MENU = """
=== ShopDB ===
 1. Add product               8. Change order status
 2. List / search products    9. All reports
 3. Update price             10. Manage stock
 4. Add customer             11. Customer order history
 5. Find customer (email)    12. Low stock products
 6. Create order             13. Top selling products
 7. View order               14. Monthly revenue
 0. Exit
"""


def ask_float(msg):
    return float(input(msg).replace(",", "."))


def show_products(rows):
    if not rows:
        print("No products found.")
    for p in rows:
        print(f"#{p['id']:<3} {p['name']:<25} {p['price']:>8.2f}  "
              f"stock: {p['stock']:<4} [{p['category']}]")


def create_order_flow(conn):
    customer_id = int(input("Customer ID: "))
    items = []
    print("Add products (empty ID = done).")
    while True:
        pid = input("  Product ID: ").strip()
        if not pid:
            break
        items.append((int(pid), int(input("  Quantity: "))))
    order_id = shopdb.create_order(conn, customer_id, items)
    print(f"Order #{order_id} created.")


def show_order(conn):
    order, items, total = shopdb.get_order(conn, int(input("Order ID: ")))
    print(f"Order #{order['id']} | {order['customer']} | "
          f"{order['status']} | {order['created_at']}")
    for i in items:
        print(f"  {i['name']:<25} {i['quantity']} x {i['unit_price']:.2f} = {i['subtotal']:.2f}")
    print(f"  TOTAL: {total:.2f}")


def manage_stock(conn):
    pid = int(input("Product ID: "))
    delta = int(input("Quantity (+ to add, - to remove): "))
    new_stock = shopdb.adjust_stock(conn, pid, delta)
    print(f"Stock updated: {new_stock} units.")


def customer_history(conn):
    c = shopdb.find_customer_by_email(conn, input("Customer email: "))
    if c is None:
        print("Customer not found.")
        return
    print(f"#{c['id']} {c['name']} <{c['email']}>")
    orders = shopdb.customer_orders(conn, c["id"])
    if not orders:
        print("  No orders.")
    for o in orders:
        print(f"  Order #{o['id']} | {o['status']} | {o['total']:.2f} | {o['created_at']}")


def report_low_stock(conn):
    print("\nLow stock products (< 10):")
    rows = shopdb.low_stock(conn)
    if not rows:
        print("  No low stock products.")
    for r in rows:
        print(f"  {r['name']}: {r['stock']} units ({r['price']:.2f})")


def report_top_products(conn):
    print("\nTop selling products:")
    rows = shopdb.top_products(conn)
    if not rows:
        print("  No sales yet (only paid/shipped orders count).")
    for r in rows:
        print(f"  {r['name']}: {r['units_sold']} units")


def report_monthly_revenue(conn):
    print("\nMonthly revenue:")
    rows = shopdb.monthly_revenue(conn)
    if not rows:
        print("  No revenue yet (only paid/shipped orders count).")
    for r in rows:
        print(f"  {r['month']}: {r['revenue']:.2f}")


def all_reports(conn):
    print(f"\nTotal revenue: {shopdb.total_revenue(conn):.2f}")
    report_monthly_revenue(conn)
    report_top_products(conn)
    report_low_stock(conn)
    print("\nOrders per customer:")
    for r in shopdb.orders_per_customer(conn):
        print(f"  {r['name']}: {r['total_orders']}")


def main():
    conn = shopdb.connect()
    while True:
        print(MENU)
        choice = input("Choose: ").strip()
        try:
            if choice == "1":
                pid = shopdb.add_product(
                    conn, input("Name: "), ask_float("Price: "),
                    int(input("Stock: ")), input("Category: "),
                )
                print(f"Product added (#{pid}).")
            elif choice == "2":
                show_products(shopdb.list_products(
                    conn,
                    search=input("Name contains (optional): ") or None,
                    category=input("Category (optional): ") or None,
                ))
            elif choice == "3":
                shopdb.update_price(conn, int(input("Product ID: ")), ask_float("New price: "))
                print("Price updated.")
            elif choice == "4":
                cid = shopdb.add_customer(conn, input("Name: "), input("Email: "))
                print(f"Customer added (#{cid}).")
            elif choice == "5":
                customer_history(conn)
            elif choice == "6":
                create_order_flow(conn)
            elif choice == "7":
                show_order(conn)
            elif choice == "8":
                shopdb.set_status(conn, int(input("Order ID: ")),
                                  input("New status (paid/shipped/cancelled): ").strip())
                print("Status updated.")
            elif choice == "9":
                all_reports(conn)
            elif choice == "10":
                manage_stock(conn)
            elif choice == "11":
                customer_history(conn)
            elif choice == "12":
                report_low_stock(conn)
            elif choice == "13":
                report_top_products(conn)
            elif choice == "14":
                report_monthly_revenue(conn)
            elif choice == "0":
                break
            else:
                print("Invalid option.")
        except shopdb.ShopError as e:
            print(f"Error: {e}")
        except ValueError:
            print("Error: invalid numeric value.")
    conn.close()


if __name__ == "__main__":
    main()