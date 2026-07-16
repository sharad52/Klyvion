# Stripe payment setup guide

This guide takes you from **zero** — no Stripe account — to selling token-credit
top-ups in Klyvion, first with **test cards** in development and then with
**live** payments in production. Payments are **optional** and **off by
default**; see [BILLING.md](BILLING.md) for the credit model itself.

> **Time:** ~15 minutes for test mode. **Cost:** free (test mode moves no money;
> live mode charges Stripe's per-transaction fee).

---

## How it fits together

```
Browser → POST /billing/checkout {plan_id}   (login required)
        → Klyvion asks Stripe to create a Checkout Session
        → browser is redirected to Stripe's hosted payment page
        → user pays → Stripe redirects back to  /?purchase=success
        → Stripe also calls  POST /billing/webhook  (server-to-server)
        → Klyvion verifies the signature and credits the account
```

The **webhook is what actually grants credits** — the browser redirect is only
cosmetic. So a working setup needs both the API keys *and* the webhook secret.

You need three values from Stripe, which become environment variables:

| From Stripe | Environment variable | Example |
|-------------|----------------------|---------|
| **Secret key** | `KLYVION_STRIPE_SECRET_KEY` | `sk_test_…` / `sk_live_…` |
| **Publishable key** | `KLYVION_STRIPE_PUBLISHABLE_KEY` | `pk_test_…` / `pk_live_…` |
| **Webhook signing secret** | `KLYVION_STRIPE_WEBHOOK_SECRET` | `whsec_…` |

> **Test mode is not a separate account.** Every Stripe account has a Test/Live
> toggle. `sk_test_`/`pk_test_` keys drive the sandbox; `sk_live_`/`pk_live_`
> keys charge real cards. Klyvion runs the *same code* for both — the key prefix
> is the only difference.

---

## Part A — Development (test mode, with test cards)

### Step 1 — Create a Stripe account

1. Go to [stripe.com](https://stripe.com) → **Sign up**. Confirm your email.
2. You land in the [Dashboard](https://dashboard.stripe.com/). You can use
   **test mode** immediately — you do **not** need to "activate" the account
   (business details, bank info) until you want to take real money.
3. Make sure the **Test mode** toggle (top-right) is **ON** while developing.

### Step 2 — Copy your test API keys

1. Dashboard → **Developers** → **API keys**
   (direct link: `https://dashboard.stripe.com/test/apikeys`).
2. Copy the **Publishable key** (`pk_test_…`) and **Secret key** (`sk_test_…`).
   Click **Reveal** to see the secret key.

### Step 3 — Install the Stripe CLI and forward webhooks

In development, Stripe can't reach your `localhost`, so the **Stripe CLI**
tunnels webhook events to you.

1. Install it: [stripe.com/docs/stripe-cli](https://docs.stripe.com/stripe-cli)
   (`brew install stripe/stripe-cli/stripe`, `scoop install stripe`, or download
   a binary). Then authenticate:

   ```bash
   stripe login
   ```

2. Start forwarding to Klyvion's webhook endpoint:

   ```bash
   stripe listen --forward-to localhost:8000/billing/webhook
   ```

   It prints a line like:

   ```
   > Ready! Your webhook signing secret is whsec_abc123...  (^C to quit)
   ```

   **Copy that `whsec_…` value** — it's your `KLYVION_STRIPE_WEBHOOK_SECRET` for
   local dev. Leave this process running while you test.

### Step 4 — Set the environment variables

Add to your `.env` (template in [`.env.example`](../.env.example)):

```bash
KLYVION_BILLING_ENABLED=1
KLYVION_STRIPE_SECRET_KEY=sk_test_xxx
KLYVION_STRIPE_PUBLISHABLE_KEY=pk_test_xxx
KLYVION_STRIPE_WEBHOOK_SECRET=whsec_xxx          # from `stripe listen`
KLYVION_PUBLIC_BASE_URL=http://localhost:8000    # builds success/cancel URLs
KLYVION_CURRENCY=usd

# Recommended so login sessions survive restarts:
KLYVION_SECRET_KEY=replace-with-a-long-random-value
```

### Step 5 — Run the server and pay with a test card

```bash
pip install -e ".[server]"        # installs the `stripe` package
klyvion serve --host 0.0.0.0 --port 8000
```

1. Open `http://localhost:8000/`, **sign up** (you get 5,000 starter credits).
2. Click **Buy credits**, choose **Standard** or **Premium**.
3. On Stripe's hosted page, pay with a **test card**:

   | Card number | Outcome |
   |-------------|---------|
   | `4242 4242 4242 4242` | ✅ Payment succeeds |
   | `4000 0000 0000 9995` | ❌ Declined — insufficient funds |
   | `4000 0025 0000 3155` | 🔐 Requires 3D Secure authentication |

   Use **any** future expiry (e.g. `12/34`), any 3-digit CVC, any postal code.

4. You're redirected back to `/?purchase=success`. The `stripe listen` terminal
   shows `checkout.session.completed`, and the UI balance jumps by the plan's
   credits. Confirm server-side:

   ```bash
   curl -b cookies.txt http://localhost:8000/auth/me
   # {"user":{...,"credits":55000,"plan":"standard"}}
   ```

More test cards & scenarios: [stripe.com/docs/testing](https://docs.stripe.com/testing).

---

## Part B — Production (live payments)

### Step 1 — Activate your account

Real charges require an activated account: Dashboard → **Activate / complete
your business profile** (legal entity, address, and a bank account for payouts).

### Step 2 — Copy your live keys

Toggle **Test mode OFF**, then **Developers** → **API keys** and copy the
**live** `pk_live_…` and `sk_live_…`.

### Step 3 — Register a live webhook endpoint

The Stripe CLI is dev-only. In production you register a public URL:

1. Dashboard (live mode) → **Developers** → **Webhooks** → **Add endpoint**.
2. **Endpoint URL:** `https://klyvion.sharadbhandari.com.np/billing/webhook`
3. **Events to send:** select **`checkout.session.completed`** (the only event
   Klyvion acts on). You may add `checkout.session.async_payment_succeeded` too.
4. **Add endpoint**, then open it and reveal the **Signing secret** (`whsec_…`).

### Step 4 — Set production environment variables

```bash
KLYVION_BILLING_ENABLED=1
KLYVION_STRIPE_SECRET_KEY=sk_live_xxx
KLYVION_STRIPE_PUBLISHABLE_KEY=pk_live_xxx
KLYVION_STRIPE_WEBHOOK_SECRET=whsec_live_xxx      # from the dashboard endpoint
KLYVION_PUBLIC_BASE_URL=https://klyvion.sharadbhandari.com.np
KLYVION_CURRENCY=usd
KLYVION_SECRET_KEY=<stable-random-32+chars>
```

> **Reverse proxy:** the webhook must reach `POST /billing/webhook` with the
> **raw, unmodified body** — signature verification fails otherwise. If you use
> the nginx config in `deploy/`, ensure the `/billing/` location proxies the
> body untouched (no buffering rewrites) and that `/synthesize` rate limits do
> not also throttle the webhook path.

### Step 5 — Verify end-to-end

Make one real low-value purchase (or use Stripe's
[test-clock / test-in-live](https://docs.stripe.com/testing) tooling), confirm
the webhook shows **200** in the dashboard's endpoint logs, and that the
account's credits increased.

---

## Disabling payments

- **Meter credits but sell nothing:** set `KLYVION_BILLING_ENABLED=1` and leave
  `KLYVION_STRIPE_SECRET_KEY` blank. Users spend starter credits; the UI hides
  the buy buttons; `/billing/checkout` returns `503`.
- **Turn the whole feature off (open demo):** set `KLYVION_BILLING_ENABLED=0`
  (or leave it unset). Synthesis is open, anonymous, and unmetered — the launch
  default. See [BILLING.md](BILLING.md#disabling-in-production).

---

## Offline development without Stripe

For unit tests or fully offline work, inject the `FakePaymentProvider` — no
Stripe account, no network. See [BILLING.md](BILLING.md#offline-without-a-stripe-account)
and `tests/test_billing.py`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Buy buttons don't appear | `KLYVION_STRIPE_SECRET_KEY` is blank, or `KLYVION_BILLING_ENABLED=0`. Check `GET /billing/config`. |
| `/billing/checkout` → **503** | No payment provider configured (secret key missing). |
| Paid, but credits didn't change | The **webhook** didn't reach the server or failed verification. In dev, is `stripe listen` running with the matching `whsec_`? In prod, check the endpoint's delivery logs in the dashboard. |
| Webhook returns **400** | Signature mismatch: wrong `KLYVION_STRIPE_WEBHOOK_SECRET`, or a proxy altered the request body. |
| `checkout.session.completed` but 0 credited | The session `metadata.username` didn't match an account. Klyvion sets this automatically; only happens if you replay a hand-crafted event. |
| Redirect after payment 404s | `KLYVION_PUBLIC_BASE_URL` is wrong; success/cancel URLs are built from it. |

## Security notes

- `sk_…` and `whsec_…` are **real secrets**. Keep them in `.env` (git-ignored);
  never commit them or expose the secret key to the browser. Only the
  **publishable** key (`pk_…`) is sent to the page.
- Klyvion **verifies every webhook's signature** with `whsec_…` before granting
  credits, so a forged request cannot top up an account.
- Rotate keys from **Developers → API keys** if one leaks.

## Related

- Credit model & tiers: [BILLING.md](BILLING.md)
- Google login: [GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md)
- Environment reference: [`.env.example`](../.env.example)
