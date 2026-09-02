from fastapi import APIRouter, HTTPException
import requests

router = APIRouter(prefix="/interop", tags=["interop"])

BASE_URL = "http://127.0.0.1:8000"


def api_request(method, path, payload=None):
    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        json=payload,
        timeout=30
    )

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    return response.json()


@router.post("/run")
def run_independent_agent():
    logs = []

    logs.append({
        "step": "catalog",
        "message": "GET /catalog"
    })

    catalog = api_request("GET", "/catalog")

    logs.append({
        "step": "catalog",
        "message": f"{catalog.get('count', 0)} products returned"
    })

    products = [
        product
        for product in catalog.get("products", [])
        if product.get("in_stock")
        and product.get("price", 0) <= 1000
    ]

    if not products:
        raise HTTPException(
            status_code=404,
            detail="No in-stock product found under ₹1,000"
        )

    product = products[0]

    logs.append({
        "step": "selection",
        "message": f"Selected {product['name']} — ₹{product['price']}"
    })

    logs.append({
        "step": "session",
        "message": "POST /sessions"
    })

    session = api_request(
        "POST",
        "/sessions",
        {"actor_type": "bare_agent"}
    )

    session_id = session["session_id"]

    logs.append({
        "step": "session",
        "message": f"Session created — {session_id}"
    })

    logs.append({
        "step": "cart",
        "message": "POST /cart"
    })

    cart = api_request(
        "POST",
        "/cart",
        {"session_id": session_id}
    )

    cart_id = cart["cart_id"]

    logs.append({
        "step": "cart",
        "message": f"Cart created — {cart_id}"
    })

    logs.append({
        "step": "cart",
        "message": "POST /cart/{cart_id}/items"
    })

    item_result = api_request(
        "POST",
        f"/cart/{cart_id}/items",
        {
            "product_id": product["id"],
            "quantity": 1
        }
    )

    logs.append({
        "step": "policy",
        "message": f"Policy: {item_result.get('policy', {}).get('status')}"
    })

    if not item_result.get("success"):
        return {
            "status": "approval_required",
            "product": product,
            "session_id": session_id,
            "cart_id": cart_id,
            "logs": logs
        }

    logs.append({
        "step": "checkout",
        "message": "POST /checkout"
    })

    checkout = api_request(
        "POST",
        "/checkout",
        {"cart_id": cart_id}
    )

    logs.append({
        "step": "checkout",
        "message": f"Checkout status: {checkout.get('status')}"
    })

    order = checkout.get("order", {})

    if order.get("razorpay_order_id"):
        logs.append({
            "step": "payment",
            "message": f"Razorpay test order created — {order['razorpay_order_id']}"
        })

    return {
        "status": checkout.get("status"),
        "allowed": checkout.get("allowed"),
        "product": product,
        "session_id": session_id,
        "cart_id": cart_id,
        "order": order,
        "logs": logs
    }