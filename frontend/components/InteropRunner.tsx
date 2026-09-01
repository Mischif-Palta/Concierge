"use client";

import { useState } from "react";

const lines = [
  ["Independent agent started", "muted"],
  ["GET /catalog?maxPrice=1000", "info"],
  ["200 OK — 4 products returned", "ok"],
  ["Selected: Performance Socks (₹399) — best fit under budget", "muted"],
  ["POST /cart", "info"],
  ["201 Created — cart created", "ok"],
  ["POST /cart/items", "info"],
  ["200 OK — cart total ₹399.00", "ok"],
  ["POST /checkout", "info"],
  ["200 OK — within autonomous limit, policy: allowed", "ok"],
  ["Razorpay test order created", "ok"],
  ["POST /checkout/confirm", "info"],
  ["200 OK — payment confirmed (test mode)", "ok"],
  ["Transaction complete — no chat UI involved", "muted"]
];

export default function InteropRunner() {
  const [running, setRunning] = useState(false);
  const [visible, setVisible] = useState(0);

  const run = () => {
    setRunning(true);
    setVisible(0);
    lines.forEach((_, i) => setTimeout(() => setVisible(i + 1), i * 250));
    setTimeout(() => setRunning(false), lines.length * 250 + 100);
  };

  return <main className="shell interop-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">C</span><span>Concierge</span></div><nav><a href="/">Commerce</a><a href="/interop">Interop</a><span className="test">● TEST MODE</span></nav></header>
    <section className="hero compact"><div><div className="eyebrow">INDEPENDENT AGENT PROOF</div><h1>Interoperability without shared UI code.</h1><p>A bare agent reads the published commerce contract and completes a purchase independently of the Concierge chat interface.</p></div></section>
    <section className="interop-card">
      <div className="panel-head"><div><h2>Bare agent runner</h2><span>API-driven transaction</span></div><button className="run" disabled={running} onClick={run}>{running ? "Running…" : "Run Independent Agent"}</button></div>
      <div className="terminal">{visible === 0 ? <div className="muted">// idle — press "Run Independent Agent" to start</div> : lines.slice(0, visible).map((l, i) => <div className={l[1]} key={i}>{l[0]}</div>)}</div>
      <div className="steps"><span className={visible >= 2 ? "active" : ""}>Catalog</span><span className={visible >= 5 ? "active" : ""}>Cart</span><span className={visible >= 9 ? "active" : ""}>Checkout</span><span className={visible >= 12 ? "active" : ""}>Payment</span></div>
    </section>
    <a className="back" href="/">← Back to commerce demo</a>
  </main>;
}