from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.substitute import find_substitute
from app.db import supabase
from app.policy import check_policy, MAX_AUTONOMOUS_CART_VALUE
from app.audit import log_event
from razorpay_client import client as razorpay_client


router = APIRouter(prefix="/checkout", tags=["Checkout"])


class CheckoutRequest(BaseModel):
    cart_id: UUID


class RecoveryRequest(BaseModel):
    cart_id: UUID
    original_product_id: int
    substitute_product_id: int


class PaymentConfirmation(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


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

    return result.data[0]


def get_fresh_product(product_id: int):
    result = (
        supabase
        .table("products")
        .select(
            "id, name, description, price, stock, image, category"
        )
        .eq("id", product_id)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def replace_cart_item(
    cart,
    original_product_id: int,
    substitute_product: dict,
    quantity: int
):
    items = cart.get("items") or []

    updated_items = []

    for item in items:
        if item.get("product_id") == original_product_id:
            continue

        updated_items.append(item)

    updated_items.append({
        "product_id": substitute_product["id"],
        "name": substitute_product["name"],
        "price": float(
            Decimal(str(substitute_product["price"]))
        ),
        "quantity": quantity,
        "stock": int(substitute_product["stock"]),
        "image": substitute_product["image"]
    })

    subtotal = Decimal("0.00")

    for item in updated_items:
        subtotal += (
            Decimal(str(item["price"]))
            * Decimal(str(item["quantity"]))
        )

    subtotal = subtotal.quantize(
        Decimal("0.01")
    )

    return updated_items, subtotal


@router.post("")
def checkout(payload: CheckoutRequest):

    cart = get_cart(payload.cart_id)

    session_id = UUID(cart["session_id"])

    if cart["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail="Cart is not active"
        )

    items = cart.get("items") or []

    if not items:
        log_event(
            session_id=session_id,
            action="checkout_blocked",
            details={
                "cart_id": str(payload.cart_id),
                "reason": "Cart is empty",
                "status": "blocked"
            }
        )

        return {
            "status": "blocked",
            "allowed": False,
            "requires_human_approval": False,
            "reason": "Cart is empty.",
            "cart_id": str(payload.cart_id)
        }

    fresh_items = []
    fresh_total = Decimal("0.00")

    for item in items:

        product_id = item.get("product_id")
        quantity = item.get("quantity")

        if not isinstance(product_id, int):
            raise HTTPException(
                status_code=400,
                detail="Invalid product ID in cart"
            )

        if not isinstance(quantity, int) or quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid quantity in cart"
            )

        product = get_fresh_product(product_id)

        if product is None:

            log_event(
                session_id=session_id,
                action="checkout_blocked",
                details={
                    "cart_id": str(payload.cart_id),
                    "product_id": product_id,
                    "reason": "Product no longer exists",
                    "status": "blocked"
                }
            )

            return {
                "status": "blocked",
                "allowed": False,
                "requires_human_approval": False,
                "reason": f"Product {product_id} is no longer available.",
                "cart_id": str(payload.cart_id)
            }

        product_stock = int(product["stock"])
        product_price = Decimal(str(product["price"]))

        if product_stock <= 0:

            substitute = find_substitute(
                product_id=product["id"],
                category=product["category"],
                price=product_price
            )

            log_event(
                session_id=session_id,
                action="checkout_stock_failure",
                details={
                    "cart_id": str(payload.cart_id),
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "requested_quantity": quantity,
                    "available_stock": product_stock,
                    "reason": "Product is out of stock",
                    "status": "blocked",
                    "substitute_available": substitute is not None
                }
            )

            response = {
                "status": "blocked",
                "allowed": False,
                "requires_human_approval": False,
                "failure_type": "out_of_stock",
                "reason": (
                    f"{product['name']} went out of stock before checkout."
                ),
                "cart_id": str(payload.cart_id),
                "failed_product": {
                    "id": product["id"],
                    "name": product["name"],
                    "price": float(product_price),
                    "image": product["image"],
                    "category": product["category"],
                    "requested_quantity": quantity,
                    "available_stock": product_stock
                },
                "recovery_available": substitute is not None
            }

            if substitute:
                response["substitute"] = substitute

                log_event(
                    session_id=session_id,
                    action="substitute_proposed",
                    details={
                        "cart_id": str(payload.cart_id),
                        "original_product_id": product["id"],
                        "original_product_name": product["name"],
                        "substitute_product_id": substitute["id"],
                        "substitute_name": substitute["name"],
                        "substitute_price": substitute["price"],
                        "reason": (
                            "Closest-priced in-stock product "
                            "in the same category"
                        )
                    }
                )

            return response

        if quantity > product_stock:

            log_event(
                session_id=session_id,
                action="checkout_blocked",
                details={
                    "cart_id": str(payload.cart_id),
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "requested_quantity": quantity,
                    "available_stock": product_stock,
                    "reason": "Requested quantity exceeds available stock",
                    "status": "blocked"
                }
            )

            return {
                "status": "blocked",
                "allowed": False,
                "requires_human_approval": False,
                "reason": (
                    f"Only {product_stock} units of "
                    f"{product['name']} are available."
                ),
                "cart_id": str(payload.cart_id),
                "product_id": product["id"]
            }

        category_policy = check_policy(
            action="checkout",
            cart_total=Decimal("0"),
            product_price=Decimal("0"),
            product_category=product["category"],
            stock=product_stock,
            is_upsell=False
        )

        if category_policy["status"] != "allowed":

            log_event(
                session_id=session_id,
                action="checkout_blocked",
                details={
                    "cart_id": str(payload.cart_id),
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "category": product["category"],
                    "reason": category_policy["reason"],
                    "policy": category_policy,
                    "status": "blocked"
                }
            )

            return {
                "status": "blocked",
                "allowed": False,
                "requires_human_approval": False,
                "reason": category_policy["reason"],
                "cart_id": str(payload.cart_id),
                "product_id": product["id"],
                "policy": category_policy
            }

        item_total = product_price * quantity
        fresh_total += item_total

        fresh_items.append({
            "product_id": product["id"],
            "name": product["name"],
            "price": float(product_price),
            "quantity": quantity,
            "stock": product_stock,
            "image": product["image"],
            "category": product["category"],
            "item_total": float(
                item_total.quantize(Decimal("0.01"))
            )
        })

    fresh_total = fresh_total.quantize(Decimal("0.01"))

    approval_result = (
        supabase
        .table("audit_log")
        .select("id, action, details, created_at")
        .eq(
            "session_id",
            str(session_id)
        )
        .eq(
            "action",
            "human_approval_granted"
        )
        .order(
            "created_at",
            desc=True
        )
        .execute()
    )

    human_approval_granted = False

    for event in approval_result.data or []:
        details = event.get("details") or {}

        if (
            str(details.get("cart_id", ""))
            == str(payload.cart_id)
        ):
            human_approval_granted = True
            break

    policy_result = check_policy(
        action="checkout",
        cart_total=Decimal("0"),
        product_price=fresh_total,
        product_category=None,
        stock=None,
        is_upsell=False
    )

    if human_approval_granted:
        policy_result = {
            **policy_result,
            "allowed": True,
            "requires_human_approval": False,
            "status": "human_approved",
            "reason": (
                "Checkout authorized by prior human approval."
            )
        }

    log_event(
        session_id=session_id,
        action="checkout_policy_decision",
        details={
            "cart_id": str(payload.cart_id),
            "cart_total_snapshot": float(
                Decimal(str(cart.get("total") or 0))
            ),
            "fresh_total": float(fresh_total),
            "autonomous_limit": float(
                MAX_AUTONOMOUS_CART_VALUE
            ),
            "policy_status": policy_result["status"],
            "allowed": policy_result["allowed"],
            "requires_human_approval": (
                policy_result["requires_human_approval"]
            ),
            "human_approval_granted": human_approval_granted,
            "reason": policy_result["reason"]
        }
    )

    if (
        policy_result["status"] == "approval_required"
        and not human_approval_granted
    ):

        return {
            "status": "pending_approval",
            "allowed": False,
            "requires_human_approval": True,
            "reason": policy_result["reason"],
            "cart_id": str(payload.cart_id),
            "cart_total": float(fresh_total),
            "autonomous_limit": float(
                MAX_AUTONOMOUS_CART_VALUE
            ),
            "items": fresh_items,
            "policy": policy_result
        }

    if (
        policy_result["status"] != "allowed"
        and policy_result["status"] != "human_approved"
    ):

        log_event(
            session_id=session_id,
            action="checkout_blocked",
            details={
                "cart_id": str(payload.cart_id),
                "fresh_total": float(fresh_total),
                "reason": policy_result["reason"],
                "policy": policy_result,
                "status": "blocked"
            }
        )

        return {
            "status": "blocked",
            "allowed": False,
            "requires_human_approval": False,
            "reason": policy_result["reason"],
            "cart_id": str(payload.cart_id),
            "cart_total": float(fresh_total),
            "items": fresh_items,
            "policy": policy_result
        }

    amount_paise = int(
        fresh_total * Decimal("100")
    )

    order_result = (
        supabase
        .table("orders")
        .insert({
            "cart_id": str(payload.cart_id),
            "session_id": str(session_id),
            "amount": amount_paise,
            "currency": "INR",
            "status": "created"
        })
        .execute()
    )

    if not order_result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to create checkout order"
        )

    order = order_result.data[0]

    try:
        razorpay_order = razorpay_client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": str(order["id"])
        })
    except Exception:

        supabase \
            .table("orders") \
            .update({
                "status": "failed"
            }) \
            .eq("id", order["id"]) \
            .execute()

        log_event(
            session_id=session_id,
            action="razorpay_order_failed",
            details={
                "cart_id": str(payload.cart_id),
                "order_id": str(order["id"]),
                "amount": amount_paise,
                "currency": "INR",
                "status": "failed"
            }
        )

        raise HTTPException(
            status_code=502,
            detail="Failed to create Razorpay order"
        )

    razorpay_order_id = razorpay_order["id"]

    update_result = (
        supabase
        .table("orders")
        .update({
            "razorpay_order_id": razorpay_order_id,
            "status": "payment_pending"
        })
        .eq("id", order["id"])
        .execute()
    )

    if not update_result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to update checkout order"
        )

    log_event(
        session_id=session_id,
        action="checkout_started",
        details={
            "cart_id": str(payload.cart_id),
            "order_id": str(order["id"]),
            "razorpay_order_id": razorpay_order_id,
            "amount": amount_paise,
            "currency": "INR",
            "fresh_total": float(fresh_total),
            "status": "payment_pending"
        }
    )

    log_event(
        session_id=session_id,
        action="razorpay_order_created",
        details={
            "cart_id": str(payload.cart_id),
            "order_id": str(order["id"]),
            "razorpay_order_id": razorpay_order_id,
            "amount": amount_paise,
            "currency": "INR",
            "status": "created"
        }
    )

    return {
        "status": "payment_pending",
        "allowed": True,
        "requires_human_approval": False,
        "cart_id": str(payload.cart_id),
        "session_id": str(session_id),
        "order": {
            "id": str(order["id"]),
            "razorpay_order_id": razorpay_order_id,
            "amount": amount_paise,
            "currency": "INR",
            "status": "payment_pending"
        },
        "items": fresh_items,
        "policy": policy_result
    }


@router.post("/recover")
def recover_checkout(payload: RecoveryRequest):

    cart = get_cart(payload.cart_id)

    session_id = UUID(cart["session_id"])

    if cart["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail="Cart is not active"
        )

    items = cart.get("items") or []

    original_item = next(
        (
            item
            for item in items
            if item.get("product_id") == payload.original_product_id
        ),
        None
    )

    if original_item is None:

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": "Original product is not in the cart",
                "status": "failed"
            }
        )

        return {
            "status": "recovery_failed",
            "reason": "Original product is not in the cart.",
            "cart_id": str(payload.cart_id)
        }

    original_product = get_fresh_product(
        payload.original_product_id
    )

    if original_product is not None and int(
        original_product["stock"]
    ) > 0:

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": "Original product is available again",
                "status": "failed"
            }
        )

        return {
            "status": "recovery_failed",
            "reason": "The original product is available again.",
            "cart_id": str(payload.cart_id)
        }

    substitute = get_fresh_product(
        payload.substitute_product_id
    )

    if substitute is None:

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": "Substitute product no longer exists",
                "status": "failed"
            }
        )

        return {
            "status": "recovery_unavailable",
            "reason": "Substitute product is no longer available.",
            "cart_id": str(payload.cart_id)
        }

    substitute_stock = int(substitute["stock"])

    if substitute_stock <= 0:

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": "Substitute is out of stock",
                "available_stock": substitute_stock,
                "status": "failed"
            }
        )

        return {
            "status": "recovery_unavailable",
            "reason": "The substitute is no longer in stock.",
            "cart_id": str(payload.cart_id),
            "substitute": {
                "id": substitute["id"],
                "name": substitute["name"],
                "price": float(
                    Decimal(str(substitute["price"]))
                ),
                "stock": substitute_stock,
                "image": substitute["image"],
                "category": substitute["category"]
            }
        }

    original_category = (
        original_product["category"]
        if original_product
        else original_item.get("category")
    )

    if substitute["category"] != original_category:

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": "Substitute category does not match original",
                "status": "failed"
            }
        )

        return {
            "status": "recovery_failed",
            "reason": (
                "Substitute does not belong to the same category."
            ),
            "cart_id": str(payload.cart_id)
        }

    substitute_price = Decimal(
        str(substitute["price"])
    )

    current_cart_total = Decimal("0.00")

    for item in items:

        if item.get("product_id") == payload.original_product_id:
            continue

        item_product_id = item.get("product_id")

        if not isinstance(item_product_id, int):
            return {
                "status": "recovery_failed",
                "reason": "Invalid product ID in cart.",
                "cart_id": str(payload.cart_id)
            }

        product = get_fresh_product(item_product_id)

        if product is None:

            log_event(
                session_id=session_id,
                action="recovery_failed",
                details={
                    "cart_id": str(payload.cart_id),
                    "original_product_id": payload.original_product_id,
                    "substitute_product_id": payload.substitute_product_id,
                    "reason": (
                        "Another cart product is no longer available"
                    ),
                    "product_id": item_product_id,
                    "status": "failed"
                }
            )

            return {
                "status": "recovery_failed",
                "reason": (
                    "Another cart product is no longer available."
                ),
                "cart_id": str(payload.cart_id)
            }

        stock = int(product["stock"])

        if stock <= 0:

            log_event(
                session_id=session_id,
                action="recovery_failed",
                details={
                    "cart_id": str(payload.cart_id),
                    "original_product_id": payload.original_product_id,
                    "substitute_product_id": payload.substitute_product_id,
                    "reason": (
                        f"{product['name']} is no longer in stock."
                    ),
                    "product_id": item_product_id,
                    "available_stock": stock,
                    "status": "failed"
                }
            )

            return {
                "status": "recovery_failed",
                "reason": (
                    f"{product['name']} is no longer in stock."
                ),
                "cart_id": str(payload.cart_id)
            }

        quantity = item.get("quantity")

        if not isinstance(quantity, int) or quantity <= 0:
            return {
                "status": "recovery_failed",
                "reason": "Invalid quantity in cart.",
                "cart_id": str(payload.cart_id)
            }

        if quantity > stock:
            return {
                "status": "recovery_failed",
                "reason": (
                    f"Only {stock} units of "
                    f"{product['name']} are available."
                ),
                "cart_id": str(payload.cart_id)
            }

        current_cart_total += (
            Decimal(str(product["price"]))
            * quantity
        )

    original_quantity = original_item.get("quantity")

    if (
        not isinstance(original_quantity, int)
        or original_quantity <= 0
    ):
        return {
            "status": "recovery_failed",
            "reason": "Invalid original product quantity.",
            "cart_id": str(payload.cart_id)
        }

    if original_quantity > substitute_stock:

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": "Substitute has insufficient stock",
                "available_stock": substitute_stock,
                "requested_quantity": original_quantity,
                "status": "failed"
            }
        )

        return {
            "status": "recovery_unavailable",
            "reason": (
                f"Only {substitute_stock} units of "
                f"{substitute['name']} are available."
            ),
            "cart_id": str(payload.cart_id),
            "substitute": {
                "id": substitute["id"],
                "name": substitute["name"],
                "price": float(substitute_price),
                "stock": substitute_stock,
                "image": substitute["image"],
                "category": substitute["category"]
            }
        }

    replacement_total = (
        substitute_price * original_quantity
    )

    new_cart_total = (
        current_cart_total + replacement_total
    ).quantize(Decimal("0.01"))

    policy_result = check_policy(
        action="checkout",
        cart_total=current_cart_total,
        product_price=replacement_total,
        product_category=substitute["category"],
        stock=substitute_stock,
        is_upsell=False
    )

    log_event(
        session_id=session_id,
        action="recovery_policy_decision",
        details={
            "cart_id": str(payload.cart_id),
            "original_product_id": payload.original_product_id,
            "substitute_product_id": payload.substitute_product_id,
            "current_cart_total": float(current_cart_total),
            "substitute_price": float(substitute_price),
            "replacement_quantity": original_quantity,
            "new_cart_total": float(new_cart_total),
            "autonomous_limit": float(
                MAX_AUTONOMOUS_CART_VALUE
            ),
            "policy_status": policy_result["status"],
            "allowed": policy_result["allowed"],
            "requires_human_approval": (
                policy_result["requires_human_approval"]
            ),
            "reason": policy_result["reason"]
        }
    )

    if policy_result["status"] == "approval_required":

        return {
            "status": "approval_required",
            "requires_human_approval": True,
            "reason": policy_result["reason"],
            "cart_id": str(payload.cart_id),
            "new_cart_total": float(new_cart_total),
            "autonomous_limit": float(
                MAX_AUTONOMOUS_CART_VALUE
            ),
            "substitute": {
                "id": substitute["id"],
                "name": substitute["name"],
                "price": float(substitute_price),
                "stock": substitute_stock,
                "image": substitute["image"],
                "category": substitute["category"]
            },
            "policy": policy_result
        }

    if policy_result["status"] != "allowed":

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": policy_result["reason"],
                "policy": policy_result,
                "status": "failed"
            }
        )

        return {
            "status": "recovery_failed",
            "requires_human_approval": False,
            "reason": policy_result["reason"],
            "cart_id": str(payload.cart_id),
            "policy": policy_result
        }

    updated_items, updated_total = replace_cart_item(
        cart=cart,
        original_product_id=payload.original_product_id,
        substitute_product=substitute,
        quantity=original_quantity
    )

    update_result = (
        supabase
        .table("carts")
        .update({
            "items": updated_items,
            "subtotal": float(updated_total),
            "total": float(updated_total)
        })
        .eq("id", str(payload.cart_id))
        .eq("status", "active")
        .execute()
    )

    if not update_result.data:

        log_event(
            session_id=session_id,
            action="recovery_failed",
            details={
                "cart_id": str(payload.cart_id),
                "original_product_id": payload.original_product_id,
                "substitute_product_id": payload.substitute_product_id,
                "reason": "Failed to update cart",
                "status": "failed"
            }
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to replace cart item"
        )

    updated_cart = update_result.data[0]

    log_event(
        session_id=session_id,
        action="substitute_accepted",
        details={
            "cart_id": str(payload.cart_id),
            "original_product_id": payload.original_product_id,
            "original_product_name": original_item.get("name"),
            "substitute_product_id": substitute["id"],
            "substitute_name": substitute["name"],
            "quantity": original_quantity,
            "old_cart_total": float(
                Decimal(str(cart.get("total") or 0))
            ),
            "new_cart_total": float(updated_total),
            "status": "success"
        }
    )

    log_event(
        session_id=session_id,
        action="cart_item_replaced",
        details={
            "cart_id": str(payload.cart_id),
            "original_product_id": payload.original_product_id,
            "substitute_product_id": substitute["id"],
            "substitute_name": substitute["name"],
            "quantity": original_quantity,
            "subtotal": updated_cart["subtotal"],
            "total": updated_cart["total"],
            "status": "success"
        }
    )

    return {
        "status": "recovered",
        "success": True,
        "requires_human_approval": False,
        "cart_id": str(payload.cart_id),
        "original_product_id": payload.original_product_id,
        "substitute": {
            "id": substitute["id"],
            "name": substitute["name"],
            "description": substitute["description"],
            "price": float(substitute_price),
            "stock": substitute_stock,
            "image": substitute["image"],
            "category": substitute["category"]
        },
        "quantity": original_quantity,
        "old_cart_total": float(
            Decimal(str(cart.get("total") or 0))
        ),
        "new_cart_total": float(updated_total),
        "cart": updated_cart,
        "policy": policy_result
    }


@router.post("/confirm")
def confirm_payment(payload: PaymentConfirmation):

    order_result = (
        supabase
        .table("orders")
        .select("*")
        .eq(
            "razorpay_order_id",
            payload.razorpay_order_id
        )
        .execute()
    )

    if not order_result.data:
        raise HTTPException(
            status_code=404,
            detail="Checkout order not found"
        )

    order = order_result.data[0]

    if order["status"] == "paid":
        return {
            "status": "paid",
            "already_processed": True,
            "order": {
                "id": order["id"],
                "razorpay_order_id": order["razorpay_order_id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "status": "paid"
            }
        }

    if order["status"] != "payment_pending":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Order cannot be confirmed from status: "
                f"{order['status']}"
            )
        )

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature
        })
    except Exception:
        session_id = UUID(order["session_id"])

        supabase \
            .table("orders") \
            .update({
                "status": "failed"
            }) \
            .eq("id", order["id"]) \
            .execute()

        log_event(
            session_id=session_id,
            action="payment_failed",
            details={
                "order_id": order["id"],
                "razorpay_order_id": payload.razorpay_order_id,
                "razorpay_payment_id": payload.razorpay_payment_id,
                "amount": order["amount"],
                "currency": order["currency"],
                "reason": "Payment signature verification failed",
                "status": "failed"
            }
        )

        return {
            "status": "failed",
            "already_processed": False,
            "reason": "Payment verification failed."
        }

    session_id = UUID(order["session_id"])

    if not order.get("cart_id"):
        raise HTTPException(
            status_code=500,
            detail="Order is not linked to a cart"
        )

    finalization_result = (
        supabase
        .rpc(
            "finalize_paid_order",
            {
                "p_order_id": str(order["id"]),
                "p_payment_id": payload.razorpay_payment_id
            }
        )
        .execute()
    )

    result = finalization_result.data

    if not result:
        raise HTTPException(
            status_code=500,
            detail="Failed to finalize paid order"
        )

    if result.get("already_processed"):
        return {
            "status": "paid",
            "already_processed": True,
            "order": {
                "id": order["id"],
                "razorpay_order_id": order["razorpay_order_id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "status": "paid"
            }
        }

    if not result.get("success"):
        log_event(
            session_id=session_id,
            action="payment_finalization_failed",
            details={
                "order_id": order["id"],
                "razorpay_order_id": payload.razorpay_order_id,
                "razorpay_payment_id": payload.razorpay_payment_id,
                "amount": order["amount"],
                "currency": order["currency"],
                "reason": result.get("reason"),
                "product_id": result.get("product_id"),
                "available_stock": result.get("available_stock"),
                "requested_quantity": result.get(
                    "requested_quantity"
                ),
                "status": "failed"
            }
        )

        return {
            "status": "failed",
            "already_processed": False,
            "reason": result.get(
                "reason",
                "Payment finalization failed."
            )
        }

    log_event(
        session_id=session_id,
        action="payment_confirmed",
        details={
            "order_id": order["id"],
            "cart_id": order["cart_id"],
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "amount": order["amount"],
            "currency": order["currency"],
            "status": "paid"
        }
    )

    return {
        "status": "paid",
        "already_processed": False,
        "order": {
            "id": order["id"],
            "razorpay_order_id": order["razorpay_order_id"],
            "razorpay_payment_id": payload.razorpay_payment_id,
            "amount": order["amount"],
            "currency": order["currency"],
            "status": "paid"
        }
    }