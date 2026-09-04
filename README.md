# Concierge — Agentic Commerce

> **An AI shopping agent that can discover, reason, govern, and transact.**

Concierge is an agentic commerce system built for the **Razorpay Buildathon**.

Instead of acting like a traditional chatbot that only recommends products, Concierge can operate across the complete commerce lifecycle:

**Discover → Reason → Govern → Transact**

The agent can read a merchant catalog, search and recommend products, create sessions and carts, enforce autonomous spending policies, request human approval when required, create Razorpay test orders, complete test-mode payments, recover from unavailable products, maintain an auditable decision trail, and expose the same commerce API to independent agents.

---

## Demo

**Frontend:** https://concierge-commerce.vercel.app

**Backend API:** https://concierge-ndyg.onrender.com

**API Docs:** https://concierge-ndyg.onrender.com/docs

---

## What Concierge Demonstrates

Concierge is designed to prove that an AI agent can operate as a **commerce operator**, not just a conversational interface.

### 1. Discover

The agent dynamically reads the merchant catalog.

It can:

- Browse products
- Search products
- Filter by category
- Filter by price
- Filter by tags
- Check inventory
- Retrieve individual products

### 2. Reason

The agent uses product information and user intent to make commerce decisions.

It can:

- Understand natural-language shopping requests
- Recommend relevant products
- Suggest complementary products
- Find substitutes
- Perform governed upsells

### 3. Govern

Every commerce action passes through the policy layer.

The system can:

- Enforce an autonomous spending limit
- Validate inventory
- Stop purchases requiring human approval
- Record policy decisions
- Record human approvals
- Maintain a live audit trail

### 4. Transact

The agent can progress from a shopping conversation to payment.

The flow includes:

- Cart creation
- Cart item management
- Checkout
- Razorpay Test Mode order creation
- Payment confirmation
- Checkout recovery
- Payment audit events

---

# Architecture

```text
                    +--------------------------+
                    |      User / Agent        |
                    +--------------------------+
                                 |
                                 v
                    +--------------------------+
                    |      Next.js Frontend    |
                    |                          |
                    |  Concierge Chat          |
                    |  Policy Engine UI        |
                    |  Interop Runner          |
                    |  Revenue Simulation      |
                    +--------------------------+
                                 |
                                 v
                    +--------------------------+
                    |       FastAPI API        |
                    |                          |
                    |  Catalog                 |
                    |  Sessions                |
                    |  Cart                    |
                    |  Agent                   |
                    |  Upsell                  |
                    |  Policy                  |
                    |  Checkout                |
                    |  Audit                   |
                    |  Interoperability        |
                    +--------------------------+
                            |          |
                  +---------+          +----------+
                  |                               |
        +------------------+            +------------------+
        |   Groq / LLM     |            | Razorpay Test    |
        |   Agent Reasoning|            | Mode             |
        +------------------+            +------------------+
```

---

# Core Features

## AI Shopping Agent

The main Concierge interface lets a user shop through conversation.

Example:

```text
User:
I need something for working out under ₹5,000.

Concierge:
Here are products that match your budget and use case...
```

The agent can then continue the interaction into cart creation and checkout.

---

## Dynamic Catalog

The backend exposes a merchant-readable catalog API.

Supported catalog operations include:

```text
GET /catalog
GET /catalog/search?q=...
GET /catalog/{product_id}
```

Catalog products contain information such as:

- Product ID
- Name
- Description
- Price
- Category
- Brand
- Image
- Thumbnail
- Stock
- Rating
- Discount
- Tags
- Product pairings
- Substitute products
- Agent tags
- Upsell priority

---

# Agentic Commerce Flow

The complete commerce flow is:

```text
User Intent
    |
    v
Catalog Discovery
    |
    v
Product Recommendation
    |
    v
Session Creation
    |
    v
Cart Creation
    |
    v
Policy Evaluation
    |
    v
Inventory Validation
    |
    v
Human Approval if Required
    |
    v
Cart Update
    |
    v
Checkout
    |
    v
Razorpay Test Order
    |
    v
Test Payment
    |
    v
Payment Confirmation
    |
    v
Audit Trail
```

---

# Autonomous Spending Governance

Concierge does not blindly execute purchases.

The policy engine evaluates actions before execution.

The demo currently uses an autonomous spending threshold of:

```text
₹5,000
```

When a purchase is within the limit:

```text
Policy → Allowed
```

When a purchase exceeds the limit:

```text
Policy → Approval Required
```

The agent stops before executing the restricted action and asks for human approval.

This demonstrates a key property of agentic commerce:

> **The agent has autonomy, but its autonomy is bounded by explicit policy.**

---

# Human Approval Flow

For purchases above the autonomous spending limit:

```text
User requests product
        |
        v
Agent evaluates purchase
        |
        v
Purchase exceeds ₹5,000
        |
        v
Execution is blocked
        |
        v
Human approval modal appears
        |
        v
Approve / Decline
        |
        v
If approved → purchase continues
```

The approval itself becomes part of the audit trail.

---

# Razorpay Integration

Concierge uses **Razorpay Test Mode** for the payment demonstration.

The checkout flow creates a Razorpay test order and allows the user to complete a simulated payment.

The application clearly identifies the payment flow as **TEST MODE**.

No real money is charged.

---

# Razorpay Test Cards

When the Razorpay test checkout opens, use any of the following cards.

| Network | Card Number | Card Type | Sub Type | CVV | Expiry |
|---|---|---|---|---|---|
| Visa | `4100 2800 0000 1007` | Debit | Consumer | Random CVV | Any future date |
| Mastercard | `5555 5100 0008 1006` | Credit | Business | Random CVV | Any future date |
| Mastercard | `5180 2872 0009 1001` | Prepaid | Consumer | Random CVV | Any future date |
| RuPay | `6527 6589 0000 1005` | Credit | Consumer | Random CVV | Any future date |
| Diners | `3608 280009 1007` | Credit | Consumer | Random CVV | Any future date |
| Amex | `3402 560004 01007` | Credit | Consumer | Random CVV | Any future date |

### Recommended Payment Test

1. Open the Concierge demo.
2. Select a product.
3. Add it to the cart.
4. Proceed to checkout.
5. Click **Pay securely**.
6. Select **Cards**.
7. Enter one of the test card numbers above.
8. Use a random CVV.
9. Use any future expiry date.
10. Complete the Razorpay Test Mode transaction.

These cards are intended for Razorpay Test Mode.

---

# Independent Agent Interoperability

Concierge exposes a published API contract that allows an external agent to interact with the commerce system without using the Concierge chat UI.

The dedicated interoperability page demonstrates:

```text
One API.
Any agent.
```

The independent agent can:

```text
GET /catalog
        |
        v
Select product
        |
        v
POST /sessions
        |
        v
POST /cart
        |
        v
POST /cart/{cart_id}/items
        |
        v
Policy evaluation
        |
        v
POST /checkout
        |
        v
Razorpay test order
```

The important distinction is that the independent agent does **not** use Concierge's UI code.

It communicates through the merchant API.

This demonstrates that Concierge's commerce capabilities are exposed as an agent-readable interface rather than being locked inside one frontend.

---

# Interoperability Demo

The `/interop` page shows the independent agent execution trace.

A successful run displays steps such as:

```text
GET /catalog
30 products returned

Selected product

POST /sessions
Session created

POST /cart
Cart created

POST /cart/{cart_id}/items
Policy: allowed

POST /checkout
Checkout status: payment_pending

Razorpay test order created
```

The transaction panel shows the selected product, amount, payment status, and Razorpay order.

---

# Transparency & Auditability

Every important commerce decision leaves an audit event.

The audit layer records events such as:

```text
Cart Created
Policy Decision
Human Approval Granted
Cart Item Added
Checkout Policy Decision
Checkout Started
Razorpay Order Created
Payment Confirmed
```

The audit trail captures information such as:

- Amount
- Cart ID
- Product ID
- Product name
- Policy status
- Approval status
- Order ID
- Razorpay order ID
- Razorpay payment ID
- Timestamp
- Decision reason

This creates a transparent record of what the agent did and why.

---

# Checkout Recovery

Concierge also handles product recovery scenarios.

If a product becomes unavailable or cannot proceed through checkout, the system can use substitute-product information to recover the commerce flow.

The recovery endpoint is:

```text
POST /checkout/recover
```

The recovery flow allows the system to move from:

```text
Unavailable Product
        |
        v
Substitute Recommendation
        |
        v
Policy Evaluation
        |
        v
Cart Update
        |
        v
Checkout
```

---

# AI Upsell Engine

Concierge includes a governed upsell mechanism.

The agent can identify products that pair with items already present in the cart.

The upsell flow is:

```text
Cart
 |
 v
Upsell analysis
 |
 v
Complementary product
 |
 v
User accepts / declines
 |
 v
Policy evaluation
 |
 v
Cart update
```

Upsells remain subject to the same commerce governance rules.

---

# Revenue Simulation

The `/results` page contains a reproducible synthetic revenue experiment.

The simulation compares:

```text
Conventional shopping sessions
vs.
Agent-assisted shopping sessions
```

The current demonstration uses:

```text
40 total synthetic sessions
20 conventional sessions
20 agent-assisted sessions
Random seed: 42
Measure: AOV
```

The displayed experiment currently shows:

```text
Baseline AOV:        ₹1,092.79
Agent-assisted AOV:  ₹2,659.37
AOV Lift:             +143.36%
```

### Important

These figures are **synthetic simulation results** and are not production revenue.

The fixed random seed makes the experiment reproducible.

---

# API

The FastAPI backend provides the commerce API.

Base URL:

```text
https://concierge-ndyg.onrender.com
```

Interactive API documentation:

```text
https://concierge-ndyg.onrender.com/docs
```

OpenAPI specification:

```text
docs/openapi.json
```

Important endpoints include:

```text
GET  /
GET  /health

GET  /catalog
GET  /catalog/search
GET  /catalog/{product_id}

POST /sessions

POST /cart
GET  /cart/{cart_id}
PATCH /cart/{cart_id}
GET  /cart/{cart_id}/policy

POST /cart/{cart_id}/items
POST /cart/{cart_id}/items/approve

POST /cart/{cart_id}/upsell
POST /cart/{cart_id}/upsell/accept
POST /cart/{cart_id}/upsell/decline

POST /checkout
POST /checkout/confirm
POST /checkout/recover

GET  /audit/session/{session_id}

POST /agent/chat

POST /interop/run
```

---

# Project Structure

```text
Concierge/
|
+-- agent-scripts/
|   +-- bare_agent.py
|
+-- backend/
|   +-- app/
|   |   +-- __init__.py
|   |   +-- agent.py
|   |   +-- audit.py
|   |   +-- cart.py
|   |   +-- catalog.py
|   |   +-- checkout.py
|   |   +-- db.py
|   |   +-- interop.py
|   |   +-- llm.py
|   |   +-- main.py
|   |   +-- policy.py
|   |   +-- sessions.py
|   |   +-- substitute.py
|   |   +-- upsell.py
|   |
|   +-- groq_client.py
|   +-- razorpay_client.py
|   +-- requirements.txt
|   +-- scripts/
|   |   +-- seed_products.py
|   +-- test_payment.html
|   +-- .env.example
|
+-- docs/
|   +-- openapi.json
|
+-- frontend/
|   +-- app/
|   |   +-- globals.css
|   |   +-- interop/
|   |   |   +-- page.tsx
|   |   +-- results/
|   |   |   +-- page.tsx
|   |   +-- layout.tsx
|   |   +-- page.tsx
|   |
|   +-- components/
|   |   +-- ConciergeDashboard.tsx
|   |   +-- InteropRunner.tsx
|   |
|   +-- lib/
|   |   +-- api.ts
|   |   +-- types.ts
|   |
|   +-- public/
|   |   +-- revenue_results.json
|   |
|   +-- package.json
|   +-- package-lock.json
|
+-- simulation/
|   +-- revenue_results.json
|   +-- revenue_simulation.py
|
+-- .gitignore
+-- LICENSE
+-- README.md
```

---

# Tech Stack

## Frontend

- Next.js 15
- React 19
- TypeScript
- CSS

## Backend

- Python
- FastAPI
- Pydantic
- Uvicorn

## AI

- Groq
- LLM-powered agent reasoning

## Payments

- Razorpay Test Mode

## API

- REST
- OpenAPI
- Agent-readable commerce endpoints

## Deployment

- Vercel for frontend
- Render for backend

---

# Environment Variables

Secrets are intentionally excluded from Git.

Backend environment variables include values such as:

```text
GROQ_API_KEY
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
```

Frontend deployment uses:

```text
NEXT_PUBLIC_API_URL
```

The repository includes:

```text
backend/.env.example
```

Never commit real API keys or secrets.

---

# Running Locally

## Backend

From the project root:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create:

```text
backend/.env
```

and provide the required environment variables.

Start FastAPI:

```powershell
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:3000
```

For local development, configure:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

---

# Testing the Deployment

Backend health check:

```powershell
Invoke-RestMethod "https://concierge-ndyg.onrender.com/"
```

Catalog check:

```powershell
Invoke-RestMethod "https://concierge-ndyg.onrender.com/catalog"
```

API documentation:

```text
https://concierge-ndyg.onrender.com/docs
```

Frontend:

```text
https://concierge-commerce.vercel.app
```

---

# Demo Routes

## Main Commerce Demo

```text
/
```

Shows:

- Concierge shopping chat
- Product discovery
- Cart interactions
- Policy engine
- Human approval
- Checkout
- Payment flow
- Audit transparency

## Independent Agent

```text
/interop
```

Shows:

- Independent agent execution
- Published API usage
- Catalog discovery
- Session creation
- Cart creation
- Policy evaluation
- Checkout

## Revenue Evidence

```text
/results
```

Shows:

- Synthetic commerce experiment
- Conventional vs agent-assisted AOV
- AOV lift
- Experiment metadata
- Buildathon thesis

---

# Security

The project is configured so that local secrets are excluded from version control.

Ignored files include:

```text
.env
.env.*
venv/
.venv/
node_modules/
.next/
```

Only example environment files are committed.

The repository should never contain:

- API secrets
- Razorpay secret keys
- Groq API keys
- Local environment files
- Authentication credentials

---

# Buildathon Thesis

Concierge is built around a simple idea:

> **The agent isn't just a chatbot. It's a commerce operator.**

A traditional chatbot can answer:

```text
"What shoes should I buy?"
```

An agentic commerce system should be able to:

```text
Discover
    |
    v
Reason
    |
    v
Govern
    |
    v
Transact
```

Concierge demonstrates this loop using a real commerce API, explicit governance, human approval, Razorpay Test Mode payments, independent agent interoperability, and an auditable decision trail.

---

# Why This Architecture Matters

The frontend is only one client.

The actual commerce capabilities live behind the API.

That means:

```text
Concierge UI
      |
      +--------------+
      |              |
      v              v
Chat Agent     Independent Agent
      |              |
      +--------------+
             |
             v
       Commerce API
             |
             v
       Policy Engine
             |
             v
        Checkout
             |
             v
        Razorpay
```

Different agents can therefore interact with the same merchant infrastructure without requiring the same UI.

This is the core interoperability thesis of the project.

---

# Current Status

The project currently includes:

- AI shopping agent
- Dynamic merchant catalog
- Product search and filtering
- Session management
- Cart management
- Autonomous spending policy
- Human approval workflow
- Inventory validation
- AI upselling
- Substitute-product recovery
- Razorpay Test Mode checkout
- Test payment confirmation
- Audit trail
- Independent-agent interoperability
- Published OpenAPI contract
- Synthetic revenue simulation
- Production frontend deployment
- Production backend deployment
- Secure environment-variable handling

---

# License

This project is provided under the license included in the repository.
