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
  `INR ${n.toLocaleString("en-IN", {
    minimumFractionDigits: 2
  })}`;

function cleanMarkdown(
  text: string
) {
  return text
    .replace(/\\([*_`])/g, "$1")
    .replace(
      /\*\*(.*?)\*\*/g,
      "$1"
    )
    .replace(
      /__(.*?)__/g,
      "$1"
    )
    .replace(
      /`([^`]+)`/g,
      "$1"
    );
}

function renderInlineText(
  text: string
) {
  const cleaned =
    text.replace(
      /\\([*_`])/g,
      "$1"
    );

  const parts =
    cleaned.split(
      /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`)/
    );

  return parts.map(
    (part, index) => {
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

      if (
        part.startsWith("__") &&
        part.endsWith("__")
      ) {
        return (
          <strong key={index}>
            {part.slice(2, -2)}
          </strong>
        );
      }

      if (
        part.startsWith("`") &&
        part.endsWith("`")
      ) {
        return (
          <code key={index}>
            {part.slice(1, -1)}
          </code>
        );
      }

      return (
        <span key={index}>
          {cleanMarkdown(
            part
          )}
        </span>
      );
    }
  );
}

function renderMessage(
  text: string
) {
  const normalized =
    text
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .trim();

  const lines =
    normalized.split("\n");

  const rendered: React.ReactNode[] =
    [];

  let numberedItems: string[] =
    [];

  let bulletItems: string[] =
    [];

  const flushLists = () => {
    if (numberedItems.length) {
      rendered.push(
        <div
          className="message-list"
          key={`numbered-${rendered.length}`}
        >
          {numberedItems.map(
            (item, index) => (
              <div
                className="message-list-item"
                key={index}
              >
                <span className="message-number">
                  {index + 1}.
                </span>

                <span className="message-list-content">
                  {renderInlineText(
                    item
                  )}
                </span>
              </div>
            )
          )}
        </div>
      );

      numberedItems = [];
    }

    if (bulletItems.length) {
      rendered.push(
        <div
          className="message-list"
          key={`bullets-${rendered.length}`}
        >
          {bulletItems.map(
            (item, index) => (
              <div
                className="message-list-item"
                key={index}
              >
                <span className="message-number">
                  •
                </span>

                <span className="message-list-content">
                  {renderInlineText(
                    item
                  )}
                </span>
              </div>
            )
          )}
        </div>
      );

      bulletItems = [];
    }
  };

  lines.forEach(
    (line, index) => {
      const trimmed =
        line.trim();

      if (!trimmed) {
        flushLists();
        return;
      }

      const numberedMatch =
        trimmed.match(
          /^\d+\.\s*(.*)$/
        );

      if (numberedMatch) {
        numberedItems.push(
          numberedMatch[1]
        );
        return;
      }

      const bulletMatch =
        trimmed.match(
          /^[-*•]\s*(.*)$/
        );

      if (bulletMatch) {
        bulletItems.push(
          bulletMatch[1]
        );
        return;
      }

      flushLists();

      rendered.push(
        <div
          className="message-line"
          key={`line-${index}`}
        >
          {renderInlineText(
            trimmed
          )}
        </div>
      );
    }
  );

  flushLists();

  return (
    <div className="message-text">
      {rendered}
    </div>
  );
}

const formatAuditAction = (
  action: string
) =>
  action
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      char =>
        char.toUpperCase()
    );

const formatAuditDetails = (
  details:
    | Record<string, unknown>
    | null
    | undefined
) => {
  if (!details) {
    return "Commerce event recorded";
  }

  const entries =
    Object.entries(details);

  if (!entries.length) {
    return "Commerce event recorded";
  }

  return entries
    .map(
      ([key, value]) => {
        const label =
          key
            .replaceAll(
              "_",
              " "
            )
            .replace(
              /\b\w/g,
              char =>
                char.toUpperCase()
            );

        let formattedValue =
          "";

        if (
          typeof value ===
            "object" &&
          value !== null
        ) {
          formattedValue =
            JSON.stringify(
              value
            );
        } else {
          formattedValue =
            String(value);
        }

        return `${label}: ${formattedValue}`;
      }
    )
    .join(" | ");
};

const auditGate = (
  event: AuditEvent
) => {
  const details =
    event.details ?? {};

  const action =
    event.action.toLowerCase();

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
    action.includes(
      "blocked"
    ) ||
    action.includes(
      "failed"
    ) ||
    action.includes(
      "rejected"
    )
  ) {
    return "Blocked";
  }

  if (
    action.includes(
      "human_approval_granted"
    )
  ) {
    return "Allowed";
  }

  return "Allowed";
};

export default function ConciergeDashboard() {
  const [query, setQuery] =
    useState("");

  const [products, setProducts] =
    useState<Product[]>([]);

  const [session, setSession] =
    useState<Session | null>(
      null
    );

  const [cart, setCart] =
    useState<Cart | null>(
      null
    );

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
          "Hi - tell me what you're looking for and I'll pull some options from the catalog."
      }
    ]);

  const [audit, setAudit] =
    useState<AuditEvent[]>(
      []
    );

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

  const total =
    cart?.total ?? 0;

  const cap = 5000;

  const percent =
    Math.min(
      100,
      (total / cap) * 100
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

      setAudit(
        events
      );

      const approvalRequestIndex =
        events.reduce(
          (
            latestIndex,
            event,
            index
          ) => {
            const details =
              event.details ??
              {};

            const isApprovalRequest =
              event.action ===
                "policy_decision" &&
              details.policy_status ===
                "approval_required" &&
              details.requires_human_approval ===
                true &&
              typeof details.product_id ===
                "number";

            if (
              isApprovalRequest
            ) {
              return index;
            }

            return latestIndex;
          },
          -1
        );

      if (
        approvalRequestIndex ===
        -1
      ) {
        setPendingApproval(
          null
        );

        return;
      }

      const approvalRequest =
        events[
          approvalRequestIndex
        ];

      const requestDetails =
        approvalRequest.details ??
        {};

      const productId =
        Number(
          requestDetails.product_id
        );

      const cartId =
        String(
          requestDetails.cart_id ??
            ""
        );

      const approvalGranted =
        events
          .slice(
            approvalRequestIndex + 1
          )
          .some(event => {
            if (
              event.action !==
              "human_approval_granted"
            ) {
              return false;
            }

            const details =
              event.details ??
              {};

            const grantedProductId =
              Number(
                details.product_id
              );

            const grantedCartId =
              String(
                details.cart_id ??
                  ""
              );

            return (
              grantedProductId ===
                productId &&
              grantedCartId ===
                cartId
            );
          });

      if (
        approvalGranted
      ) {
        setPendingApproval(
          null
        );

        return;
      }

      const approvalRejected =
        events
          .slice(
            approvalRequestIndex + 1
          )
          .some(event => {
            if (
              event.action !==
              "human_approval_rejected"
            ) {
              return false;
            }

            const details =
              event.details ??
              {};

            const rejectedProductId =
              Number(
                details.product_id
              );

            const rejectedCartId =
              String(
                details.cart_id ??
                  ""
              );

            return (
              rejectedProductId ===
                productId &&
              rejectedCartId ===
                cartId
            );
          });

      if (
        approvalRejected
      ) {
        setPendingApproval(
          null
        );

        return;
      }

      setPendingApproval({
        productId:
          productId,
        productName:
          String(
            requestDetails.product_name ??
              "Requested product"
          ),
        quantity:
          Number(
            requestDetails.quantity ??
              1
          ),
        price:
          Number(
            requestDetails.product_price ??
              0
          ),
        reason:
          String(
            requestDetails.reason ??
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
        setLoading(
          true
        );

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
        if (!mounted) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Failed to initialize Concierge"
        );
      } finally {
        if (mounted) {
          setLoading(
            false
          );
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

    return () => {
      window.clearInterval(
        interval
      );
    };
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

    return () => {
      script.remove();
    };
  }, []);

  const search = async (
    value: string
  ) => {
    const trimmed =
      value.trim();

    if (
      !trimmed ||
      sending
    ) {
      return;
    }

    if (
      !session ||
      !cart
    ) {
      setMessages(
        items => [
          ...items,
          {
            who: "Concierge",
            text:
              "Your Concierge session is still initializing. Please try again."
          }
        ]
      );

      return;
    }

    setMessages(
      items => [
        ...items,
        {
          who: "You",
          text: trimmed
        }
      ]
    );

    setQuery("");

    setSending(
      true
    );

    try {
      const result =
        await api.chat(
          session.session_id,
          cart.cart_id,
          trimmed
        );

      setMessages(
        items => [
          ...items,
          {
            who: "Concierge",
            text:
              result.response
          }
        ]
      );

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

      if (
        result.checkout
      ) {
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
      setMessages(
        items => [
          ...items,
          {
            who: "Concierge",
            text:
              err instanceof Error
                ? err.message
                : "I couldn't process that request."
          }
        ]
      );

      await refreshAudit(
        session.session_id
      );
    } finally {
      setSending(
        false
      );
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

      if (
        result.success
      ) {
        setCart(
          result.cart
        );

        setMessages(
          items => [
            ...items,
            {
              who: "Concierge",
              text:
                `${product.name} was added to your cart.`
            }
          ]
        );
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
            result.policy
              .reason
        });

        setMessages(
          items => [
            ...items,
            {
              who: "Concierge",
              text:
                `${product.name} requires human approval before it can be added.`
            }
          ]
        );
      }

      if (session) {
        await refreshAudit(
          session.session_id
        );
      }
    } catch (err) {
      setMessages(
        items => [
          ...items,
          {
            who: "Concierge",
            text:
              err instanceof Error
                ? err.message
                : "I couldn't add that product to your cart."
          }
        ]
      );

      if (session) {
        await refreshAudit(
          session.session_id
        );
      }
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

        if (
          !result.success
        ) {
          throw new Error(
            result.policy
              ?.reason ||
              "Human approval could not be completed."
          );
        }

        setCart(
          result.cart
        );

        setPendingApproval(
          null
        );

        setMessages(
          items => [
            ...items,
            {
              who: "Concierge",
              text:
                `${approval.productName} was approved and added to your cart.`
            }
          ]
        );

        if (session) {
          await refreshAudit(
            session.session_id
          );
        }
      } catch (err) {
        setMessages(
          items => [
            ...items,
            {
              who: "Concierge",
              text:
                err instanceof Error
                  ? err.message
                  : "Human approval could not be completed."
            }
          ]
        );

        if (session) {
          await refreshAudit(
            session.session_id
          );
        }
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
        setMessages(
          items => [
            ...items,
            {
              who: "Concierge",
              text:
                "Your cart is empty - add something first."
            }
          ]
        );

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

        if (
          result.requires_human_approval ||
          !result.allowed
        ) {
          setMessages(
            items => [
              ...items,
              {
                who: "Concierge",
                text:
                  result.reason ||
                  "Checkout requires human approval and cannot proceed automatically."
              }
            ]
          );
        } else if (
          result.order
        ) {
          setMessages(
            items => [
              ...items,
              {
                who: "Concierge",
                text:
                  "Checkout is ready. Payment is pending."
              }
            ]
          );
        }

        if (session) {
          await refreshAudit(
            session.session_id
          );
        }
      } catch (err) {
        setCheckoutData(
          null
        );

        setMessages(
          items => [
            ...items,
            {
              who: "Concierge",
              text:
                err instanceof Error
                  ? err.message
                  : "I couldn't start checkout."
            }
          ]
        );

        setShowCheckout(
          false
        );

        if (session) {
          await refreshAudit(
            session.session_id
          );
        }
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
      !cart
    ) {
      return;
    }

    if (
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
        await new Promise<void>(
          resolve => {
            const started =
              Date.now();

            const interval =
              window.setInterval(
                () => {
                  if (
                    window.Razorpay ||
                    Date.now() -
                      started >
                      5000
                  ) {
                    window.clearInterval(
                      interval
                    );

                    resolve();
                  }
                },
                100
              );
          }
        );
      }

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

      const options:
        RazorpayOptions =
        {
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
                  await api.confirmPayment(
                    {
                      razorpay_order_id:
                        payment.razorpay_order_id,
                      razorpay_payment_id:
                        payment.razorpay_payment_id,
                      razorpay_signature:
                        payment.razorpay_signature
                    }
                  );

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

                  setMessages(
                    items => [
                      ...items,
                      {
                        who: "Concierge",
                        text:
                          `Payment confirmed. Your order has been completed in test mode.\nRazorpay Order: ${payment.razorpay_order_id}`
                      }
                    ]
                  );

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
                } else {
                  setMessages(
                    items => [
                      ...items,
                      {
                        who: "Concierge",
                        text:
                          confirmation.reason ||
                          "Payment could not be confirmed."
                      }
                    ]
                  );

                  await refreshAudit(
                    session.session_id
                  );
                }
              } catch (err) {
                setMessages(
                  items => [
                    ...items,
                    {
                      who: "Concierge",
                      text:
                        err instanceof Error
                          ? err.message
                          : "Payment confirmation failed."
                    }
                  ]
                );

                await refreshAudit(
                  session.session_id
                );
              } finally {
                setPaymentLoading(
                  false
                );
              }
            },
          modal: {
            ondismiss:
              () => {
                setPaymentLoading(
                  false
                );

                setMessages(
                  items => [
                    ...items,
                    {
                      who: "Concierge",
                      text:
                        "Payment was cancelled. The order was not finalized."
                    }
                  ]
                );
              }
          },
          theme: {
            color:
              "#6d5dfc"
          }
        };

      const razorpay =
        new window.Razorpay(
          options
        );

      razorpay.open();
    } catch (err) {
      setPaymentLoading(
        false
      );

      setMessages(
        items => [
          ...items,
          {
            who: "Concierge",
            text:
              err instanceof Error
                ? err.message
                : "I couldn't open Razorpay Checkout."
          }
        ]
      );

      await refreshAudit(
        session.session_id
      );
    }
  };

  const refreshCatalog =
    async () => {
      try {
        setError("");

        const catalog =
          await api.getCatalog();

        const shuffled =
          [
            ...catalog.products
          ].sort(
            () =>
              Math.random() -
              0.5
          );

        setProducts(
          shuffled
        );

        if (session) {
          await refreshAudit(
            session.session_id
          );
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to refresh catalog"
        );
      }
    };

  const checkoutBlocked =
    checkoutData
      ? !checkoutData.allowed ||
        checkoutData.requires_human_approval
      : false;

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">
            C
          </span>

          <span>
            Concierge
          </span>
        </div>

        <nav>
          <a href="/">
            Commerce
          </a>

          <a href="/interop">
            Interop
          </a>

          <span className="test">
            TEST MODE
          </span>
        </nav>
      </header>

      <section className="hero">
        <div>
          <div className="eyebrow">
            AGENTIC COMMERCE
          </div>

          <h1>
            Your AI shopping agent, with guardrails.
          </h1>

          <p>
            Concierge discovers products,
            reasons about purchases,
            keeps an audit trail,
            and completes transactions
            within merchant policy.
          </p>
        </div>

        <div className="hero-stat">
          <span>
            Autonomous limit
          </span>

          <strong>
            INR 5,000
          </strong>

          <small>
            Human approval above cap
          </small>
        </div>
      </section>

      <section className="commerce-bar">
        <div>
          <small>
            Cart
          </small>

          <strong>
            {cartItems.length}{" "}
            {cartItems.length ===
            1
              ? "item"
              : "items"}
          </strong>
        </div>

        <div>
          <small>
            Total
          </small>

          <strong>
            {money(total)}
          </strong>
        </div>

        <div className="track">
          <div className="track-bg">
            <div
              className="track-fill"
              style={{
                width: `${percent}%`
              }}
            />
          </div>

          <small>
            {money(total)} /{" "}
            {money(cap)}
          </small>
        </div>

        <span
          className={
            total > cap &&
            !humanApproved
              ? "policy wait"
              : "policy"
          }
        >
          {total > cap
            ? humanApproved
              ? "[OK] Human approved"
              : "[!] Approval required"
            : "[OK] Within limit"}
        </span>

        <button
          className="checkout"
          onClick={
            checkout
          }
          disabled={
            loading ||
            sending ||
            checkoutLoading
          }
        >
          {checkoutLoading
            ? "Checking..."
            : "Checkout"}
        </button>
      </section>

      <section className="grid">
        <div className="panel chat-panel">
          <div className="panel-head">
            <div>
              <h2>
                Shopping with Concierge
              </h2>

              <span>
                chat agent
              </span>
            </div>

            <span className="live">
              LIVE
            </span>
          </div>

          <div className="chat-body">
            {messages.map(
              (
                message,
                index
              ) => (
                <div
                  className={`message ${
                    message.who ===
                    "You"
                      ? "user"
                      : ""
                  }`}
                  key={index}
                >
                  <small>
                    {message.who}
                  </small>

                  <div>
                    {renderMessage(
                      message.text
                    )}
                  </div>
                </div>
              )
            )}
          </div>

          <div className="quick">
            <button
              disabled={
                sending
              }
              onClick={() =>
                search(
                  "tennis gear"
                )
              }
            >
              Tennis gear
            </button>

            <button
              disabled={
                sending
              }
              onClick={() =>
                search(
                  "running shoes"
                )
              }
            >
              Running shoes
            </button>
          </div>

          <div className="input-row">
            <input
              value={
                query
              }
              disabled={
                loading ||
                sending
              }
              onChange={event =>
                setQuery(
                  event.target
                    .value
                )
              }
              onKeyDown={event => {
                if (
                  event.key ===
                    "Enter" &&
                  !event.shiftKey
                ) {
                  event.preventDefault();

                  search(
                    query
                  );
                }
              }}
              placeholder={
                sending
                  ? "Concierge is thinking..."
                  : "Ask Concierge something..."
              }
            />

            <button
              disabled={
                loading ||
                sending ||
                !query.trim()
              }
              onClick={() =>
                search(
                  query
                )
              }
            >
              {sending
                ? "..."
                : "Send"}
            </button>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                Live audit trail
              </h2>

              <span>
                every action, explained
              </span>
            </div>
          </div>

          <div className="audit">
            {audit.length ===
            0 ? (
              <div className="audit-item">
                <i />

                <div>
                  <div className="audit-meta">
                    <span>
                      System
                    </span>

                    <em>
                      waiting
                    </em>
                  </div>

                  <strong>
                    Waiting for audit events
                  </strong>

                  <p>
                    Connecting to merchant audit log
                  </p>

                  <b>
                    [Pending]
                  </b>
                </div>
              </div>
            ) : (
              [
                ...audit
              ]
                .reverse()
                .map(
                  (
                    event,
                    index
                  ) => (
                    <div
                      className="audit-item"
                      key={
                        event.id ??
                        `${event.action}-${event.created_at}-${index}`
                      }
                    >
                      <i />

                      <div>
                        <div className="audit-meta">
                          <span>
                            Backend
                          </span>

                          <em>
                            {event.created_at
                              ? new Date(
                                  event.created_at
                                ).toLocaleTimeString(
                                  "en-IN",
                                  {
                                    hour:
                                      "2-digit",
                                    minute:
                                      "2-digit",
                                    second:
                                      "2-digit"
                                  }
                                )
                              : "now"}
                          </em>
                        </div>

                        <strong>
                          {formatAuditAction(
                            event.action
                          )}
                        </strong>

                        <p>
                          {formatAuditDetails(
                            event.details
                          )}
                        </p>

                        <b>
                          [
                          {
                            auditGate(
                              event
                            )
                          }
                          ]
                        </b>
                      </div>
                    </div>
                  )
                )
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                Browse catalog
              </h2>

              <span>
                {session
                  ? "merchant inventory"
                  : "connecting..."}
              </span>
            </div>

            <button
              className="shuffle"
              onClick={
                refreshCatalog
              }
            >
              Refresh
            </button>
          </div>

          {error && (
            <div className="product-body">
              <span>
                {error}
              </span>
            </div>
          )}

          <div className="catalog">
            {products.map(
              product => (
                <article
                  className="product"
                  key={
                    product.id
                  }
                >
                  <div className="product-art">
                    {product.image ? (
                      <img
                        src={
                          product.image
                        }
                        alt={
                          product.name
                        }
                        style={{
                          width:
                            "100%",
                          height:
                            "100%",
                          objectFit:
                            "contain"
                        }}
                      />
                    ) : (
                      product.category ===
                      "Tennis"
                        ? "TENNIS"
                        : "SPORT"
                    )}
                  </div>

                  <div className="product-body">
                    <small>
                      {
                        product.category
                      }
                    </small>

                    <h3>
                      {
                        product.name
                      }
                    </h3>

                    <strong>
                      {money(
                        product.price
                      )}
                    </strong>

                    <span>
                      {product.stock
                        ? `[OK] ${product.stock} in stock`
                        : "[X] Out of stock"}
                    </span>

                    <button
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
                    </button>
                  </div>
                </article>
              )
            )}
          </div>
        </div>
      </section>

      <footer>
        Independent-agent proof lives
        on{" "}
        <a href="/interop">
          /interop
        </a>{" "}
        - same backend, zero shared
        UI shortcuts.
      </footer>

      {pendingApproval && (
        <div className="approval-backdrop">
          <div className="approval-modal">
            <div className="approval-label">
              HUMAN APPROVAL REQUIRED
            </div>

            <h2>
              Approve this purchase?
            </h2>

            <p>
              Concierge cannot
              autonomously add this
              item because it exceeds
              the autonomous spending
              limit.
            </p>

            <div className="approval-product">
              <div>
                <strong>
                  {
                    pendingApproval.productName
                  }
                </strong>

                <span>
                  Quantity:{" "}
                  {
                    pendingApproval.quantity
                  }
                </span>
              </div>

              <strong>
                {money(
                  pendingApproval.price
                )}
              </strong>
            </div>

            <div className="approval-reason">
              {
                pendingApproval.reason
              }
            </div>

            <div className="modal-actions">
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
                  : "Approve Purchase"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showCheckout && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-top">
              <span>
                CHECKOUT
              </span>

              <b>
                Razorpay Test Mode
              </b>
            </div>

            <h2>
              Complete your order
            </h2>

            {checkoutLoading && (
              <div className="pay-box">
                Validating your cart and
                creating a secure Razorpay
                test order...
              </div>
            )}

            {!checkoutLoading &&
              checkoutData && (
                <>
                  {checkoutData.requires_human_approval && (
                    <div className="pay-box">
                      <strong>
                        Approval Required
                      </strong>

                      <br />

                      {
                        checkoutData.reason
                      }
                    </div>
                  )}

                  {!checkoutData.allowed &&
                    !checkoutData.requires_human_approval && (
                      <div className="pay-box">
                        <strong>
                          Checkout Blocked
                        </strong>

                        <br />

                        {
                          checkoutData.reason
                        }
                      </div>
                    )}

                  {checkoutData.order &&
                    checkoutData.allowed &&
                    !checkoutData.requires_human_approval && (
                      <>
                        <div className="summary">
                          <span>
                            {
                              checkoutData
                                .items
                                ?.length ??
                              cartItems.length
                            }{" "}
                            items
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

                        <div className="pay-box">
                          Razorpay Test
                          Mode
                          <br />
                          Order:{" "}
                          {
                            checkoutData
                              .order
                              .razorpay_order_id
                          }
                          <br />
                          Payment status:
                          pending
                        </div>
                      </>
                    )}
                </>
              )}

            {!checkoutLoading &&
              !checkoutData && (
                <div className="pay-box">
                  Checkout information is
                  unavailable.
                </div>
              )}

            <div className="modal-actions">
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
                onClick={
                  pay
                }
              >
                {paymentLoading
                  ? "Opening..."
                  : "Pay (test)"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}