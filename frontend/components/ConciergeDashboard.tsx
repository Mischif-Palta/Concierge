"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type {
  AuditEvent,
  Cart,
  CheckoutResponse,
  Product,
  Session
} from "../lib/types";

declare global {
  interface Window {
    Razorpay?: new (
      options: RazorpayOptions
    ) => RazorpayInstance;
  }
}

type RazorpayOptions = {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  handler: (
    response: RazorpayPaymentResponse
  ) => void;
  modal?: {
    ondismiss?: () => void;
  };
  theme?: {
    color?: string;
  };
};

type RazorpayPaymentResponse = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

type RazorpayInstance = {
  open: () => void;
};

type PendingApproval = {
  productId: number;
  productName: string;
  quantity: number;
  price: number;
  reason: string;
};

const money = (n: number) =>
  `₹${n.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;

function renderMessage(text: string) {
  const normalized = text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .trim();

  const renderInline = (value: string) => {
    const parts = value.split(/(\*\*[^*]+\*\*)/g);

    return parts.map((part: string, index: number) => {
      if (
        part.startsWith("**") &&
        part.endsWith("**")
      ) {
        return (
          <strong key={index}>
            {part.slice(2, -2)}
          </strong>
        );
      }

      return <span key={index}>{part}</span>;
    });
  };

  const parts = normalized
    .split(/(?=\d+\.\s+)/)
    .map((part: string) => part.trim())
    .filter(Boolean);

  const numberedItems = parts.filter(part =>
    /^\d+\.\s+/.test(part)
  );

  if (numberedItems.length >= 2) {
    const firstNumberIndex = normalized.search(
      /\d+\.\s+/
    );

    const intro =
      firstNumberIndex > 0
        ? normalized
            .slice(0, firstNumberIndex)
            .trim()
        : "";

    return (
      <div className="message-text">
        {intro && (
          <div className="message-intro">
            {renderInline(intro)}
          </div>
        )}

        <div className="message-list">
          {numberedItems.map((item, index) => {
            const match = item.match(
              /^(\d+)\.\s+([\s\S]*)$/
            );

            if (!match) {
              return null;
            }

            return (
              <div
                className="message-list-item"
                key={index}
              >
                <span className="message-number">
                  {match[1]}.
                </span>

                <span className="message-list-content">
                  {renderInline(match[2])}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  const lines = normalized.split("\n");

  return (
    <div className="message-text">
      {lines.map((line, index) => (
        <div className="message-line" key={index}>
          {renderInline(line)}
        </div>
      ))}
    </div>
  );
}

function formatAuditAction(action: string) {
  return action
    .replaceAll("_", " ")
    .replace(/\b\w/g, char =>
      char.toUpperCase()
    );
}

function formatAuditDetails(
  details:
    | Record<string, unknown>
    | null
    | undefined
) {
  if (!details) {
    return "Commerce event recorded";
  }

  const entries =
    Object.entries(details);

  if (!entries.length) {
    return "Commerce event recorded";
  }

  return entries
    .map(([key, value]) => {
      const label =
        key
          .replaceAll("_", " ")
          .replace(
            /\b\w/g,
            char => char.toUpperCase()
          );

      const formatted =
        typeof value === "object" &&
        value !== null
          ? JSON.stringify(value)
          : String(value);

      return `${label}: ${formatted}`;
    })
    .join(" · ");
}

function auditGate(event: AuditEvent) {
  const details =
    event.details ?? {};

  if (
    details.requires_human_approval ===
      true ||
    details.policy_status ===
      "approval_required"
  ) {
    return "Approval Required";
  }

  if (
    details.allowed === false ||
    event.action
      .toLowerCase()
      .includes("failed") ||
    event.action
      .toLowerCase()
      .includes("blocked")
  ) {
    return "Blocked";
  }

  return "Allowed";
}

export default function ConciergeDashboard() {
  const [query, setQuery] =
    useState("");

  const [products, setProducts] =
    useState<Product[]>([]);

  const [session, setSession] =
    useState<Session | null>(null);

  const [cart, setCart] =
    useState<Cart | null>(null);

  const [messages, setMessages] =
    useState<
      {
        who: string;
        text: string;
      }[]
    >([
      {
        who: "Concierge",
        text:
          "Tell me what you're shopping for. I'll search the merchant catalog, evaluate the options and keep every purchase within policy."
      }
    ]);

  const [audit, setAudit] =
    useState<AuditEvent[]>([]);

  const [
    pendingApproval,
    setPendingApproval
  ] =
    useState<PendingApproval | null>(
      null
    );

  const [
    approvalLoading,
    setApprovalLoading
  ] =
    useState(false);

  const [
    showCheckout,
    setShowCheckout
  ] =
    useState(false);

  const [
    checkoutData,
    setCheckoutData
  ] =
    useState<CheckoutResponse | null>(
      null
    );

  const [
    checkoutLoading,
    setCheckoutLoading
  ] =
    useState(false);

  const [
    paymentLoading,
    setPaymentLoading
  ] =
    useState(false);

  const [
    loading,
    setLoading
  ] =
    useState(true);

  const [
    sending,
    setSending
  ] =
    useState(false);

  const [
    error,
    setError
  ] =
    useState("");

  const [
    compareIds,
    setCompareIds
  ] =
    useState<number[]>([]);

  const [
    showComparison,
    setShowComparison
  ] =
    useState(false);

  const total =
    cart?.total ?? 0;

  const autonomousLimit =
    5000;

  const usagePercent =
    Math.min(
      100,
      (total / autonomousLimit) *
        100
    );

  const cartItems =
    cart?.items ?? [];

  const cartProductIds =
    useMemo(
      () =>
        new Set(
          cartItems.map(
            item =>
              item.product_id
          )
        ),
      [cartItems]
    );

  const compareProducts =
    useMemo(
      () =>
        products.filter(
          product =>
            compareIds.includes(
              product.id
            )
        ),
      [products, compareIds]
    );

  const humanApproved =
    audit.some(event => {
      if (
        event.action !==
        "human_approval_granted"
      ) {
        return false;
      }

      const details =
        event.details ?? {};

      return (
        String(
          details.cart_id ?? ""
        ) ===
        String(
          cart?.cart_id ?? ""
        )
      );
    });

  const refreshAudit = async (
    sessionId: string
  ) => {
    try {
      const result =
        await api.getAudit(
          sessionId
        );

      const events =
        result.events;

      setAudit(events);

      const latestApproval =
        [...events]
          .reverse()
          .find(event => {
            const details =
              event.details ?? {};

            return (
              event.action ===
                "policy_decision" &&
              details.policy_status ===
                "approval_required" &&
              details.requires_human_approval ===
                true &&
              typeof details.product_id ===
                "number"
            );
          });

      if (!latestApproval) {
        setPendingApproval(
          null
        );
        return;
      }

      const details =
        latestApproval.details ??
        {};

      const requestIndex =
        events.indexOf(
          latestApproval
        );

      const resolved =
        events
          .slice(requestIndex + 1)
          .some(event => {
            if (
              event.action !==
                "human_approval_granted" &&
              event.action !==
                "human_approval_rejected"
            ) {
              return false;
            }

            const eventDetails =
              event.details ??
              {};

            return (
              Number(
                eventDetails.product_id
              ) ===
                Number(
                  details.product_id
                ) &&
              String(
                eventDetails.cart_id ??
                  ""
              ) ===
                String(
                  details.cart_id ??
                    ""
                )
            );
          });

      if (resolved) {
        setPendingApproval(
          null
        );
        return;
      }

      setPendingApproval({
        productId: Number(
          details.product_id
        ),
        productName: String(
          details.product_name ??
            "Requested product"
        ),
        quantity: Number(
          details.quantity ?? 1
        ),
        price: Number(
          details.product_price ?? 0
        ),
        reason: String(
          details.reason ??
            "This purchase requires human approval."
        )
      });
    } catch {
    }
  };

  useEffect(() => {
    let mounted = true;

    async function initialize() {
      try {
        setLoading(true);
        setError("");

        const createdSession =
          await api.createSession(
            "chat"
          );

        if (!mounted) {
          return;
        }

        setSession(
          createdSession
        );

        const createdCart =
          await api.createCart(
            createdSession.session_id
          );

        if (!mounted) {
          return;
        }

        setCart(
          createdCart
        );

        const catalog =
          await api.getCatalog();

        if (!mounted) {
          return;
        }

        setProducts(
          catalog.products
        );

        await refreshAudit(
          createdSession.session_id
        );
      } catch (err) {
        if (mounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to initialize Concierge"
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    initialize();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    refreshAudit(
      session.session_id
    );

    const interval =
      window.setInterval(
        () => {
          refreshAudit(
            session.session_id
          );
        },
        2000
      );

    return () =>
      window.clearInterval(
        interval
      );
  }, [session]);

  useEffect(() => {
    if (
      typeof window ===
        "undefined" ||
      window.Razorpay
    ) {
      return;
    }

    const script =
      document.createElement(
        "script"
      );

    script.src =
      "https://checkout.razorpay.com/v1/checkout.js";

    script.async = true;

    document.body.appendChild(
      script
    );

    return () =>
      script.remove();
  }, []);

  const search = async (
    value: string
  ) => {
    const trimmed =
      value.trim();

    if (
      !trimmed ||
      sending ||
      !session ||
      !cart
    ) {
      return;
    }

    setMessages(items => [
      ...items,
      {
        who: "You",
        text: trimmed
      }
    ]);

    setQuery("");
    setSending(true);

    try {
      const result =
        await api.chat(
          session.session_id,
          cart.cart_id,
          trimmed
        );

      setMessages(items => [
        ...items,
        {
          who: "Concierge",
          text:
            result.response
        }
      ]);

      const currentCartId =
        result.cart_id ||
        cart.cart_id;

      const updatedCart =
        await api.getCart(
          currentCartId
        );

      setCart(
        updatedCart
      );

      if (result.checkout) {
        setCheckoutData({
          status:
            "payment_pending",
          allowed: true,
          requires_human_approval:
            false,
          cart_id:
            currentCartId,
          session_id:
            session.session_id,
          order:
            result.checkout
        });

        setShowCheckout(
          true
        );
      }

      await refreshAudit(
        session.session_id
      );
    } catch (err) {
      setMessages(items => [
        ...items,
        {
          who: "Concierge",
          text:
            err instanceof Error
              ? err.message
              : "I couldn't process that request."
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  const addToCart = async (
    product: Product
  ) => {
    if (!cart) {
      return;
    }

    try {
      const result =
        await api.addCartItem(
          cart.cart_id,
          product.id,
          1
        );

      if (result.success) {
        setCart(
          result.cart
        );

        setMessages(items => [
          ...items,
          {
            who: "Concierge",
            text:
              `${product.name} is in your cart.`
          }
        ]);
      } else if (
        result.policy
          ?.requires_human_approval
      ) {
        setPendingApproval({
          productId:
            product.id,
          productName:
            product.name,
          quantity: 1,
          price:
            product.price,
          reason:
            result.policy.reason
        });
      }

      if (session) {
        await refreshAudit(
          session.session_id
        );
      }
    } catch (err) {
      setMessages(items => [
        ...items,
        {
          who: "Concierge",
          text:
            err instanceof Error
              ? err.message
              : "I couldn't add that product."
        }
      ]);
    }
  };

  const approvePurchase =
    async () => {
      if (
        !cart ||
        !pendingApproval ||
        approvalLoading
      ) {
        return;
      }

      setApprovalLoading(
        true
      );

      const approval =
        pendingApproval;

      try {
        const result =
          await api.approveCartItem(
            cart.cart_id,
            approval.productId,
            approval.quantity
          );

        if (!result.success) {
          throw new Error(
            result.policy?.reason ||
              "Approval failed."
          );
        }

        setCart(
          result.cart
        );

        setPendingApproval(
          null
        );

        setMessages(items => [
          ...items,
          {
            who: "Concierge",
            text:
              `${approval.productName} was approved and added to your cart.`
          }
        ]);

        if (session) {
          await refreshAudit(
            session.session_id
          );
        }
      } catch (err) {
        setMessages(items => [
          ...items,
          {
            who: "Concierge",
            text:
              err instanceof Error
                ? err.message
                : "Approval failed."
          }
        ]);
      } finally {
        setApprovalLoading(
          false
        );
      }
    };

  const checkout =
    async () => {
      if (
        !cart ||
        !cartItems.length
      ) {
        return;
      }

      setCheckoutLoading(
        true
      );

      setCheckoutData(
        null
      );

      setShowCheckout(
        true
      );

      try {
        const result =
          await api.checkout(
            cart.cart_id
          );

        setCheckoutData(
          result
        );

        if (session) {
          await refreshAudit(
            session.session_id
          );
        }
      } catch (err) {
        setShowCheckout(
          false
        );

        setMessages(items => [
          ...items,
          {
            who: "Concierge",
            text:
              err instanceof Error
                ? err.message
                : "Checkout failed."
          }
        ]);
      } finally {
        setCheckoutLoading(
          false
        );
      }
    };

  const pay = async () => {
    if (
      !checkoutData?.order ||
      !session ||
      !cart ||
      checkoutData.requires_human_approval ||
      !checkoutData.allowed
    ) {
      return;
    }

    setPaymentLoading(
      true
    );

    try {
      if (
        !window.Razorpay
      ) {
        throw new Error(
          "Razorpay Checkout could not be loaded."
        );
      }

      const key =
        process.env
          .NEXT_PUBLIC_RAZORPAY_KEY_ID;

      if (!key) {
        throw new Error(
          "Razorpay public key is not configured."
        );
      }

      const order =
        checkoutData.order;

      const razorpay =
        new window.Razorpay({
          key,
          amount:
            order.amount,
          currency:
            order.currency,
          name:
            "Concierge",
          description:
            "Concierge Commerce Test Payment",
          order_id:
            order.razorpay_order_id,
          handler:
            async payment => {
              try {
                const confirmation =
                  await api.confirmPayment({
                    razorpay_order_id:
                      payment.razorpay_order_id,
                    razorpay_payment_id:
                      payment.razorpay_payment_id,
                    razorpay_signature:
                      payment.razorpay_signature
                  });

                if (
                  confirmation.status ===
                  "paid"
                ) {
                  setShowCheckout(
                    false
                  );

                  setCheckoutData(
                    null
                  );

                  setMessages(items => [
                    ...items,
                    {
                      who: "Concierge",
                      text:
                        "Payment confirmed. Your order has been completed in test mode."
                    }
                  ]);

                  const updatedCart =
                    await api.getCart(
                      cart.cart_id
                    );

                  setCart(
                    updatedCart
                  );

                  await refreshAudit(
                    session.session_id
                  );
                }
              } catch (err) {
                setMessages(items => [
                  ...items,
                  {
                    who: "Concierge",
                    text:
                      err instanceof Error
                        ? err.message
                        : "Payment confirmation failed."
                  }
                ]);
              } finally {
                setPaymentLoading(
                  false
                );
              }
            },
          modal: {
            ondismiss: () =>
              setPaymentLoading(
                false
              )
          },
          theme: {
            color:
              "#7c3aed"
          }
        });

      razorpay.open();
    } catch (err) {
      setPaymentLoading(
        false
      );

      setMessages(items => [
        ...items,
        {
          who: "Concierge",
          text:
            err instanceof Error
              ? err.message
              : "Could not open payment."
        }
      ]);
    }
  };

  const refreshCatalog = async () => {
    try {
      const catalog = await api.getCatalog();

      const randomizedProducts = [...catalog.products].sort(
        () => Math.random() - 0.5
      );

      setProducts(randomizedProducts);

      setCompareIds([]);
      setShowComparison(false);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to refresh catalog"
      );
    }
  };

  const toggleCompare = (
    productId: number
  ) => {
    setCompareIds(current => {
      if (
        current.includes(
          productId
        )
      ) {
        return current.filter(
          id => id !== productId
        );
      }

      if (
        current.length >= 3
      ) {
        return current;
      }

      return [
        ...current,
        productId
      ];
    });
  };

  const checkoutBlocked =
    checkoutData
      ? !checkoutData.allowed ||
        checkoutData.requires_human_approval
      : false;

  return (
    <main className="app-shell">
      <header className="topbar">
        <a
          href="/"
          className="brand"
        >
          <span className="brand-mark">
            C
          </span>

          <span>
            Concierge
          </span>
        </a>

        <nav>
          <a
            className="active"
            href="/"
          >
            Commerce
          </a>

          <a href="/interop">
            Interop
          </a>

          <a href="/results">
            Results
          </a>

          <span className="test-badge">
            <i />
            TEST MODE
          </span>
        </nav>
      </header>

      <section className="hero-new">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="pulse" />
            AGENTIC COMMERCE
          </div>

          <h1>
            Shopping that thinks
            <span> before it buys.</span>
          </h1>

          <p>
            Concierge discovers products,
            evaluates options, respects
            merchant policy and completes
            purchases with a complete
            audit trail.
          </p>

          <div className="hero-actions">
            <button
              className="primary-button"
              onClick={() =>
                document
                  .getElementById(
                    "shopping"
                  )
                  ?.scrollIntoView({
                    behavior:
                      "smooth"
                  })
              }
            >
              Start shopping
              <span>→</span>
            </button>

            <a
              className="secondary-button"
              href="/interop"
            >
              See agent interoperability
            </a>
          </div>
        </div>

        <div className="agent-card">
          <div className="agent-card-top">
            <div>
              <span className="micro-label">
                CONCIERGE AGENT
              </span>

              <strong>
                {sending
                  ? "Thinking..."
                  : "Ready to shop"}
              </strong>
            </div>

            <span className="live-pill">
              <i />
              LIVE
            </span>
          </div>

          <div className="agent-orbit">
            <div className="orbit-ring ring-one" />
            <div className="orbit-ring ring-two" />
            <div className="agent-core">
              <span>✦</span>
            </div>
          </div>

          <div className="agent-status">
            <span>
              <i />
              Catalog connected
            </span>

            <span>
              <i />
              Policy engine active
            </span>

            <span>
              <i />
              Audit trail recording
            </span>
          </div>
        </div>
      </section>

      <section className="trust-strip">
        <div>
          <span>01</span>
          <strong>
            DISCOVER
          </strong>
          <small>
            Merchant catalog
          </small>
        </div>

        <div>
          <span>02</span>
          <strong>
            REASON
          </strong>
          <small>
            Agent decisions
          </small>
        </div>

        <div>
          <span>03</span>
          <strong>
            GOVERN
          </strong>
          <small>
            Merchant policy
          </small>
        </div>

        <div>
          <span>04</span>
          <strong>
            TRANSACT
          </strong>
          <small>
            Razorpay test mode
          </small>
        </div>
      </section>

      <section
        id="shopping"
        className="workspace"
      >
        <div className="workspace-heading">
          <div>
            <span className="section-kicker">
              THE AGENT WORKSPACE
            </span>

            <h2>
              Shop through conversation.
            </h2>
          </div>

          <div className="workspace-meta">
            <span>
              SESSION
            </span>

            <strong>
              {session
                ? "CONNECTED"
                : "CONNECTING"}
            </strong>
          </div>
        </div>

        <div className="workspace-grid">
          <section className="chat-panel-new panel-new">
            <div className="panel-header-new">
              <div>
                <span className="panel-icon">
                  ✦
                </span>

                <div>
                  <strong>
                    Concierge
                  </strong>

                  <small>
                    AI shopping agent
                  </small>
                </div>
              </div>

              <span className="status-dot">
                {sending
                  ? "PROCESSING"
                  : "ONLINE"}
              </span>
            </div>

            <div className="chat-feed">
              {messages.map(
                (message, index) => (
                  <div
                    className={`chat-message ${
                      message.who ===
                      "You"
                        ? "from-user"
                        : "from-agent"
                    }`}
                    key={index}
                  >
                    <div className="message-label">
                      {message.who ===
                      "You"
                        ? "YOU"
                        : "CONCIERGE"}
                    </div>

                    <div className="message-bubble">
                      {renderMessage(
                        message.text
                      )}
                    </div>
                  </div>
                )
              )}

              {sending && (
                <div className="thinking">
                  <span />
                  <span />
                  <span />
                  Concierge is evaluating
                  your request
                </div>
              )}
            </div>

            <div className="suggestion-row">
              <button
                onClick={() =>
                  search(
                    "Find me tennis gear under ₹2000"
                  )
                }
              >
                Tennis gear
              </button>

              <button
                onClick={() =>
                  search(
                    "Show me running shoes"
                  )
                }
              >
                Running shoes
              </button>

              <button
                onClick={() =>
                  search(
                    "Find something under ₹1000"
                  )
                }
              >
                Under ₹1,000
              </button>
            </div>

            <div className="chat-input-new">
              <input
                value={query}
                disabled={
                  loading ||
                  sending
                }
                onChange={event =>
                  setQuery(
                    event.target.value
                  )
                }
                onKeyDown={event => {
                  if (
                    event.key ===
                      "Enter" &&
                    !event.shiftKey
                  ) {
                    event.preventDefault();
                    search(query);
                  }
                }}
                placeholder={
                  loading
                    ? "Connecting to merchant..."
                    : "What are you looking for?"
                }
              />

              <button
                disabled={
                  loading ||
                  sending ||
                  !query.trim()
                }
                onClick={() =>
                  search(query)
                }
              >
                →
              </button>
            </div>
          </section>

          <aside className="governance-panel panel-new">
            <div className="panel-header-new">
              <div>
                <span className="panel-icon shield">
                  ✓
                </span>

                <div>
                  <strong>
                    Policy Engine
                  </strong>

                  <small>
                    Autonomous governance
                  </small>
                </div>
              </div>

              <span className="status-dot">
                ACTIVE
              </span>
            </div>

            <div className="limit-block">
              <div className="limit-heading">
                <span>
                  AUTONOMOUS SPEND
                </span>

                <strong>
                  {money(total)}
                </strong>
              </div>

              <div className="limit-track">
                <div
                  style={{
                    width: `${usagePercent}%`
                  }}
                />
              </div>

              <div className="limit-foot">
                <span>
                  ₹0
                </span>

                <span>
                  ₹5,000 limit
                </span>
              </div>
            </div>

            <div className="governance-checks">
              <div>
                <span className="check">
                  ✓
                </span>

                <div>
                  <strong>
                    Purchase policy
                  </strong>

                  <small>
                    Actions evaluated before execution
                  </small>
                </div>
              </div>

              <div>
                <span className="check">
                  ✓
                </span>

                <div>
                  <strong>
                    Inventory validation
                  </strong>

                  <small>
                    Stock verified at checkout
                  </small>
                </div>
              </div>

              <div>
                <span className="check">
                  ✓
                </span>

                <div>
                  <strong>
                    Human escalation
                  </strong>

                  <small>
                    Required above ₹5,000
                  </small>
                </div>
              </div>
            </div>

            <div
              className={`governance-state ${
                total > autonomousLimit &&
                !humanApproved
                  ? "warning"
                  : ""
              }`}
            >
              <span>
                {total >
                  autonomousLimit &&
                !humanApproved
                  ? "!"
                  : "✓"}
              </span>

              <div>
                <strong>
                  {total >
                    autonomousLimit &&
                  !humanApproved
                    ? "Human approval required"
                    : "Within autonomous policy"}
                </strong>

                <small>
                  {total >
                    autonomousLimit &&
                  !humanApproved
                    ? "The agent cannot continue without authorization."
                    : "Concierge can continue autonomously."}
                </small>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="catalog-section">
        <div className="section-heading-row">
          <div>
            <span className="section-kicker">
              MERCHANT INVENTORY
            </span>

            <h2>
              Browse the catalog.
            </h2>
          </div>

          <button
            className="refresh-button"
            onClick={
              refreshCatalog
            }
          >
            ↻ Refresh catalog
          </button>
        </div>

        {compareIds.length > 0 && (
          <div className="compare-toolbar">
            <div>
              <span className="compare-count">
                {compareIds.length}
              </span>

              <span>
                products selected
              </span>
            </div>

            <div>
              <button
                disabled={
                  compareIds.length <
                  2
                }
                onClick={() =>
                  setShowComparison(
                    true
                  )
                }
              >
                Compare options
              </button>

              <button
                onClick={() => {
                  setCompareIds([]);
                  setShowComparison(
                    false
                  );
                }}
              >
                Clear
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <div className="product-grid">
          {products.map(product => (
            <article
              className="product-card-new"
              key={product.id}
            >
              <div className="product-image-new">
                <div className="product-category">
                  {product.category}
                </div>

                {product.image ? (
                  <img
                    src={
                      product.image
                    }
                    alt={
                      product.name
                    }
                  />
                ) : (
                  <div className="image-placeholder">
                    PRODUCT
                  </div>
                )}

                {product.discount_percentage >
                  0 && (
                  <span className="discount-badge">
                    -
                    {product.discount_percentage.toFixed(
                      0
                    )}
                    %
                  </span>
                )}

                {compareIds.includes(
                  product.id
                ) && (
                  <span className="selected-badge">
                    ✓ COMPARE
                  </span>
                )}
              </div>

              <div className="product-info-new">
                <div className="product-rating">
                  ★{" "}
                  {(product.rating ?? 0).toFixed(
                    1
                  )}

                  <span>
                    · {product.stock} in stock
                  </span>
                </div>

                <h3>
                  {product.name}
                </h3>

                <div className="product-price-row">
                  <strong>
                    {money(
                      product.price
                    )}
                  </strong>

                  <span>
                    ID #{product.id}
                  </span>
                </div>

                <button
                  className="add-button"
                  disabled={
                    !product.stock ||
                    sending
                  }
                  onClick={() =>
                    addToCart(
                      product
                    )
                  }
                >
                  {cartProductIds.has(
                    product.id
                  )
                    ? "Add another"
                    : "Add to cart"}

                  <span>
                    +
                  </span>
                </button>

                <button
                  className={`compare-button ${
                    compareIds.includes(
                      product.id
                    )
                      ? "selected"
                      : ""
                  }`}
                  disabled={
                    !product.stock ||
                    (compareIds.length >=
                      3 &&
                      !compareIds.includes(
                        product.id
                      ))
                  }
                  onClick={() =>
                    toggleCompare(
                      product.id
                    )
                  }
                >
                  {compareIds.includes(
                    product.id
                  )
                    ? "✓ Selected for comparison"
                    : "Compare product"}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="audit-section">
        <div className="section-heading-row">
          <div>
            <span className="section-kicker">
              TRANSPARENCY LAYER
            </span>

            <h2>
              Every decision leaves a trace.
            </h2>
          </div>

          <span className="audit-live">
            ● LIVE AUDIT
          </span>
        </div>

        <div className="audit-timeline">
          {audit.length === 0 ? (
            <div className="audit-empty">
              Waiting for commerce events...
            </div>
          ) : (
            [...audit]
              .reverse()
              .slice(0, 8)
              .map(
                (
                  event,
                  index
                ) => (
                  <div
                    className="audit-event"
                    key={
                      event.id ??
                      `${event.action}-${index}`
                    }
                  >
                    <div className="audit-node">
                      <i />
                    </div>

                    <div className="audit-event-main">
                      <div>
                        <strong>
                          {formatAuditAction(
                            event.action
                          )}
                        </strong>

                        <span>
                          {event.created_at
                            ? new Date(
                                event.created_at
                              ).toLocaleTimeString(
                                "en-IN",
                                {
                                  hour:
                                    "2-digit",
                                  minute:
                                    "2-digit"
                                }
                              )
                            : "now"}
                        </span>
                      </div>

                      <p>
                        {formatAuditDetails(
                          event.details
                        )}
                      </p>
                    </div>

                    <span
                      className={`audit-status ${
                        auditGate(
                          event
                        ) ===
                        "Approval Required"
                          ? "approval"
                          : auditGate(
                              event
                            ) ===
                            "Blocked"
                          ? "blocked"
                          : ""
                      }`}
                    >
                      {auditGate(
                        event
                      )}
                    </span>
                  </div>
                )
              )
          )}
        </div>
      </section>

      <footer className="site-footer">
        <div>
          <span className="footer-logo">
            C
          </span>

          <strong>
            Concierge
          </strong>
        </div>

        <span>
          Governed agentic commerce
        </span>

        <div>
          <a href="/interop">
            Independent agent →
          </a>

          <a href="/results">
            Revenue evidence →
          </a>
        </div>
      </footer>

      {showComparison && (
        <div className="overlay">
          <div className="modal-new comparison-modal-new">
            <div className="modal-heading-new">
              <div>
                <span>
                  PRODUCT INTELLIGENCE
                </span>

                <h2>
                  Compare your options.
                </h2>
              </div>

              <button
                className="close-button"
                onClick={() =>
                  setShowComparison(
                    false
                  )
                }
              >
                ×
              </button>
            </div>

            <div className="comparison-grid-new">
              {compareProducts.map(
                product => (
                  <div
                    className="comparison-card-new"
                    key={
                      product.id
                    }
                  >
                    <div className="comparison-image-new">
                      {product.image && (
                        <img
                          src={
                            product.image
                          }
                          alt={
                            product.name
                          }
                        />
                      )}
                    </div>

                    <span>
                      {product.category}
                    </span>

                    <h3>
                      {product.name}
                    </h3>

                    <strong>
                      {money(
                        product.price
                      )}
                    </strong>

                    <div className="comparison-stat">
                      <span>
                        Rating
                      </span>

                      <b>
                        ★{" "}
                        {(product.rating ?? 0).toFixed(
                          1
                        )}
                      </b>
                    </div>

                    <div className="comparison-stat">
                      <span>
                        Stock
                      </span>

                      <b>
                        {product.stock}
                      </b>
                    </div>

                    <div className="comparison-stat">
                      <span>
                        Discount
                      </span>

                      <b>
                        {product.discount_percentage.toFixed(
                          0
                        )}
                        %
                      </b>
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      )}

      {pendingApproval && (
        <div className="overlay">
          <div className="modal-new approval-modal-new">
            <div className="approval-icon">
              !
            </div>

            <span className="modal-kicker">
              GOVERNANCE CHECK
            </span>

            <h2>
              Human approval required.
            </h2>

            <p>
              This purchase exceeds the
              agent's autonomous spending
              limit. Concierge has stopped
              before executing the action.
            </p>

            <div className="approval-order">
              <div>
                <span>
                  PRODUCT
                </span>

                <strong>
                  {
                    pendingApproval.productName
                  }
                </strong>
              </div>

              <div>
                <span>
                  AMOUNT
                </span>

                <strong>
                  {money(
                    pendingApproval.price
                  )}
                </strong>
              </div>
            </div>

            <div className="approval-reason-new">
              {pendingApproval.reason}
            </div>

            <div className="modal-actions-new">
              <button
                disabled={
                  approvalLoading
                }
                onClick={() =>
                  setPendingApproval(
                    null
                  )
                }
              >
                Decline
              </button>

              <button
                disabled={
                  approvalLoading
                }
                onClick={
                  approvePurchase
                }
              >
                {approvalLoading
                  ? "Approving..."
                  : "Approve purchase"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showCheckout && (
        <div className="overlay">
          <div className="modal-new checkout-modal-new">
            <div className="modal-heading-new">
              <div>
                <span>
                  SECURE CHECKOUT
                </span>

                <h2>
                  Complete your order.
                </h2>
              </div>

              <button
                className="close-button"
                onClick={() => {
                  setShowCheckout(
                    false
                  );
                  setCheckoutData(
                    null
                  );
                }}
              >
                ×
              </button>
            </div>

            {checkoutLoading && (
              <div className="checkout-state">
                <div className="loader" />
                <strong>
                  Validating your cart
                </strong>

                <span>
                  Checking stock, pricing and merchant policy...
                </span>
              </div>
            )}

            {!checkoutLoading &&
              checkoutData && (
                <>
                  {checkoutData.requires_human_approval && (
                    <div className="checkout-warning">
                      <strong>
                        Approval required
                      </strong>

                      <span>
                        {
                          checkoutData.reason
                        }
                      </span>
                    </div>
                  )}

                  {checkoutData.order &&
                    checkoutData.allowed &&
                    !checkoutData.requires_human_approval && (
                      <div className="checkout-order">
                        <div>
                          <span>
                            ORDER
                          </span>

                          <strong>
                            {
                              checkoutData
                                .order
                                .razorpay_order_id
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            TOTAL
                          </span>

                          <strong>
                            {money(
                              checkoutData
                                .order
                                .amount /
                                100
                            )}
                          </strong>
                        </div>

                        <div className="test-payment">
                          <span>
                            RAZORPAY
                          </span>

                          <strong>
                            TEST MODE
                          </strong>
                        </div>
                      </div>
                    )}
                </>
              )}

            <div className="modal-actions-new">
              <button
                disabled={
                  paymentLoading
                }
                onClick={() => {
                  setShowCheckout(
                    false
                  );
                  setCheckoutData(
                    null
                  );
                }}
              >
                Cancel
              </button>

              <button
                disabled={
                  checkoutLoading ||
                  paymentLoading ||
                  checkoutBlocked ||
                  !checkoutData?.order
                }
                onClick={pay}
              >
                {paymentLoading
                  ? "Opening Razorpay..."
                  : "Pay securely →"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}