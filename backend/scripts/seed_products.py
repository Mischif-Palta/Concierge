import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client


# ============================================================
# Configuration
# ============================================================

load_dotenv()

DUMMYJSON_URL = "https://dummyjson.com/products?limit=0"

# DummyJSON prices are USD.
# Concierge demo catalog is represented in INR.
USD_TO_INR = 84

SELECT_COUNTS = {
    "sports-accessories": 17,
    "mens-shoes": 5,
    "mobile-accessories": 4,
    "mens-watches": 2,
    "sunglasses": 2,
}


# ============================================================
# Supabase
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
        "must be configured in .env"
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# ============================================================
# Concierge Product Relationships
# ============================================================

PRODUCT_RELATIONSHIPS = {

    # --------------------------------------------------------
    # Sports
    # --------------------------------------------------------

    137: {  # American Football
        "pairs_with": [147],
        "substitute_products": [],
    },

    138: {  # Baseball Ball
        "pairs_with": [139, 150],
        "substitute_products": [151],
    },

    139: {  # Baseball Glove
        "pairs_with": [138, 150],
        "substitute_products": [],
    },

    140: {  # Basketball
        "pairs_with": [141],
        "substitute_products": [147, 153],
    },

    141: {  # Basketball Rim
        "pairs_with": [140],
        "substitute_products": [],
    },

    142: {  # Cricket Ball
        "pairs_with": [143, 144, 145],
        "substitute_products": [],
    },

    143: {  # Cricket Bat
        "pairs_with": [142, 144, 145],
        "substitute_products": [],
    },

    144: {  # Cricket Helmet
        "pairs_with": [143, 142],
        "substitute_products": [],
    },

    145: {  # Cricket Wicket
        "pairs_with": [143, 142],
        "substitute_products": [],
    },

    146: {  # Feather Shuttlecock
        "pairs_with": [152],
        "substitute_products": [151],
    },

    147: {  # Football
        "pairs_with": [137, 140],
        "substitute_products": [153],
    },

    148: {  # Golf Ball
        "pairs_with": [149],
        "substitute_products": [],
    },

    149: {  # Iron Golf
        "pairs_with": [148],
        "substitute_products": [],
    },

    150: {  # Metal Baseball Bat
        "pairs_with": [138, 139],
        "substitute_products": [],
    },

    151: {  # Tennis Ball
        "pairs_with": [152],
        "substitute_products": [146],
    },

    152: {  # Tennis Racket
        "pairs_with": [151, 146],
        "substitute_products": [],
    },

    153: {  # Volleyball
        "pairs_with": [140, 147],
        "substitute_products": [140, 147],
    },


    # --------------------------------------------------------
    # Shoes
    # --------------------------------------------------------

    88: {  # Nike Air Jordan 1 Red And Black
        "pairs_with": [89, 90, 91, 92],
        "substitute_products": [90, 91, 92],
    },

    89: {  # Nike Baseball Cleats
        "pairs_with": [143, 147],
        "substitute_products": [90],
    },

    90: {  # Puma Future Rider Trainers
        "pairs_with": [91, 92],
        "substitute_products": [88, 91, 92],
    },

    91: {  # Sports Sneakers Off White & Red
        "pairs_with": [90, 92],
        "substitute_products": [90, 92],
    },

    92: {  # Sports Sneakers Off White Red
        "pairs_with": [90, 91],
        "substitute_products": [90, 91],
    },


    # --------------------------------------------------------
    # Mobile Accessories
    # --------------------------------------------------------

    99: {  # Amazon Echo Plus
        "pairs_with": [100, 101, 102],
        "substitute_products": [],
    },

    100: {  # Apple Airpods
        "pairs_with": [102],
        "substitute_products": [101],
    },

    101: {  # Apple AirPods Max Silver
        "pairs_with": [102],
        "substitute_products": [100],
    },

    102: {  # Apple Airpower Wireless Charger
        "pairs_with": [100, 101],
        "substitute_products": [],
    },


    # --------------------------------------------------------
    # Watches
    # --------------------------------------------------------

    93: {  # Brown Leather Belt Watch
        "pairs_with": [94],
        "substitute_products": [],
    },

    94: {  # Longines Master Collection
        "pairs_with": [93],
        "substitute_products": [],
    },


    # --------------------------------------------------------
    # Sunglasses
    # --------------------------------------------------------

    154: {  # Black Sun Glasses
        "pairs_with": [],
        "substitute_products": [155],
    },

    155: {  # Classic Sun Glasses
        "pairs_with": [],
        "substitute_products": [154],
    },
}


# ============================================================
# Fetch DummyJSON Products
# ============================================================

def fetch_products():
    response = requests.get(
        DUMMYJSON_URL,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    print(
        f"DummyJSON products available: "
        f"{data['total']}"
    )

    return data["products"]


# ============================================================
# Select Concierge Catalog
# ============================================================

def select_products(products):

    selected = []

    for category, count in SELECT_COUNTS.items():

        category_products = [
            product
            for product in products
            if product.get("category") == category
        ]

        category_products.sort(
            key=lambda product: product["id"]
        )

        chosen = category_products[:count]

        print(
            f"{category}: "
            f"{len(chosen)}/{count} selected"
        )

        selected.extend(chosen)

    if len(selected) != 30:
        raise RuntimeError(
            f"Expected 30 products, "
            f"got {len(selected)}"
        )

    return selected


# ============================================================
# Normalize Price
# ============================================================

def normalize_price(price):
    """
    Convert DummyJSON USD demo pricing into INR.
    """

    return round(
        float(price) * USD_TO_INR,
        2,
    )


# ============================================================
# Build Agent Tags
# ============================================================

def build_agent_tags(product):

    tags = set()

    category = product.get(
        "category",
        "",
    )

    name = product.get(
        "title",
        "",
    )

    tags.add(category)

    for tag in product.get(
        "tags",
        [],
    ):
        tags.add(
            tag.lower()
        )

    name_lower = name.lower()

    # Sports
    sports_keywords = [
        "cricket",
        "football",
        "basketball",
        "tennis",
        "golf",
        "baseball",
        "volleyball",
        "shuttlecock",
    ]

    if any(
        word in name_lower
        for word in sports_keywords
    ):
        tags.add("sports")

    # Footwear
    if "shoe" in name_lower or "sneaker" in name_lower:
        tags.add("footwear")

    # Wearables
    if "watch" in name_lower:
        tags.add("wearable")

    # Technology
    if category == "mobile-accessories":
        tags.add("technology")

    if "airpods" in name_lower:
        tags.add("audio")

    if "charger" in name_lower:
        tags.add("charging")

    # Fashion
    if category == "sunglasses":
        tags.add("fashion")
        tags.add("eyewear")

    return sorted(tags)


# ============================================================
# Normalize Product
# ============================================================

def normalize_product(product):

    product_id = product["id"]

    images = product.get(
        "images",
        [],
    )

    image = (
        images[0]
        if images
        else None
    )

    stock = int(
        product.get(
            "stock",
            0,
        )
    )

    relationships = PRODUCT_RELATIONSHIPS.get(
        product_id,
        {
            "pairs_with": [],
            "substitute_products": [],
        },
    )

    return {
        "id": product_id,

        "name": product.get(
            "title"
        ),

        "description": product.get(
            "description"
        ),

        "price": normalize_price(
            product.get(
                "price",
                0,
            )
        ),

        "category": product.get(
            "category"
        ),

        "brand": product.get(
            "brand"
        ),

        "image": image,

        "thumbnail": product.get(
            "thumbnail"
        ),

        "stock": stock,

        "rating": product.get(
            "rating"
        ),

        "discount_percentage": product.get(
            "discountPercentage",
            0,
        ),

        "tags": product.get(
            "tags",
            []
        ),

        "pairs_with": relationships[
            "pairs_with"
        ],

        "substitute_products": relationships[
            "substitute_products"
        ],

        "agent_tags": build_agent_tags(
            product
        ),

        "upsell_priority": 5,
    }


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=== Concierge Product Seeder ===")
    print()

    # --------------------------------------------------------
    # Fetch
    # --------------------------------------------------------

    products = fetch_products()

    # --------------------------------------------------------
    # Select
    # --------------------------------------------------------

    selected = select_products(
        products
    )

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    normalized = [
        normalize_product(product)
        for product in selected
    ]

    print()
    print(
        f"Normalized products: "
        f"{len(normalized)}"
    )

    # --------------------------------------------------------
    # Display catalog
    # --------------------------------------------------------

    print()
    print("Selected catalog:")
    print()

    for product in normalized:

        print(
            f"{product['id']:>3} | "
            f"{product['name']:<35} | "
            f"₹{product['price']:<10} | "
            f"stock={product['stock']}"
        )

    # --------------------------------------------------------
    # Display relationships
    # --------------------------------------------------------

    print()
    print("Product relationships:")
    print()

    for product in normalized:

        pairs = product[
            "pairs_with"
        ]

        substitutes = product[
            "substitute_products"
        ]

        if pairs or substitutes:

            print(
                f"{product['id']} "
                f"{product['name']}"
            )

            if pairs:
                print(
                    f"  pairs_with: "
                    f"{pairs}"
                )

            if substitutes:
                print(
                    f"  substitutes: "
                    f"{substitutes}"
                )

    # --------------------------------------------------------
    # Supabase Upsert
    # --------------------------------------------------------

    print()
    print(
        "Inserting into Supabase..."
    )

    response = (
        supabase
        .table("products")
        .upsert(normalized)
        .execute()
    )

    print()
    print(
        "Supabase insert/update completed."
    )

    print(
        f"Records processed: "
        f"{len(response.data)}"
    )

    print()
    print(
        "=== Concierge Product Seeder Complete ==="
    )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()