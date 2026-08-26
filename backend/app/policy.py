from decimal import Decimal


# ============================================================
# POLICY CONFIGURATION
# ============================================================

MAX_AUTONOMOUS_CART_VALUE = Decimal("5000")
MAX_AUTONOMOUS_UPSELL_VALUE = Decimal("1000")


# Categories Concierge is allowed to operate on.
# These match categories currently present in our catalog.
ALLOWED_CATEGORIES = {
    "sports-accessories",
    "mens-shoes",
    "mobile-accessories",
    "mens-watches",
    "sunglasses",
}


# ============================================================
# POLICY ENGINE
# ============================================================

def check_policy(
    action: str,
    cart_total: Decimal = Decimal("0"),
    product_price: Decimal = Decimal("0"),
    product_category: str | None = None,
    stock: int | None = None,
    is_upsell: bool = False,
):
    """
    Evaluate whether a commerce action is allowed.

    Returns one of:

    allowed
    approval_required
    blocked
    """

    cart_total = Decimal(str(cart_total))
    product_price = Decimal(str(product_price))

    # --------------------------------------------------------
    # STOCK GATE
    # --------------------------------------------------------

    if stock is not None and stock <= 0:
        return {
            "allowed": False,
            "requires_human_approval": False,
            "status": "blocked",
            "reason": "Product is out of stock.",
            "policy": {
                "stock": stock
            }
        }

    # --------------------------------------------------------
    # CATEGORY GATE
    # --------------------------------------------------------

    if product_category is not None:

        if product_category not in ALLOWED_CATEGORIES:
            return {
                "allowed": False,
                "requires_human_approval": False,
                "status": "blocked",
                "reason": "Product category is outside Concierge's allowed catalog scope.",
                "policy": {
                    "category": product_category,
                    "allowed_categories": sorted(
                        ALLOWED_CATEGORIES
                    )
                }
            }

    # --------------------------------------------------------
    # UPSELL LIMIT
    # --------------------------------------------------------

    if is_upsell:

        if product_price > MAX_AUTONOMOUS_UPSELL_VALUE:
            return {
                "allowed": False,
                "requires_human_approval": True,
                "status": "approval_required",
                "reason": "Upsell exceeds the autonomous upsell limit.",
                "policy": {
                    "max_autonomous_upsell_value": float(
                        MAX_AUTONOMOUS_UPSELL_VALUE
                    ),
                    "product_price": float(product_price)
                }
            }

    # --------------------------------------------------------
    # AUTONOMOUS CART LIMIT
    # --------------------------------------------------------

    new_cart_total = cart_total + product_price

    if new_cart_total > MAX_AUTONOMOUS_CART_VALUE:

        return {
            "allowed": False,
            "requires_human_approval": True,
            "status": "approval_required",
            "reason": "Cart exceeds the autonomous spending limit.",
            "policy": {
                "max_autonomous_cart_value": float(
                    MAX_AUTONOMOUS_CART_VALUE
                ),
                "current_cart_value": float(cart_total),
                "product_price": float(product_price),
                "new_cart_value": float(new_cart_total)
            }
        }

    # --------------------------------------------------------
    # ALLOWED
    # --------------------------------------------------------

    return {
        "allowed": True,
        "requires_human_approval": False,
        "status": "allowed",
        "reason": "Action is within Concierge's autonomous policy limits.",
        "policy": {
            "max_autonomous_cart_value": float(
                MAX_AUTONOMOUS_CART_VALUE
            ),
            "current_cart_value": float(cart_total),
            "product_price": float(product_price),
            "new_cart_value": float(new_cart_total)
        }
    }