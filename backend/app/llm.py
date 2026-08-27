import json
import os

from groq import Groq


# ============================================================
# GROQ CLIENT
# ============================================================

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# ============================================================
# UPSELL SELECTION
# ============================================================

def select_upsell(candidates: list[dict]) -> dict | None:
    """
    Ask the LLM to select ONE product from the provided
    validated candidates.

    The LLM must not invent products.
    """

    if not candidates:
        return None

    # --------------------------------------------------------
    # Build controlled candidate data
    # --------------------------------------------------------

    candidate_data = []

    for candidate in candidates:

        candidate_data.append({
            "product_id": candidate["id"],
            "name": candidate["name"],
            "description": candidate.get("description"),
            "price": candidate["price"],
            "category": candidate.get("category"),
            "agent_tags": candidate.get("agent_tags") or [],
        })

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------

    prompt = f"""
You are Concierge, an AI commerce assistant.

Your task is to select the SINGLE most natural cross-sell
product from the provided candidate products.

IMPORTANT RULES:

1. You MUST choose exactly one product from the candidates.
2. NEVER invent a product.
3. NEVER modify a product_id.
4. Use only the information provided.
5. Give one concise, product-specific reason.
6. Do not invent customer statistics or purchase percentages.
7. Return ONLY valid JSON.

Current candidate products:

{json.dumps(candidate_data, indent=2)}

Return exactly:

{{
  "product_id": <integer>,
  "reasoning": "<one sentence>"
}}
"""

    # --------------------------------------------------------
    # Groq request
    # --------------------------------------------------------

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise commerce recommendation "
                    "engine. Follow the provided catalog strictly."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        response_format={
            "type": "json_object"
        }
    )

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    content = response.choices[0].message.content

    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None

    # --------------------------------------------------------
    # Validate structure
    # --------------------------------------------------------

    if not isinstance(result, dict):
        return None

    product_id = result.get("product_id")
    reasoning = result.get("reasoning")

    if not isinstance(product_id, int):
        return None

    if not isinstance(reasoning, str):
        return None

    reasoning = reasoning.strip()

    if not reasoning:
        return None

    # --------------------------------------------------------
    # CRITICAL: validate product against candidates
    # --------------------------------------------------------

    candidate_ids = {
        int(candidate["id"])
        for candidate in candidates
    }

    if product_id not in candidate_ids:
        return None

    # --------------------------------------------------------
    # Return validated model decision
    # --------------------------------------------------------

    return {
        "product_id": product_id,
        "reasoning": reasoning
    }