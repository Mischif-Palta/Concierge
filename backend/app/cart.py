from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import supabase
from app.policy import check_policy, MAX_AUTONOMOUS_CART_VALUE
from app.audit import log_event


router = APIRouter(
    prefix="/cart",
    tags=["Cart"]
)


class CartCreate(BaseModel):
    session_id: UUID


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int


class CartUpdate(BaseModel):
    product_id: int
    quantity: int


class CartItemApproval(BaseModel):
    product_id: int
    quantity: int


def calculate_subtotal(items):
    subtotal = Decimal("0")

    for item in items:
        subtotal += (
            Decimal(str(item["price"]))
            * Decimal(str(item["quantity"]))
        )

    return subtotal.quantize(
        Decimal("0.01")
    )


def format_cart(cart):
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


@router.post("")
def create_cart(
    payload: CartCreate
):
    session_result = (
        supabase
        .table("sessions")
        .select("id")
        .eq(
            "id",
            str(payload.session_id)
        )
        .execute()
    )

    if not session_result.data:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    result = (
        supabase
        .table("carts")
        .insert({
            "session_id": str(
                payload.session_id
            ),
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

    log_event(
        session_id=payload.session_id,
        action="cart_created",
        details={
            "cart_id": str(cart["id"]),
            "status": cart["status"],
            "subtotal": cart["subtotal"],
            "total": cart["total"],
        }
    )

    return format_cart(cart)


@router.get("/{cart_id}")
def get_cart(
    cart_id: UUID
):
    result = (
        supabase
        .table("carts")
        .select("*")
        .eq(
            "id",
            str(cart_id)
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    cart = result.data[0]

    return format_cart(cart)


@router.get("/{cart_id}/policy")
def get_cart_policy(
    cart_id: UUID
):
    result = (
        supabase
        .table("carts")
        .select(
            "id, session_id, total, status"
        )
        .eq(
            "id",
            str(cart_id)
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    cart = result.data[0]

    current_cart_value = Decimal(
        str(cart.get("total") or 0)
    )

    autonomous_limit = (
        MAX_AUTONOMOUS_CART_VALUE
    )

    remaining = (
        autonomous_limit
        - current_cart_value
    )

    if remaining < 0:
        remaining = Decimal("0")

    if autonomous_limit > 0:
        percentage_used = (
            current_cart_value
            / autonomous_limit
        ) * Decimal("100")
    else:
        percentage_used = Decimal("0")

    percentage_used = (
        percentage_used.quantize(
            Decimal("0.01")
        )
    )

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


@router.post("/{cart_id}/items")
def add_cart_item(
    cart_id: UUID,
    payload: CartItemAdd
):
    if payload.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0"
        )

    cart_result = (
        supabase
        .table("carts")
        .select("*")
        .eq(
            "id",
            str(cart_id)
        )
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

    session_id = UUID(
        cart["session_id"]
    )

    product_result = (
        supabase
        .table("products")
        .select(
            "id, name, price, stock, image, category"
        )
        .eq(
            "id",
            payload.product_id
        )
        .execute()
    )

    if not product_result.data:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product = product_result.data[0]

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

    existing_item = None

    for item in items:
        if item["product_id"] == payload.product_id:
            existing_item = item
            break

    current_quantity = 0

    if existing_item:
        current_quantity = (
            existing_item["quantity"]
        )

    new_quantity = (
        current_quantity
        + payload.quantity
    )

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
                "reason": (
                    "Requested quantity exceeds "
                    "available stock"
                ),
                "status": "blocked"
            }
        )

        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {product['stock']} units available"
            )
        )

    current_cart_total = Decimal(
        str(cart.get("total") or 0)
    )

    product_price = Decimal(
        str(product["price"])
    )

    added_value = (
        product_price
        * payload.quantity
    )

    policy_result = check_policy(
        action="add_to_cart",
        cart_total=current_cart_total,
        product_price=added_value,
        product_category=product["category"],
        stock=product["stock"],
        is_upsell=False
    )

    log_event(
        session_id=session_id,
        action="policy_decision",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity": payload.quantity,
            "product_price": float(
                product["price"]
            ),
            "added_value": float(
                added_value
            ),
            "current_cart_total": float(
                current_cart_total
            ),
            "policy_status": (
                policy_result["status"]
            ),
            "allowed": (
                policy_result["allowed"]
            ),
            "requires_human_approval": (
                policy_result[
                    "requires_human_approval"
                ]
            ),
            "reason": (
                policy_result["reason"]
            )
        }
    )

    if policy_result["status"] != "allowed":
        return {
            "success": False,
            "cart_id": str(cart_id),
            "policy": policy_result,
            "cart": format_cart(cart)
        }

    if existing_item:
        existing_item["quantity"] = (
            new_quantity
        )

        existing_item["price"] = float(
            product["price"]
        )

        existing_item["stock"] = (
            product["stock"]
        )

    else:
        items.append({
            "product_id": product["id"],
            "name": product["name"],
            "price": float(
                product["price"]
            ),
            "quantity": payload.quantity,
            "stock": product["stock"],
            "image": product["image"]
        })

    subtotal = calculate_subtotal(
        items
    )

    total = subtotal

    update_result = (
        supabase
        .table("carts")
        .update({
            "items": items,
            "subtotal": float(subtotal),
            "total": float(total)
        })
        .eq(
            "id",
            str(cart_id)
        )
        .execute()
    )

    if not update_result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to update cart"
        )

    updated_cart = (
        update_result.data[0]
    )

    log_event(
        session_id=session_id,
        action="cart_item_added",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity_added": payload.quantity,
            "cart_quantity": new_quantity,
            "unit_price": float(
                product["price"]
            ),
            "subtotal": updated_cart["subtotal"],
            "total": updated_cart["total"],
            "status": "success"
        }
    )

    return {
        "success": True,
        "cart": format_cart(
            updated_cart
        ),
        "policy": policy_result
    }


@router.post("/{cart_id}/items/approve")
def approve_cart_item(
    cart_id: UUID,
    payload: CartItemApproval
):
    if payload.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0"
        )

    cart_result = (
        supabase
        .table("carts")
        .select("*")
        .eq(
            "id",
            str(cart_id)
        )
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

    session_id = UUID(
        cart["session_id"]
    )

    product_result = (
        supabase
        .table("products")
        .select(
            "id, name, price, stock, image, category"
        )
        .eq(
            "id",
            payload.product_id
        )
        .execute()
    )

    if not product_result.data:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product = product_result.data[0]

    if product["stock"] <= 0:
        log_event(
            session_id=session_id,
            action="human_approval_rejected",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": payload.quantity,
                "reason": "Product is out of stock",
                "stock": product["stock"],
                "status": "rejected"
            }
        )

        raise HTTPException(
            status_code=400,
            detail="Product is out of stock"
        )

    items = cart.get("items") or []

    existing_item = None

    for item in items:
        if item["product_id"] == payload.product_id:
            existing_item = item
            break

    current_quantity = (
        existing_item["quantity"]
        if existing_item
        else 0
    )

    new_quantity = (
        current_quantity
        + payload.quantity
    )

    if new_quantity > product["stock"]:
        log_event(
            session_id=session_id,
            action="human_approval_rejected",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "requested_quantity": new_quantity,
                "available_stock": product["stock"],
                "reason": (
                    "Requested quantity exceeds "
                    "available stock"
                ),
                "status": "rejected"
            }
        )

        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {product['stock']} units available"
            )
        )

    current_cart_total = Decimal(
        str(cart.get("total") or 0)
    )

    product_price = Decimal(
        str(product["price"])
    )

    added_value = (
        product_price
        * payload.quantity
    )

    policy_result = check_policy(
        action="add_to_cart",
        cart_total=current_cart_total,
        product_price=added_value,
        product_category=product["category"],
        stock=product["stock"],
        is_upsell=False
    )

    log_event(
        session_id=session_id,
        action="human_approval_granted",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity": payload.quantity,
            "added_value": float(
                added_value
            ),
            "current_cart_total": float(
                current_cart_total
            ),
            "previous_policy_status": (
                policy_result["status"]
            ),
            "previous_policy_allowed": (
                policy_result["allowed"]
            ),
            "approved_by": "human",
            "status": "approved"
        }
    )

    if existing_item:
        existing_item["quantity"] = (
            new_quantity
        )

        existing_item["price"] = float(
            product["price"]
        )

        existing_item["stock"] = (
            product["stock"]
        )

    else:
        items.append({
            "product_id": product["id"],
            "name": product["name"],
            "price": float(
                product["price"]
            ),
            "quantity": payload.quantity,
            "stock": product["stock"],
            "image": product["image"]
        })

    subtotal = calculate_subtotal(
        items
    )

    total = subtotal

    update_result = (
        supabase
        .table("carts")
        .update({
            "items": items,
            "subtotal": float(subtotal),
            "total": float(total)
        })
        .eq(
            "id",
            str(cart_id)
        )
        .execute()
    )

    if not update_result.data:
        log_event(
            session_id=session_id,
            action="human_approval_action_failed",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "reason": "Failed to update cart",
                "status": "failed"
            }
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update cart"
        )

    updated_cart = (
        update_result.data[0]
    )

    log_event(
        session_id=session_id,
        action="cart_item_added",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity_added": payload.quantity,
            "cart_quantity": new_quantity,
            "unit_price": float(
                product["price"]
            ),
            "subtotal": updated_cart["subtotal"],
            "total": updated_cart["total"],
            "status": "success",
            "approved_by": "human"
        }
    )

    return {
        "success": True,
        "approved": True,
        "cart": format_cart(
            updated_cart
        ),
        "policy": {
            "allowed": True,
            "requires_human_approval": False,
            "status": "human_approved",
            "reason": (
                "Purchase explicitly approved by human."
            )
        }
    }


@router.patch("/{cart_id}")
def update_cart(
    cart_id: UUID,
    payload: CartUpdate
):
    cart_result = (
        supabase
        .table("carts")
        .select("*")
        .eq(
            "id",
            str(cart_id)
        )
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

    session_id = UUID(
        cart["session_id"]
    )

    items = cart.get("items") or []

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

    if payload.quantity == 0:
        removed_item = items[
            item_index
        ]

        items.pop(item_index)

        subtotal = calculate_subtotal(
            items
        )

        total = subtotal

        update_result = (
            supabase
            .table("carts")
            .update({
                "items": items,
                "subtotal": float(
                    subtotal
                ),
                "total": float(
                    total
                )
            })
            .eq(
                "id",
                str(cart_id)
            )
            .execute()
        )

        if not update_result.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to update cart"
            )

        updated_cart = (
            update_result.data[0]
        )

        log_event(
            session_id=session_id,
            action="cart_item_removed",
            details={
                "cart_id": str(cart_id),
                "product_id": (
                    removed_item["product_id"]
                ),
                "product_name": (
                    removed_item.get("name")
                ),
                "quantity_removed": (
                    removed_item["quantity"]
                ),
                "subtotal": (
                    updated_cart["subtotal"]
                ),
                "total": (
                    updated_cart["total"]
                ),
                "status": "success"
            }
        )

        return format_cart(
            updated_cart
        )

    if payload.quantity < 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity cannot be negative"
        )

    product_result = (
        supabase
        .table("products")
        .select(
            "id, name, price, stock"
        )
        .eq(
            "id",
            payload.product_id
        )
        .execute()
    )

    if not product_result.data:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product = product_result.data[0]

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
                "requested_quantity": (
                    payload.quantity
                ),
                "available_stock": (
                    product["stock"]
                ),
                "reason": (
                    "Requested quantity exceeds "
                    "available stock"
                ),
                "status": "blocked"
            }
        )

        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {product['stock']} units available"
            )
        )

    old_quantity = items[
        item_index
    ]["quantity"]

    items[item_index]["quantity"] = (
        payload.quantity
    )

    items[item_index]["price"] = float(
        product["price"]
    )

    items[item_index]["stock"] = (
        product["stock"]
    )

    subtotal = calculate_subtotal(
        items
    )

    total = subtotal

    update_result = (
        supabase
        .table("carts")
        .update({
            "items": items,
            "subtotal": float(
                subtotal
            ),
            "total": float(
                total
            )
        })
        .eq(
            "id",
            str(cart_id)
        )
        .execute()
    )

    if not update_result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to update cart"
        )

    updated_cart = (
        update_result.data[0]
    )

    log_event(
        session_id=session_id,
        action="cart_item_updated",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "old_quantity": old_quantity,
            "new_quantity": payload.quantity,
            "unit_price": float(
                product["price"]
            ),
            "subtotal": (
                updated_cart["subtotal"]
            ),
            "total": (
                updated_cart["total"]
            ),
            "status": "success"
        }
    )

    return format_cart(
        updated_cart
    )