from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import supabase
from app.policy import check_policy, ALLOWED_CATEGORIES
from app.audit import log_event
from app.llm import select_upsell
from app.cart import format_cart


router = APIRouter(prefix="/cart", tags=["Upsell"])


class UpsellAcceptRequest(BaseModel):
    product_id: int


def generate_upsell_candidates(cart: dict) -> list[dict]:
    items = cart.get("items") or []

    if not items:
        return []

    cart_product_ids = {
        int(item["product_id"])
        for item in items
    }

    candidate_ids = set()

    for item in items:
        product_id = int(item["product_id"])

        product_result = (
            supabase
            .table("products")
            .select("id, pairs_with")
            .eq("id", product_id)
            .maybe_single()
            .execute()
        )

        product = product_result.data

        if not product:
            continue

        for candidate_id in product.get("pairs_with") or []:
            try:
                candidate_ids.add(int(candidate_id))
            except (TypeError, ValueError):
                continue

    candidate_ids -= cart_product_ids

    if not candidate_ids:
        return []

    response = (
        supabase
        .table("products")
        .select(
            """
            id,
            name,
            description,
            price,
            category,
            brand,
            image,
            thumbnail,
            stock,
            pairs_with,
            agent_tags,
            upsell_priority
            """
        )
        .in_("id", list(candidate_ids))
        .execute()
    )

    candidates = response.data or []

    valid_candidates = []

    for product in candidates:
        product_id = int(product["id"])
        stock = int(product.get("stock") or 0)
        category = product.get("category")

        if stock <= 0:
            continue

        if product_id in cart_product_ids:
            continue

        if category not in ALLOWED_CATEGORIES:
            continue

        valid_candidates.append({
            "id": product_id,
            "name": product["name"],
            "description": product.get("description"),
            "price": float(product["price"]),
            "category": category,
            "brand": product.get("brand"),
            "image": product.get("image"),
            "thumbnail": product.get("thumbnail"),
            "stock": stock,
            "agent_tags": product.get("agent_tags") or [],
            "upsell_priority": product.get("upsell_priority") or 0
        })

    valid_candidates.sort(
        key=lambda product: (
            -int(product["upsell_priority"]),
            float(product["price"])
        )
    )

    return valid_candidates


@router.post("/{cart_id}/upsell")
def create_upsell(cart_id: UUID):
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

    candidates = generate_upsell_candidates(cart)

    if not candidates:
        return {
            "success": False,
            "recommendation": None,
            "message": "No valid upsell candidates available."
        }

    selection = select_upsell(candidates)

    if not selection:
        log_event(
            session_id=session_id,
            action="upsell_blocked",
            details={
                "cart_id": str(cart_id),
                "reason": "LLM returned an invalid upsell recommendation.",
                "candidate_count": len(candidates)
            }
        )

        return {
            "success": False,
            "recommendation": None,
            "message": "Unable to generate a valid upsell recommendation."
        }

    selected_product = next(
        (
            candidate
            for candidate in candidates
            if candidate["id"] == selection["product_id"]
        ),
        None
    )

    if not selected_product:
        log_event(
            session_id=session_id,
            action="upsell_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": selection["product_id"],
                "reason": "LLM selected a product outside the validated candidate set."
            }
        )

        return {
            "success": False,
            "recommendation": None,
            "message": "Invalid upsell recommendation."
        }

    product_result = (
        supabase
        .table("products")
        .select(
            "id, name, price, category, image, thumbnail, stock"
        )
        .eq("id", selected_product["id"])
        .maybe_single()
        .execute()
    )

    product = product_result.data

    if not product:
        log_event(
            session_id=session_id,
            action="upsell_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": selected_product["id"],
                "reason": "Recommended product no longer exists."
            }
        )

        return {
            "success": False,
            "recommendation": None,
            "message": "Recommended product is no longer available."
        }

    stock = int(product.get("stock") or 0)

    current_cart_total = Decimal(
        str(cart.get("total") or 0)
    )

    product_price = Decimal(
        str(product["price"])
    )

    policy_result = check_policy(
        action="upsell",
        cart_total=current_cart_total,
        product_price=product_price,
        product_category=product.get("category"),
        stock=stock,
        is_upsell=True
    )

    log_event(
        session_id=session_id,
        action="upsell_proposed",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "price": float(product_price),
            "reasoning": selection["reasoning"],
            "candidate_source": "pairs_with",
            "current_cart_total": float(current_cart_total),
            "policy_status": policy_result["status"],
            "allowed": policy_result["allowed"],
            "requires_human_approval": policy_result["requires_human_approval"],
            "reason": policy_result["reason"]
        }
    )

    return {
        "success": True,
        "suggested_item": {
            "id": product["id"],
            "name": product["name"],
            "price": float(product_price),
            "image": product.get("image"),
            "thumbnail": product.get("thumbnail"),
            "stock": stock
        },
        "price_delta": float(product_price),
        "reasoning": selection["reasoning"],
        "policy": policy_result
    }

@router.post("/{cart_id}/upsell/accept")
def accept_upsell(
    cart_id: UUID,
    payload: UpsellAcceptRequest
):
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

    product_result = (
        supabase
        .table("products")
        .select(
            "id, name, price, category, image, thumbnail, stock"
        )
        .eq("id", payload.product_id)
        .maybe_single()
        .execute()
    )

    product = product_result.data

    if not product:
        log_event(
            session_id=session_id,
            action="upsell_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": payload.product_id,
                "reason": "Product not found during upsell acceptance."
            }
        )

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    items = cart.get("items") or []

    if any(
        int(item["product_id"]) == payload.product_id
        for item in items
    ):
        log_event(
            session_id=session_id,
            action="upsell_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "reason": "Product is already in the cart."
            }
        )

        raise HTTPException(
            status_code=400,
            detail="Product is already in the cart"
        )

    stock = int(product.get("stock") or 0)

    if stock <= 0:
        log_event(
            session_id=session_id,
            action="upsell_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "reason": "Product became out of stock before acceptance.",
                "stock": stock
            }
        )

        return {
            "success": False,
            "cart": {
                "items": items,
                "item_count": sum(
                    item["quantity"]
                    for item in items
                ),
                "subtotal": cart["subtotal"],
                "total": cart["total"],
                "status": cart["status"]
            },
            "policy": {
                "allowed": False,
                "requires_human_approval": False,
                "status": "blocked",
                "reason": "Product is out of stock."
            }
        }

    current_cart_total = Decimal(
        str(cart.get("total") or 0)
    )

    product_price = Decimal(
        str(product["price"])
    )

    policy_result = check_policy(
        action="upsell_accept",
        cart_total=current_cart_total,
        product_price=product_price,
        product_category=product.get("category"),
        stock=stock,
        is_upsell=True
    )

    if policy_result["status"] != "allowed":
        log_event(
            session_id=session_id,
            action="upsell_blocked",
            details={
                "cart_id": str(cart_id),
                "product_id": product["id"],
                "product_name": product["name"],
                "price": float(product_price),
                "current_cart_total": float(current_cart_total),
                "policy_status": policy_result["status"],
                "reason": policy_result["reason"]
            }
        )

        return {
            "success": False,
            "cart": {
                "items": items,
                "item_count": sum(
                    item["quantity"]
                    for item in items
                ),
                "subtotal": cart["subtotal"],
                "total": cart["total"],
                "status": cart["status"]
            },
            "policy": policy_result
        }

    items.append({
        "product_id": product["id"],
        "name": product["name"],
        "price": float(product_price),
        "quantity": 1,
        "stock": stock,
        "image": product.get("image")
    })

    subtotal = Decimal("0")

    for item in items:
        subtotal += (
            Decimal(str(item["price"]))
            * Decimal(str(item["quantity"]))
        )

    subtotal = subtotal.quantize(
        Decimal("0.01")
    )

    update_result = (
        supabase
        .table("carts")
        .update({
            "items": items,
            "subtotal": float(subtotal),
            "total": float(subtotal)
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
        action="upsell_accepted",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "price": float(product_price),
            "quantity": 1,
            "subtotal": updated_cart["subtotal"],
            "total": updated_cart["total"],
            "policy_status": policy_result["status"],
            "status": "success"
        }
    )

    return {
        "success": True,
        "cart": format_cart(updated_cart),
        "policy": policy_result
    }

@router.post("/{cart_id}/upsell/decline")
def decline_upsell(
    cart_id: UUID,
    payload: UpsellAcceptRequest
):
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

    session_id = UUID(cart["session_id"])

    product_result = (
        supabase
        .table("products")
        .select("id, name, price")
        .eq("id", payload.product_id)
        .maybe_single()
        .execute()
    )

    product = product_result.data

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    items = cart.get("items") or []

    log_event(
        session_id=session_id,
        action="upsell_declined",
        details={
            "cart_id": str(cart_id),
            "product_id": product["id"],
            "product_name": product["name"],
            "price": float(product["price"]),
            "status": "declined"
        }
    )

    return {
        "success": True,
        "message": "Upsell declined.",
        "declined_item": {
            "id": product["id"],
            "name": product["name"],
            "price": float(product["price"])
        },
        "cart": format_cart(cart)
    }