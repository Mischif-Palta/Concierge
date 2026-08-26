from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import supabase
from app.policy import check_policy, MAX_AUTONOMOUS_CART_VALUE
from app.audit import log_event


router = APIRouter(prefix="/cart", tags=["Cart"])


# ============================================================
# REQUEST MODELS
# ============================================================

class CartCreate(BaseModel):
    session_id: UUID


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int


class CartUpdate(BaseModel):
    product_id: int
    quantity: int


# ============================================================
# HELPERS
# ============================================================

def calculate_subtotal(items):
    """
    Calculate cart subtotal using Decimal.
    """

    subtotal = Decimal("0")

    for item in items:
        subtotal += (
            Decimal(str(item["price"]))
            * Decimal(str(item["quantity"]))
        )

    return subtotal.quantize(Decimal("0.01"))


def format_cart(cart):
    """
    Convert a database cart into the API response format.
    """

    items = cart.get("items") or []

    return {
        "cart_id": cart["id"],
        "session_id": cart["session_id"],
        "items": items,
        "item_count": sum(
            item["quantity"]
            for item in items
        ),
        "subtotal": cart["subtotal"],
        "total": cart["total"],
        "status": cart["status"],
    }


# ============================================================
# CREATE CART
# ============================================================

@router.post("")
def create_cart(payload: CartCreate):

    # Verify session exists
    session_result = (
        supabase
        .table("sessions")
        .select("id")
        .eq("id", str(payload.session_id))
        .execute()
    )

    if not session_result.data:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    # Create cart
    result = (
        supabase
        .table("carts")
        .insert({
            "session_id": str(payload.session_id),
            "items": [],
            "subtotal": 0,
            "total": 0,
            "status": "active"
        })
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to create cart"
        )

    cart = result.data[0]

    return format_cart(cart)


# ============================================================
# GET CART
# ============================================================

@router.get("/{cart_id}")
def get_cart(cart_id: UUID):

    result = (
        supabase
        .table("carts")
        .select("*")
        .eq("id", str(cart_id))
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    cart = result.data[0]

    return format_cart(cart)

# ============================================================
# GET CART POLICY / SPEND CAP
# ============================================================

@router.get("/{cart_id}/policy")
def get_cart_policy(cart_id: UUID):

    # --------------------------------------------------------
    # Get cart
    # --------------------------------------------------------

    result = (
        supabase
        .table("carts")
        .select("id, session_id, total, status")
        .eq("id", str(cart_id))
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    cart = result.data[0]

    # --------------------------------------------------------
    # Calculate spend-cap information
    # --------------------------------------------------------

    current_cart_value = Decimal(
        str(cart.get("total") or 0)
    )

    autonomous_limit = MAX_AUTONOMOUS_CART_VALUE

    remaining = autonomous_limit - current_cart_value

    # Don't expose a negative remaining budget
    if remaining < 0:
        remaining = Decimal("0")

    # Calculate percentage used
    if autonomous_limit > 0:
        percentage_used = (
            current_cart_value
            / autonomous_limit
        ) * Decimal("100")
    else:
        percentage_used = Decimal("0")

    percentage_used = percentage_used.quantize(
        Decimal("0.01")
    )

    # Cap displayed percentage at 100%
    if percentage_used > Decimal("100"):
        percentage_used = Decimal("100")

    return {
        "cart_id": cart["id"],
        "session_id": cart["session_id"],
        "current_cart_value": float(
            current_cart_value.quantize(
                Decimal("0.01")
            )
        ),
        "autonomous_limit": float(
            autonomous_limit
        ),
        "remaining_autonomous_budget": float(
            remaining.quantize(
                Decimal("0.01")
            )
        ),
        "percentage_used": float(
            percentage_used
        ),
        "status": cart["status"]
    }

# ============================================================
# ADD ITEM TO CART
# ============================================================

@router.post("/{cart_id}/items")
def add_cart_item(
    cart_id: UUID,
    payload: CartItemAdd
):

    # --------------------------------------------------------
    # Validate quantity
    # --------------------------------------------------------

    if payload.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0"
        )

    # --------------------------------------------------------
    # Get cart
    # --------------------------------------------------------

    cart_result = (
        supabase
        .table("carts")
        .select("*")
        .eq("id", str(cart_id))
        .execute()
    )

    if not cart_result.data:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    cart = cart_result.data[0]

    if cart["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail="Cart is not active"
        )

    session_id = UUID(cart["session_id"])

    # --------------------------------------------------------
    # Get authoritative product data
    # --------------------------------------------------------

    product_result = (
        supabase
        .table("products")
        .select(
            "id, name, price, stock, image, category"
        )
        .eq("id", payload.product_id)
        .execute()
    )

    if not product_result.data:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product = product_result.data[0]

    # --------------------------------------------------------
    # Stock validation
    # --------------------------------------------------------

    if product["stock"] <= 0:

        log_event(
            session_id=session_id,
            action="cart_action_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": payload.quantity,
                "reason": "Product is out of stock",
                "stock": product["stock"],
                "status": "blocked"
            }
        )

        raise HTTPException(
            status_code=400,
            detail="Product is out of stock"
        )

    items = cart.get("items") or []

    # --------------------------------------------------------
    # Determine existing quantity
    # --------------------------------------------------------

    existing_item = None

    for item in items:
        if item["product_id"] == payload.product_id:
            existing_item = item
            break

    current_quantity = 0

    if existing_item:
        current_quantity = existing_item["quantity"]

    new_quantity = current_quantity + payload.quantity

    # --------------------------------------------------------
    # Stock validation against total quantity
    # --------------------------------------------------------

    if new_quantity > product["stock"]:

        log_event(
            session_id=session_id,
            action="cart_action_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "requested_quantity": new_quantity,
                "available_stock": product["stock"],
                "reason": "Requested quantity exceeds available stock",
                "status": "blocked"
            }
        )

        raise HTTPException(
            status_code=400,
            detail=f"Only {product['stock']} units available"
        )

    # --------------------------------------------------------
    # Calculate proposed new cart value
    # --------------------------------------------------------

    current_cart_total = Decimal(
        str(cart.get("total") or 0)
    )

    product_price = Decimal(
        str(product["price"])
    )

    added_value = product_price * payload.quantity

    # --------------------------------------------------------
    # POLICY ENGINE
    # --------------------------------------------------------

    policy_result = check_policy(
        action="add_to_cart",
        cart_total=current_cart_total,
        product_price=added_value,
        product_category=product["category"],
        stock=product["stock"],
        is_upsell=False
    )

    # --------------------------------------------------------
    # AUDIT POLICY DECISION
    # --------------------------------------------------------

    log_event(
        session_id=session_id,
        action="policy_decision",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity": payload.quantity,
            "product_price": float(product["price"]),
            "added_value": float(added_value),
            "current_cart_total": float(current_cart_total),
            "policy_status": policy_result["status"],
            "allowed": policy_result["allowed"],
            "requires_human_approval": (
                policy_result["requires_human_approval"]
            ),
            "reason": policy_result["reason"]
        }
    )

    # --------------------------------------------------------
    # POLICY GATE
    # --------------------------------------------------------

    if policy_result["status"] != "allowed":

        return {
            "success": False,
            "cart_id": str(cart_id),
            "policy": policy_result,
            "cart": {
                "items": items,
                "item_count": sum(
                    item["quantity"]
                    for item in items
                ),
                "subtotal": cart["subtotal"],
                "total": cart["total"],
                "status": cart["status"]
            }
        }

    # --------------------------------------------------------
    # Add / update item
    # --------------------------------------------------------

    if existing_item:

        existing_item["quantity"] = new_quantity

        # Always use authoritative price
        existing_item["price"] = float(
            product["price"]
        )

        # Refresh stock
        existing_item["stock"] = product["stock"]

    else:

        items.append({
            "product_id": product["id"],
            "name": product["name"],
            "price": float(product["price"]),
            "quantity": payload.quantity,
            "stock": product["stock"],
            "image": product["image"]
        })

    # --------------------------------------------------------
    # Recalculate totals
    # --------------------------------------------------------

    subtotal = calculate_subtotal(items)
    total = subtotal

    # --------------------------------------------------------
    # Save cart
    # --------------------------------------------------------

    update_result = (
        supabase
        .table("carts")
        .update({
            "items": items,
            "subtotal": float(subtotal),
            "total": float(total)
        })
        .eq("id", str(cart_id))
        .execute()
    )

    if not update_result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to update cart"
        )

    updated_cart = update_result.data[0]

    # --------------------------------------------------------
    # AUDIT SUCCESSFUL CART ACTION
    # --------------------------------------------------------

    log_event(
        session_id=session_id,
        action="cart_item_added",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity_added": payload.quantity,
            "cart_quantity": new_quantity,
            "unit_price": float(product["price"]),
            "subtotal": updated_cart["subtotal"],
            "total": updated_cart["total"],
            "status": "success"
        }
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "success": True,
        "cart": format_cart(updated_cart),
        "policy": policy_result
    }


# ============================================================
# UPDATE / REMOVE CART ITEM
# ============================================================

@router.patch("/{cart_id}")
def update_cart(
    cart_id: UUID,
    payload: CartUpdate
):

    # --------------------------------------------------------
    # Get cart
    # --------------------------------------------------------

    cart_result = (
        supabase
        .table("carts")
        .select("*")
        .eq("id", str(cart_id))
        .execute()
    )

    if not cart_result.data:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    cart = cart_result.data[0]

    if cart["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail="Cart is not active"
        )

    session_id = UUID(cart["session_id"])

    items = cart.get("items") or []

    # --------------------------------------------------------
    # Find item
    # --------------------------------------------------------

    item_index = None

    for index, item in enumerate(items):

        if item["product_id"] == payload.product_id:
            item_index = index
            break

    if item_index is None:
        raise HTTPException(
            status_code=404,
            detail="Product is not in the cart"
        )

    # --------------------------------------------------------
    # Remove item
    # quantity = 0
    # --------------------------------------------------------

    if payload.quantity == 0:

        removed_item = items[item_index]

        items.pop(item_index)

        # Recalculate
        subtotal = calculate_subtotal(items)
        total = subtotal

        update_result = (
            supabase
            .table("carts")
            .update({
                "items": items,
                "subtotal": float(subtotal),
                "total": float(total)
            })
            .eq("id", str(cart_id))
            .execute()
        )

        if not update_result.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to update cart"
            )

        updated_cart = update_result.data[0]

        log_event(
            session_id=session_id,
            action="cart_item_removed",
            details={
                "cart_id": str(cart_id),
                "product_id": removed_item["product_id"],
                "product_name": removed_item.get("name"),
                "quantity_removed": removed_item["quantity"],
                "subtotal": updated_cart["subtotal"],
                "total": updated_cart["total"],
                "status": "success"
            }
        )

        return format_cart(updated_cart)

    # --------------------------------------------------------
    # Reject negative quantity
    # --------------------------------------------------------

    if payload.quantity < 0:

        raise HTTPException(
            status_code=400,
            detail="Quantity cannot be negative"
        )

    # --------------------------------------------------------
    # Get authoritative product data
    # --------------------------------------------------------

    product_result = (
        supabase
        .table("products")
        .select(
            "id, name, price, stock"
        )
        .eq("id", payload.product_id)
        .execute()
    )

    if not product_result.data:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product = product_result.data[0]

    # --------------------------------------------------------
    # Stock validation
    # --------------------------------------------------------

    if product["stock"] <= 0:

        log_event(
            session_id=session_id,
            action="cart_action_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": payload.quantity,
                "reason": "Product is out of stock",
                "stock": product["stock"],
                "status": "blocked"
            }
        )

        raise HTTPException(
            status_code=400,
            detail="Product is out of stock"
        )

    if payload.quantity > product["stock"]:

        log_event(
            session_id=session_id,
            action="cart_action_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "requested_quantity": payload.quantity,
                "available_stock": product["stock"],
                "reason": "Requested quantity exceeds available stock",
                "status": "blocked"
            }
        )

        raise HTTPException(
            status_code=400,
            detail=f"Only {product['stock']} units available"
        )

    # --------------------------------------------------------
    # Update quantity
    # --------------------------------------------------------

    old_quantity = items[item_index]["quantity"]

    items[item_index]["quantity"] = payload.quantity

    # Refresh authoritative price
    items[item_index]["price"] = float(
        product["price"]
    )

    # Refresh stock
    items[item_index]["stock"] = product["stock"]

    # --------------------------------------------------------
    # Recalculate totals
    # --------------------------------------------------------

    subtotal = calculate_subtotal(items)
    total = subtotal

    # --------------------------------------------------------
    # Save updated cart
    # --------------------------------------------------------

    update_result = (
        supabase
        .table("carts")
        .update({
            "items": items,
            "subtotal": float(subtotal),
            "total": float(total)
        })
        .eq("id", str(cart_id))
        .execute()
    )

    if not update_result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to update cart"
        )

    updated_cart = update_result.data[0]

    # --------------------------------------------------------
    # AUDIT QUANTITY UPDATE
    # --------------------------------------------------------

    log_event(
        session_id=session_id,
        action="cart_item_updated",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "old_quantity": old_quantity,
            "new_quantity": payload.quantity,
            "unit_price": float(product["price"]),
            "subtotal": updated_cart["subtotal"],
            "total": updated_cart["total"],
            "status": "success"
        }
    )

    return format_cart(updated_cart)