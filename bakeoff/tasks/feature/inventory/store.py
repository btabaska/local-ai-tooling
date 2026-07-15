"""In-memory inventory store."""


class Store:
    def __init__(self):
        self.items = {}

    def add_item(self, name, price, qty):
        if price < 0 or qty < 0:
            raise ValueError("price and qty must be non-negative")
        if name in self.items:
            self.items[name]["qty"] += qty
        else:
            self.items[name] = {"price": price, "qty": qty}

    def total_value(self):
        return sum(v["price"] * v["qty"] for v in self.items.values())
