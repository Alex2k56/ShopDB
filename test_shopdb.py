import unittest

import shopdb


class ShopDBTests(unittest.TestCase):
    def setUp(self):
        self.conn = shopdb.connect(":memory:")
        self.cid = shopdb.add_customer(self.conn, "Ana", "ana@example.com")
        self.pid = shopdb.add_product(self.conn, "Mouse", 50, 5, "IT")

    def stock(self):
        return self.conn.execute(
            "SELECT stock FROM products WHERE id=?", (self.pid,)
        ).fetchone()[0]

    def test_valid_order_reduces_stock_and_computes_total(self):
        oid = shopdb.create_order(self.conn, self.cid, [(self.pid, 2)])
        _, _, total = shopdb.get_order(self.conn, oid)
        self.assertEqual(total, 100)
        self.assertEqual(self.stock(), 3)

    def test_insufficient_stock_rolls_back(self):
        with self.assertRaises(shopdb.ShopError):
            shopdb.create_order(self.conn, self.cid, [(self.pid, 99)])
        self.assertEqual(self.stock(), 5)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)

    def test_unknown_product_and_customer(self):
        with self.assertRaises(shopdb.ShopError):
            shopdb.create_order(self.conn, self.cid, [(999, 1)])
        with self.assertRaises(shopdb.ShopError):
            shopdb.create_order(self.conn, 999, [(self.pid, 1)])

    def test_price_snapshot_kept_after_price_change(self):
        oid = shopdb.create_order(self.conn, self.cid, [(self.pid, 1)])
        shopdb.update_price(self.conn, self.pid, 80)
        self.assertEqual(shopdb.get_order(self.conn, oid)[2], 50)

    def test_cancel_restores_stock_and_blocks_invalid_transition(self):
        oid = shopdb.create_order(self.conn, self.cid, [(self.pid, 2)])
        shopdb.set_status(self.conn, oid, "cancelled")
        self.assertEqual(self.stock(), 5)
        with self.assertRaises(shopdb.ShopError):
            shopdb.set_status(self.conn, oid, "paid")

    def test_revenue_counts_only_paid_and_shipped(self):
        o1 = shopdb.create_order(self.conn, self.cid, [(self.pid, 1)])
        shopdb.create_order(self.conn, self.cid, [(self.pid, 1)])  # stays pending
        shopdb.set_status(self.conn, o1, "paid")
        self.assertEqual(shopdb.total_revenue(self.conn), 50)

    def test_duplicate_email_and_negative_price(self):
        with self.assertRaises(shopdb.ShopError):
            shopdb.add_customer(self.conn, "Other Ana", "ANA@example.com")
        with self.assertRaises(shopdb.ShopError):
            shopdb.add_product(self.conn, "X", -1, 1)

    def test_adjust_stock_add_subtract_and_no_negative(self):
        self.assertEqual(shopdb.adjust_stock(self.conn, self.pid, 10), 15)
        self.assertEqual(shopdb.adjust_stock(self.conn, self.pid, -15), 0)
        with self.assertRaises(shopdb.ShopError):
            shopdb.adjust_stock(self.conn, self.pid, -1)
        with self.assertRaises(shopdb.ShopError):
            shopdb.adjust_stock(self.conn, 999, 1)
        self.assertEqual(self.stock(), 0)


if __name__ == "__main__":
    unittest.main()