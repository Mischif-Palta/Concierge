"use client";

import { useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

type Log = {
  step: string;
  message: string;
};

export default function InteropRunner() {
  const [running, setRunning] =
    useState(false);

  const [logs, setLogs] =
    useState<Log[]>([]);

  const [result, setResult] =
    useState<any>(null);

  const [error, setError] =
    useState("");

  const run = async () => {
    setRunning(true);
    setLogs([]);
    setResult(null);
    setError("");

    try {
      const response =
        await fetch(
          `${API_URL}/interop/run`,
          {
            method: "POST"
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Independent agent execution failed"
        );
      }

      setLogs(
        data.logs || []
      );

      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Independent agent execution failed"
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <main className="app-shell interop-page">
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
          <a href="/">
            Commerce
          </a>

          <a
            href="/interop"
            className="active"
          >
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

      <section className="interop-hero">
        <div>
          <div className="eyebrow">
            <span className="pulse" />
            INDEPENDENT AGENT PROOF
          </div>

          <h1>
            One API.
            <br />
            <span>Any agent.</span>
          </h1>

          <p>
            This agent does not use Concierge's
            chat interface. It discovers the
            merchant API, creates its own session,
            builds a cart and reaches checkout
            independently.
          </p>

          <div className="interop-proof">
            <span>
              ✓ Published API contract
            </span>

            <span>
              ✓ No shared UI code
            </span>

            <span>
              ✓ Same governance layer
            </span>
          </div>
        </div>

        <div className="interop-orb">
          <div className="interop-orb-ring" />
          <div className="interop-orb-core">
            <span>↗</span>
          </div>

          <div className="orb-label">
            BARE AGENT
            <strong>
              API NATIVE
            </strong>
          </div>
        </div>
      </section>

      <section className="interop-workspace">
        <div className="terminal-panel">
          <div className="terminal-header">
            <div>
              <span className="terminal-dots">
                <i />
                <i />
                <i />
              </span>

              <strong>
                independent-agent
              </strong>
            </div>

            <span>
              POST /interop/run
            </span>
          </div>

          <div className="terminal-body">
            {logs.length === 0 &&
              !running &&
              !error && (
                <div className="terminal-idle">
                  <span>
                    $
                  </span>

                  <p>
                    Ready to execute an
                    independent commerce agent.
                  </p>

                  <small>
                    No Concierge UI calls are
                    involved.
                  </small>
                </div>
              )}

            {running && (
              <div className="terminal-running">
                <div className="loader" />

                <strong>
                  Agent executing...
                </strong>

                <span>
                  Reading merchant API
                  contract
                </span>
              </div>
            )}

            {logs.map(
              (log, index) => (
                <div
                  className="terminal-line"
                  key={index}
                >
                  <span className="terminal-step">
                    {String(
                      index + 1
                    ).padStart(
                      2,
                      "0"
                    )}
                  </span>

                  <span className="terminal-command">
                    {log.message}
                  </span>

                  <span className="terminal-check">
                    ✓
                  </span>
                </div>
              )
            )}

            {error && (
              <div className="terminal-error">
                <span>
                  ✕
                </span>

                {error}
              </div>
            )}
          </div>

          <div className="terminal-footer">
            <button
              className="run-agent-button"
              disabled={running}
              onClick={run}
            >
              {running
                ? "Agent running..."
                : "Run independent agent"}

              {!running && (
                <span>
                  →
                </span>
              )}
            </button>
          </div>
        </div>

        <aside className="interop-result-panel">
          <div className="result-panel-heading">
            <span>
              TRANSACTION
            </span>

            <i />
          </div>

          {result ? (
            <>
              <div className="interop-result-status">
                <span>
                  ✓
                </span>

                <div>
                  <strong>
                    Checkout reached
                  </strong>

                  <small>
                    Independent agent completed
                    the commerce flow.
                  </small>
                </div>
              </div>

              <div className="interop-result-data">
                <div>
                  <span>
                    PRODUCT
                  </span>

                  <strong>
                    {result.product?.name}
                  </strong>
                </div>

                <div>
                  <span>
                    AMOUNT
                  </span>

                  <strong>
                    ₹
                    {Number(
                      result.product?.price ??
                        0
                    ).toLocaleString(
                      "en-IN",
                      {
                        minimumFractionDigits: 2
                      }
                    )}
                  </strong>
                </div>

                <div>
                  <span>
                    STATUS
                  </span>

                  <strong>
                    {result.status}
                  </strong>
                </div>

                <div>
                  <span>
                    RAZORPAY ORDER
                  </span>

                  <strong>
                    {
                      result.order
                        ?.razorpay_order_id
                    }
                  </strong>
                </div>
              </div>
            </>
          ) : (
            <div className="result-empty">
              <div>
                ◌
              </div>

              <strong>
                No transaction yet
              </strong>

              <span>
                Run the agent to see a live
                transaction result.
              </span>
            </div>
          )}

          <div className="api-contract">
            <span>
              API CONTRACT
            </span>

            <strong>
              /docs
            </strong>

            <small>
              Agent-readable FastAPI
              specification
            </small>

            <a
              href={`${API_URL}/docs`}
              target="_blank"
              rel="noreferrer"
            >
              Open API docs →
            </a>
          </div>
        </aside>
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
          Independent agent interoperability
        </span>

        <a href="/">
          ← Back to Commerce
        </a>
      </footer>
    </main>
  );
}