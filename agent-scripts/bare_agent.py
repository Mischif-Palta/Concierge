import requests

BASE_URL = "http://127.0.0.1:8000"


def get_catalog():
    response = requests.get(
        f"{BASE_URL}/catalog",
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def create_session():
    response = requests.post(
        f"{BASE_URL}/sessions",
        json={"actor_type": "bare_agent"},
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def create_cart(session_id):
    response = requests.post(
        f"{BASE_URL}/cart",
        json={"session_id": session_id},
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def add_to_cart(cart_id, product_id, quantity):
    response = requests.post(
        f"{BASE_URL}/cart/{cart_id}/items",
        json={
            "product_id": product_id,
            "quantity": quantity
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def select_expensive_product(catalog, minimum_price):
    products = catalog.get("products", [])

    candidates = [
        product
        for product in products
        if product.get("in_stock")
        and product.get("price", 0) > minimum_price
    ]

    if not candidates:
        raise RuntimeError(
            f"No in-stock product found above ₹{minimum_price}"
        )

    return candidates[0]


def main():
    print("=" * 48)
    print("CONCIERGE INDEPENDENT AGENT")
    print("=" * 48)

    print("\nGoal:")
    print("Attempt to add an in-stock product above ₹5,000")

    print("\n[1] GET /catalog")

    catalog = get_catalog()

    print(
        f"    → {catalog.get('count', 0)} products returned"
    )

    product = select_expensive_product(
        catalog,
        minimum_price=5000
    )

    print("\n[2] Product selection")
    print(f"    → {product['name']}")
    print(f"    → ₹{product['price']}")
    print(f"    → Stock: {product['stock']}")
    print(f"    → Product ID: {product['id']}")

    print("\n[3] POST /sessions")

    session = create_session()
    session_id = session["session_id"]

    print(f"    → Session ID: {session_id}")
    print(f"    → Actor: {session['actor_type']}")
    print(f"    → Status: {session['status']}")

    print("\n[4] POST /cart")

    cart = create_cart(session_id)
    cart_id = cart["cart_id"]

    print(f"    → Cart ID: {cart_id}")

    print("\n[5] POST /cart/{cart_id}/items")

    result = add_to_cart(
        cart_id,
        product["id"],
        quantity=1
    )

    print(f"    → Success: {result.get('success')}")
    print(f"    → Policy: {result.get('policy')}")

    policy = result.get("policy", {})

    if policy.get("requires_human_approval"):
        print("\n🔒 HUMAN APPROVAL REQUIRED")
        print(f"    → Status: {policy.get('status')}")
        print(f"    → Reason: {policy.get('reason')}")
    elif result.get("success"):
        print("\n⚠ Product was allowed autonomously")
    else:
        print("\n✗ Product was rejected")

    print("\n✓ Governance boundary test complete")


if __name__ == "__main__":
    main()