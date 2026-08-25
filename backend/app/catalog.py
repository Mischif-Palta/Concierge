from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.db import supabase

class Product(BaseModel):
    id: int
    name: str
    description: str | None = None
    price: float
    category: str | None = None
    brand: str | None = None
    image: str | None = None
    thumbnail: str | None = None
    stock: int
    in_stock: bool
    rating: float | None = None
    discount_percentage: float = 0
    tags: list[str] = []
    pairs_with: list[int] = []
    substitute_products: list[int] = []
    agent_tags: list[str] = []
    upsell_priority: int = 0


class CatalogResponse(BaseModel):
    products: list[Product]
    count: int


class SearchResponse(BaseModel):
    query: str
    products: list[Product]
    count: int

router = APIRouter(
    prefix="/catalog",
    tags=["Catalog"],
)

def format_product(product: dict) -> dict:
    """
    Convert the raw Supabase product record into the
    public Concierge catalog format.
    """

    stock = int(product.get("stock") or 0)

    return {
        "id": product["id"],
        "name": product["name"],
        "description": product.get("description"),
        "price": float(product["price"]),
        "category": product.get("category"),
        "brand": product.get("brand"),
        "image": product.get("image"),
        "thumbnail": product.get("thumbnail"),
        "stock": stock,
        "in_stock": stock > 0,
        "rating": (
            float(product["rating"])
            if product.get("rating") is not None
            else None
        ),
        "discount_percentage": (
            float(product["discount_percentage"])
            if product.get("discount_percentage") is not None
            else 0
        ),
        "tags": product.get("tags") or [],
        "pairs_with": product.get("pairs_with") or [],
        "substitute_products": (
            product.get("substitute_products") or []
        ),
        "agent_tags": product.get("agent_tags") or [],
        "upsell_priority": (
            product.get("upsell_priority") or 0
        ),
    }


@router.get("", response_model=CatalogResponse)
def get_catalog(
    category: Optional[str] = Query(
        default=None
    ),
    min_price: Optional[float] = Query(
        default=None,
        ge=0
    ),
    max_price: Optional[float] = Query(
        default=None,
        ge=0
    ),
    tag: Optional[str] = Query(
        default=None
    ),
    in_stock: Optional[bool] = Query(
        default=None
    ),
):
    """
    Return the Concierge product catalog.

    Supports optional category, price, tag,
    and stock filters.
    """

    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=400,
            detail="min_price cannot be greater than max_price",
        )

    query = (
        supabase
        .table("products")
        .select("*")
    )

    if category:
        query = query.eq(
            "category",
            category
        )

    if min_price is not None:
        query = query.gte(
            "price",
            min_price
        )

    if max_price is not None:
        query = query.lte(
            "price",
            max_price
        )

    if in_stock is True:
        query = query.gt(
            "stock",
            0
        )

    elif in_stock is False:
        query = query.eq(
            "stock",
            0
        )

    response = query.order(
        "id"
    ).execute()

    products = response.data or []

    if tag:
        tag_lower = tag.lower()

        products = [
            product
            for product in products
            if tag_lower in [
                str(value).lower()
                for value in (
                    product.get("tags") or []
                )
            ]
            or tag_lower in [
                str(value).lower()
                for value in (
                    product.get("agent_tags") or []
                )
            ]
        ]

    formatted_products = [
        format_product(product)
        for product in products
    ]

    return {
        "products": formatted_products,
        "count": len(formatted_products),
    }


@router.get("/search", response_model=SearchResponse)
def search_catalog(
    q: str = Query(
        ...,
        min_length=1
    )
):
    """
    Search the Concierge catalog by product name,
    description, category, or brand.
    """

    search_term = q.strip()

    if not search_term:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty",
        )

    response = (
        supabase
        .table("products")
        .select("*")
        .or_(
            f"name.ilike.%{search_term}%,"
            f"description.ilike.%{search_term}%,"
            f"category.ilike.%{search_term}%,"
            f"brand.ilike.%{search_term}%"
        )
        .order("id")
        .execute()
    )

    products = response.data or []

    formatted_products = [
        format_product(product)
        for product in products
    ]

    return {
        "query": search_term,
        "products": formatted_products,
        "count": len(formatted_products),
    }


@router.get("/{product_id}", response_model=Product)
def get_product(
    product_id: int
):
    """
    Return a single product by ID.
    """

    response = (
        supabase
        .table("products")
        .select("*")
        .eq("id", product_id)
        .maybe_single()
        .execute()
    )

    product = response.data

    if not product:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "product_not_found",
                "message": (
                    f"Product {product_id} "
                    "was not found"
                ),
            },
        )

    return format_product(product)