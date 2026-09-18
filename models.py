"""models.py — ★ your one class lives here.

TODO: rename Item to fit your project (Book, Player, Expense, Room, Equipment ...),
give it the fields you keep in data.json, and one method that does something useful.

A page can turn a row from data.json into an object like this:

    import models
    item = models.Item(row["name"], row["price"])
    item.describe()
"""


class Item:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def describe(self):
        # TODO: return a sentence about this item
        return self.name
