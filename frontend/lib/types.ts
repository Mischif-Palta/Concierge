export type Product = {
  id: number;
  name: string;
  description?: string | null;
  price: number;
  category?: string | null;
  brand?: string | null;
  image?: string | null;
  thumbnail?: string | null;
  stock: number;
  in_stock: boolean;
  rating?: number | null;
  discount_percentage: number;
  tags: string[];
  pairs_with: number[];
  substitute_products: number[];
  agent_tags: string[];
  upsell_priority: number;
};

export type CatalogResponse = {
  products: Product[];
  count: number;
};

export type SearchResponse = {
  query: string;
  products: Product[];
  count: number;
};

export type Session = {
  session_id: string;
  actor_type:
    | "chat"
    | "bare_agent";
  status: string;
};

export type CartItem = {
  product_id: number;
  name: string;
  price: number;
  quantity: number;
  stock: number;
  image?: string | null;
  category?: string | null;
  item_total?: number;
};

export type Cart = {
  cart_id: string;
  session_id: string;
  items: CartItem[];
  item_count: number;
  subtotal: number;
  total: number;
  status: string;
};

export type Policy = {
  allowed: boolean;
  requires_human_approval: boolean;
  status: string;
  reason: string;
};

export type CartPolicy = {
  cart_id: string;
  session_id: string;
  current_cart_value: number;
  autonomous_limit: number;
  remaining_autonomous_budget: number;
  percentage_used: number;
  status: string;
};

export type Upsell = {
  success: boolean;
  suggested_item?: {
    id: number;
    name: string;
    price: number;
    image?: string | null;
    thumbnail?: string | null;
    stock: number;
  } | null;
  price_delta?: number;
  reasoning?: string;
  policy?: Policy;
  message?: string;
};

export type CheckoutOrder = {
  id: string;
  razorpay_order_id: string;
  amount: number;
  currency: string;
  status: string;
};

export type CheckoutResponse = {
  status: string;
  allowed: boolean;
  requires_human_approval: boolean;
  reason?: string;
  cart_id: string;
  session_id?: string;
  order?: CheckoutOrder;
  items?: CartItem[];
  cart_total?: number;
  autonomous_limit?: number;
  policy?: Policy;
  failure_type?: string;
  failed_product?: {
    id: number;
    name: string;
    price: number;
    image?: string | null;
    category?: string | null;
    requested_quantity: number;
    available_stock: number;
  };
  recovery_available?: boolean;
  substitute?: Substitute;
};

export type Substitute = {
  id: number;
  name: string;
  description?: string | null;
  price: number;
  stock: number;
  image?: string | null;
  category?: string | null;
};

export type RecoveryResponse = {
  status: string;
  success?: boolean;
  requires_human_approval?: boolean;
  reason?: string;
  cart_id: string;
  original_product_id?: number;
  substitute?: Substitute;
  quantity?: number;
  old_cart_total?: number;
  new_cart_total?: number;
  cart?: Cart;
  policy?: Policy;
};

export type PaymentConfirmation = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

export type PaymentConfirmationResponse = {
  status: string;
  already_processed: boolean;
  reason?: string;
  order?: CheckoutOrder & {
    razorpay_payment_id?: string;
  };
};

export type AuditEvent = {
  id?: string;
  session_id: string;
  action: string;
  details?: Record<string, unknown>;
  created_at?: string;
};

export type AuditResponse = {
  session_id: string;
  events: AuditEvent[];
  count: number;
};

export type ChatResponse = {
  session_id: string;
  cart_id: string;
  response: string;
  checkout: CheckoutOrder | null;
};