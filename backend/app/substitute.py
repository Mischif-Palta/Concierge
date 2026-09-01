from decimal import Decimal

from app.db import supabase


def find_substitute(product_id: int, category: str, price: Decimal):
    result = (
        supabase
        .table("products")
        .select(
            "id, name, description, price, stock, image, category"
        )
        .eq("category", category)
        .gt("stock", 0)
        .neq("id", product_id)
        .execute()
    )

    products = result.data or []

    if not products:
        return None

    products.sort(
        key=lambda product: abs(
            Decimal(str(product["price"])) - price
        )
    )

    product = products[0]

    return {
        "id": product["id"],
        "name": product["name"],
        "description": product["description"],
        "price": float(Decimal(str(product["price"]))),
        "stock": int(product["stock"]),
        "image": product["image"],
        "category": product["category"]
    }