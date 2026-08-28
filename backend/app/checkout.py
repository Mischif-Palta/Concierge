from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import supabase
from app.policy import check_policy, MAX_AUTONOMOUS_CART_VALUE
from app.audit import log_event
from razorpay_client import client as razorpay_client


router = APIRouter(prefix="/checkout", tags=["Checkout"])


class CheckoutRequest(BaseModel):
    cart_id: UUID

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

            log_event(
                session_id=session_id,
                action="checkout_blocked",
                details={
                    "cart_id": str(payload.cart_id),
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "requested_quantity": quantity,
                    "available_stock": product_stock,
                    "reason": "Product is out of stock",
                    "status": "blocked"
                }
            )

            return {
                "status": "blocked",
                "allowed": False,
                "requires_human_approval": False,
                "reason": f"{product['name']} is out of stock.",
                "cart_id": str(payload.cart_id),
                "product_id": product["id"]
            }

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

    policy_result = check_policy(
        action="checkout",
        cart_total=Decimal("0"),
        product_price=fresh_total,
        product_category=None,
        stock=None,
        is_upsell=False
    )

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
            "reason": policy_result["reason"]
        }
    )

    if policy_result["status"] == "approval_required":

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

    if policy_result["status"] != "allowed":

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
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "amount": order["amount"],
            "currency": order["currency"],
            "status": "paid"
        }
    }