import random
from datetime import date, timedelta
from decimal import Decimal


def populate(con, seed=42):
    rng = random.Random(seed)
    con.execute("CREATE TABLE customers(customer_id INTEGER,region VARCHAR)")
    con.execute("CREATE TABLE products(product_id INTEGER,category VARCHAR)")
    con.execute(
        "CREATE TABLE orders(order_id INTEGER,customer_id INTEGER,ordered_at DATE,status VARCHAR)"
    )
    con.execute(
        "CREATE TABLE order_items(order_id INTEGER,item_id INTEGER,product_id INTEGER,quantity INTEGER,unit_price DECIMAL(10,2))"
    )
    regions = ["华东", "华南", "华北", None]
    con.executemany(
        "INSERT INTO customers VALUES(?,?)", [(i, regions[i % 4]) for i in range(1, 81)]
    )
    con.executemany(
        "INSERT INTO products VALUES(?,?)",
        [(i, ["图书", "数码", "家居", "运动"][i % 4]) for i in range(1, 21)],
    )
    orders = []
    items = []
    n = 240 + (seed % 13)
    for i in range(1, n + 1):
        status = rng.choices(["delivered", "cancelled", "processing"], [0.78, 0.14, 0.08])[0]
        orders.append(
            (
                i,
                None if i % 19 == 0 else rng.randint(1, 80),
                date(2025, 1, 1) + timedelta(days=rng.randrange(90)),
                status,
            )
        )
        for j in range(1, rng.randint(1, 4) + 1):
            items.append(
                (
                    i,
                    j,
                    rng.randint(1, 20),
                    rng.randint(1, 3),
                    Decimal(rng.randint(100, 15000)) / 100,
                )
            )
    con.executemany("INSERT INTO orders VALUES(?,?,?,?)", orders)
    con.executemany("INSERT INTO order_items VALUES(?,?,?,?,?)", items)
