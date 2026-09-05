from __future__ import annotations

STORE_ALIASES = {
    "pune": "S001",
    "पुणे": "S001",
    "mumbai": "S002",
    "मुंबई": "S002",
    "nashik": "S003",
    "nasik": "S003",
    "नाशिक": "S003",
    "नासिक": "S003",
}

# Only add aliases that are specific enough to avoid silently mapping an
# ambiguous category word to one product. English catalog matching fills in the
# rest dynamically from products.csv.
PRODUCT_ALIASES = {
    "milk": "P001",
    "amul milk": "P001",
    "दूध": "P001",
    "मिल्क": "P001",
    "paneer": "P003",
    "पनीर": "P003",
    "butter": "P004",
    "बटर": "P004",
    "मक्खन": "P004",
    "cheese slices": "P005",
    "चीज स्लाइस": "P005",
    "brown bread": "P006",
    "ब्राउन ब्रेड": "P006",
    "cola": "P011",
    "कोला": "P011",
    "shampoo": "P021",
    "शैम्पू": "P021",
    "शॅम्पू": "P021",
}

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
