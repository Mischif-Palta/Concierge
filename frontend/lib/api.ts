import type {
  AuditResponse,
  Cart,
  CartPolicy,
  CatalogResponse,
  ChatResponse,
  CheckoutResponse,
  PaymentConfirmation,
  PaymentConfirmationResponse,
  RecoveryResponse,
  SearchResponse,
  Session,
  Upsell
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {})
      }
    }
  );

  const data =
    await response.json().catch(
      () => null
    );

  if (!response.ok) {
    const detail =
      data?.detail ||
      data?.message ||
      "Request failed";

    throw new Error(
      typeof detail === "string"
        ? detail
        : JSON.stringify(detail)
    );
  }

  return data as T;
}

export const api = {
  getCatalog: (params?: {
    category?: string;
    min_price?: number;
    max_price?: number;
    tag?: string;
    in_stock?: boolean;
  }) => {
    const searchParams =
      new URLSearchParams();

    if (params?.category) {
      searchParams.set(
        "category",
        params.category
      );
    }

    if (
      params?.min_price !== undefined
    ) {
      searchParams.set(
        "min_price",
        String(params.min_price)
      );
    }

    if (
      params?.max_price !== undefined
    ) {
      searchParams.set(
        "max_price",
        String(params.max_price)
      );
    }

    if (params?.tag) {
      searchParams.set(
        "tag",
        params.tag
      );
    }

    if (
      params?.in_stock !== undefined
    ) {
      searchParams.set(
        "in_stock",
        String(params.in_stock)
      );
    }

    const query =
      searchParams.toString();

    return request<CatalogResponse>(
      `/catalog${query ? `?${query}` : ""}`
    );
  },

  searchCatalog: (
    query: string
  ) =>
    request<SearchResponse>(
      `/catalog/search?q=${encodeURIComponent(
        query
      )}`
    ),

  getProduct: (
    productId: number
  ) =>
    request<
      import("./types").Product
    >(
      `/catalog/${productId}`
    ),

  createSession: (
    actorType:
      | "chat"
      | "bare_agent"
  ) =>
    request<Session>(
      "/sessions",
      {
        method: "POST",
        body: JSON.stringify({
          actor_type: actorType
        })
      }
    ),

  createCart: (
    sessionId: string
  ) =>
    request<Cart>(
      "/cart",
      {
        method: "POST",
        body: JSON.stringify({
          session_id:
            sessionId
        })
      }
    ),

  getCart: (
    cartId: string
  ) =>
    request<Cart>(
      `/cart/${cartId}`
    ),

  getCartPolicy: (
    cartId: string
  ) =>
    request<CartPolicy>(
      `/cart/${cartId}/policy`
    ),

  addCartItem: (
    cartId: string,
    productId: number,
    quantity: number
  ) =>
    request<{
      success: boolean;
      cart: Cart;
      policy: import("./types").Policy;
    }>(
      `/cart/${cartId}/items`,
      {
        method: "POST",
        body: JSON.stringify({
          product_id:
            productId,
          quantity
        })
      }
    ),

  approveCartItem: (
    cartId: string,
    productId: number,
    quantity: number
  ) =>
    request<{
      success: boolean;
      approved: boolean;
      cart: Cart;
      policy: import("./types").Policy;
    }>(
      `/cart/${cartId}/items/approve`,
      {
        method: "POST",
        body: JSON.stringify({
          product_id:
            productId,
          quantity
        })
      }
    ),

  updateCart: (
    cartId: string,
    productId: number,
    quantity: number
  ) =>
    request<Cart>(
      `/cart/${cartId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          product_id:
            productId,
          quantity
        })
      }
    ),

  createUpsell: (
    cartId: string
  ) =>
    request<Upsell>(
      `/cart/${cartId}/upsell`,
      {
        method: "POST"
      }
    ),

  acceptUpsell: (
    cartId: string,
    productId: number
  ) =>
    request<{
      success: boolean;
      cart: Cart;
      policy: import("./types").Policy;
    }>(
      `/cart/${cartId}/upsell/accept`,
      {
        method: "POST",
        body: JSON.stringify({
          product_id:
            productId
        })
      }
    ),

  declineUpsell: (
    cartId: string,
    productId: number
  ) =>
    request<{
      success: boolean;
      message: string;
      cart: Cart;
    }>(
      `/cart/${cartId}/upsell/decline`,
      {
        method: "POST",
        body: JSON.stringify({
          product_id:
            productId
        })
      }
    ),

  checkout: (
    cartId: string
  ) =>
    request<CheckoutResponse>(
      "/checkout",
      {
        method: "POST",
        body: JSON.stringify({
          cart_id:
            cartId
        })
      }
    ),

  confirmPayment: (
    payment: PaymentConfirmation
  ) =>
    request<PaymentConfirmationResponse>(
      "/checkout/confirm",
      {
        method: "POST",
        body: JSON.stringify(
          payment
        )
      }
    ),

  recoverCheckout: (
    cartId: string,
    originalProductId: number,
    substituteProductId: number
  ) =>
    request<RecoveryResponse>(
      "/checkout/recover",
      {
        method: "POST",
        body: JSON.stringify({
          cart_id:
            cartId,
          original_product_id:
            originalProductId,
          substitute_product_id:
            substituteProductId
        })
      }
    ),

  getAudit: (
    sessionId: string
  ) =>
    request<AuditResponse>(
      `/audit/session/${sessionId}`
    ),

  chat: (
    sessionId: string,
    cartId: string,
    message: string
  ) =>
    request<ChatResponse>(
      "/agent/chat",
      {
        method: "POST",
        body: JSON.stringify({
          session_id:
            sessionId,
          cart_id:
            cartId,
          message
        })
      }
    )
};