"use client";

import { useEffect, useState } from "react";

type RevenueResults = {
  simulation: boolean;
  seed: number;
  sessions: {
    baseline: number;
    agent_assisted: number;
  };
  baseline: {
    orders: number[];
    aov: number;
  };
  agent_assisted: {
    orders: number[];
    aov: number;
  };
  aov_lift_percentage: number;
};

const money = (n: number) =>
  `₹${n.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;

export default function Results() {
  const [results, setResults] =
    useState<RevenueResults | null>(null);

  const [error, setError] =
    useState("");

  useEffect(() => {
    async function loadResults() {
      try {
        const response =
          await fetch("/revenue_results.json");

        if (!response.ok) {
          throw new Error(
            "Failed to load simulation results."
          );
        }

        const data =
          (await response.json()) as RevenueResults;

        setResults(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load simulation results."
        );
      }
    }

    loadResults();
  }, []);

  if (error) {
    return (
      <main className="app-shell results-page">
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

            <a href="/interop">
              Interop
            </a>

            <a
              href="/results"
              className="active"
            >
              Results
            </a>

            <span className="test-badge">
              <i />
              TEST MODE
            </span>
          </nav>
        </header>

        <section className="results-main">
          <div className="synthetic-warning">
            <div className="warning-symbol">
              !
            </div>

            <div>
              <strong>
                Unable to load simulation
              </strong>

              <p>
                {error}
              </p>
            </div>
          </div>
        </section>
      </main>
    );
  }

  if (!results) {
    return (
      <main className="app-shell results-page">
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

            <a href="/interop">
              Interop
            </a>

            <a
              href="/results"
              className="active"
            >
              Results
            </a>

            <span className="test-badge">
              <i />
              TEST MODE
            </span>
          </nav>
        </header>

        <section className="results-main">
          <div className="synthetic-warning">
            <div className="warning-symbol">
              …
            </div>

            <div>
              <strong>
                Loading simulation results
              </strong>

              <p>
                Reading the reproducible revenue experiment.
              </p>
            </div>
          </div>
        </section>
      </main>
    );
  }

  const baselineAov =
    results.baseline.aov;

  const agentAov =
    results.agent_assisted.aov;

  const aovLift =
    results.aov_lift_percentage;

  const maxAov =
    Math.max(
      baselineAov,
      agentAov
    );

  const baselineWidth =
    maxAov > 0
      ? (baselineAov / maxAov) * 100
      : 0;

  const agentWidth =
    maxAov > 0
      ? (agentAov / maxAov) * 100
      : 0;

  const liftWidth =
    Math.min(
      100,
      (aovLift / 200) * 100
    );

  const totalSessions =
    results.sessions.baseline +
    results.sessions.agent_assisted;

  return (
    <main className="app-shell results-page">
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

          <a href="/interop">
            Interop
          </a>

          <a
            href="/results"
            className="active"
          >
            Results
          </a>

          <span className="test-badge">
            <i />
            TEST MODE
          </span>
        </nav>
      </header>

      <section className="results-hero">
        <div>
          <div className="eyebrow">
            <span className="pulse" />
            SYNTHETIC REVENUE EVIDENCE
          </div>

          <h1>
            What happens when
            <br />
            <span>agents start selling?</span>
          </h1>

          <p>
            A reproducible simulation comparing
            conventional shopping sessions with
            agent-assisted commerce.
          </p>
        </div>

        <div className="simulation-badge">
          <span>
            SIMULATION
          </span>

          <strong>
            SEED {results.seed}
          </strong>

          <small>
            {totalSessions} synthetic sessions
          </small>
        </div>
      </section>

      <section className="results-main">
        <div className="results-label">
          <span>
            AOV COMPARISON
          </span>

          <small>
            {results.sessions.baseline} baseline ·{" "}
            {results.sessions.agent_assisted} agent-assisted
          </small>
        </div>

        <div className="aov-display">
          <div className="metric-row baseline">
            <div className="metric-info">
              <span>
                BASELINE
              </span>

              <strong>
                {money(baselineAov)}
              </strong>

              <small>
                {results.sessions.baseline} conventional sessions
              </small>
            </div>

            <div className="metric-track">
              <div
                className="metric-fill"
                style={{
                  width: `${baselineWidth}%`
                }}
              >
                <span>
                  {money(baselineAov)}
                </span>
              </div>
            </div>
          </div>

          <div className="metric-row assisted">
            <div className="metric-info">
              <span>
                AGENT-ASSISTED
              </span>

              <strong>
                {money(agentAov)}
              </strong>

              <small>
                {results.sessions.agent_assisted} agent-assisted sessions
              </small>
            </div>

            <div className="metric-track">
              <div
                className="metric-fill"
                style={{
                  width: `${agentWidth}%`
                }}
              >
                <span>
                  {money(agentAov)}
                </span>
              </div>
            </div>
          </div>

          <div className="metric-row lift">
            <div className="metric-info">
              <span>
                AOV LIFT
              </span>

              <strong>
                +{aovLift.toFixed(2)}%
              </strong>

              <small>
                Agent-assisted vs baseline
              </small>
            </div>

            <div className="metric-track">
              <div
                className="metric-fill"
                style={{
                  width: `${liftWidth}%`
                }}
              >
                <span>
                  +{aovLift.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="evidence-grid">
          <div>
            <span>
              EXPERIMENT
            </span>

            <strong>
              {totalSessions} sessions
            </strong>

            <small>
              Equal split between groups
            </small>
          </div>

          <div>
            <span>
              RANDOM SEED
            </span>

            <strong>
              {results.seed}
            </strong>

            <small>
              Reproducible simulation
            </small>
          </div>

          <div>
            <span>
              MEASURE
            </span>

            <strong>
              AOV
            </strong>

            <small>
              Average order value
            </small>
          </div>
        </div>

        <div className="synthetic-warning">
          <div className="warning-symbol">
            !
          </div>

          <div>
            <strong>
              Synthetic simulation
            </strong>

            <p>
              These figures are simulated and
              are not production revenue. The
              experiment uses a fixed random seed
              so the result is reproducible.
            </p>
          </div>
        </div>
      </section>

      <section className="results-story">
        <div>
          <span className="section-kicker">
            THE BUILDATHON THESIS
          </span>

          <h2>
            The agent isn't just a chatbot.
            <br />
            <span>
              It's a commerce operator.
            </span>
          </h2>
        </div>

        <div className="thesis-points">
          <div>
            <span>
              01
            </span>

            <strong>
              Discover
            </strong>

            <p>
              Reads the merchant catalog
              dynamically.
            </p>
          </div>

          <div>
            <span>
              02
            </span>

            <strong>
              Reason
            </strong>

            <p>
              Evaluates products and
              recommendations.
            </p>
          </div>

          <div>
            <span>
              03
            </span>

            <strong>
              Govern
            </strong>

            <p>
              Enforces autonomous spending
              boundaries.
            </p>
          </div>

          <div>
            <span>
              04
            </span>

            <strong>
              Transact
            </strong>

            <p>
              Uses the same commerce API to
              reach payment.
            </p>
          </div>
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
          Synthetic evidence · not production revenue
        </span>

        <div>
          <a href="/">
            Commerce →
          </a>

          <a href="/interop">
            Interop →
          </a>
        </div>
      </footer>
    </main>
  );
}