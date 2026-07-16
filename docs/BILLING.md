# Token credits & billing

Klyvion can meter synthesis with a **token-credit** system and sell top-ups
through **Stripe**. It is **off by default** — nothing below changes the open,
anonymous demo unless you switch it on.

## How it works

- A new account is granted **starter credits** on registration
  (`KLYVION_SIGNUP_CREDITS`, default `5000`).
- Each `/synthesize` call costs `len(text) × KLYVION_TOKENS_PER_CHAR` credits
  (default **1 credit per character**), debited from the caller's balance.
- When the balance is too low, the API returns **HTTP 402** and the web UI
  opens the *Buy credits* dialog.
- Each account tracks lifetime **`credits_used`** and **`credits_granted`** on
  top of the remaining **`credits`**, all returned by `GET /auth/me`. The web UI
  surfaces them in an **account profile** (click your name or the credit pill):
  tokens remaining / used / granted, a usage bar, and the per-character rate.
  A refund for a failed generation rolls back `credits_used`, so failures never
  count as usage.
- Three tiers are advertised at `/billing/plans`:

  | Plan | Credits | Price |
  |------|---------|-------|
  | Free | 5,000 (signup grant) | — (not purchasable) |
  | Standard | 50,000 | $9.00 |
  | Premium | 200,000 | $29.00 |

  Purchases are **one-time credit top-ups** (Stripe Checkout `mode=payment`),
  not recurring subscriptions. A completed checkout fires a webhook that credits
  the buyer's account.

## Switching it on

```bash
export KLYVION_BILLING_ENABLED=1          # master switch (default 0 = off)
export KLYVION_SIGNUP_CREDITS=5000        # starter grant per new account
export KLYVION_TOKENS_PER_CHAR=1          # credits charged per character
```

With billing **on**, `/synthesize` requires a logged-in session (it must know
whose balance to debit); preview and download behave as before. With billing
**off**, synthesis stays open and anonymous and no credit fields appear.

> Metering can run without Stripe (no `KLYVION_STRIPE_SECRET_KEY`): users spend
> their starter credits but cannot buy more, and the UI hides the buy buttons.

## Testing payments in development (Stripe test mode)

> For the full walkthrough — creating a Stripe account, finding your keys, and
> going live — see **[STRIPE_SETUP.md](STRIPE_SETUP.md)**. The quick version:

Stripe **test mode** lets you complete real checkout flows with fake cards — no
money moves. Use your `sk_test_…` / `pk_test_…` keys.

1. Create a Stripe account and copy the **test** keys from the dashboard
   (Developers → API keys).
2. Configure the server:

   ```bash
   export KLYVION_BILLING_ENABLED=1
   export KLYVION_STRIPE_SECRET_KEY=sk_test_xxx
   export KLYVION_STRIPE_PUBLISHABLE_KEY=pk_test_xxx
   export KLYVION_PUBLIC_BASE_URL=http://localhost:8000   # for success/cancel URLs
   klyvion serve --port 8000
   ```

3. Forward webhooks to your local server with the Stripe CLI and copy the
   signing secret it prints into `KLYVION_STRIPE_WEBHOOK_SECRET`:

   ```bash
   stripe listen --forward-to localhost:8000/billing/webhook
   # -> "Ready! Your webhook signing secret is whsec_xxx"
   export KLYVION_STRIPE_WEBHOOK_SECRET=whsec_xxx      # then restart the server
   ```

4. In the web UI: sign up, click **Buy credits**, pick a tier, and pay with a
   Stripe **test card**:

   | Card number | Result |
   |-------------|--------|
   | `4242 4242 4242 4242` | Payment succeeds |
   | `4000 0000 0000 9995` | Card declined (insufficient funds) |
   | `4000 0025 0000 3155` | Requires 3D Secure authentication |

   Use any future expiry, any CVC, any postal code. On success the webhook
   credits your account and the UI shows the new balance.

### Offline, without a Stripe account

For unit tests and fully offline dev, inject the `FakePaymentProvider`, which
completes instantly and treats a plain-JSON webhook body as trusted:

```python
from klyvion.api.server import create_app
from klyvion.billing import BillingService, FakePaymentProvider

billing = BillingService.from_settings(
    settings, store=store, provider=FakePaymentProvider()
)
app = create_app(tts, billing=billing)
```

See `tests/test_billing.py` for the end-to-end pattern.

## Disabling in production

Billing is off unless `KLYVION_BILLING_ENABLED=1`. To run the public demo with
open, unmetered synthesis (the launch recommendation), simply leave it unset —
or set it to `0` — in production:

```bash
KLYVION_BILLING_ENABLED=0     # open demo: no login, no credits, no payments
```

To take payments for real, set `KLYVION_BILLING_ENABLED=1` **and** swap the
Stripe test keys for **live** keys (`sk_live_…`, `pk_live_…`) plus a live
webhook endpoint secret. Nothing else changes — the same code path runs test
and live; the key prefix is the only difference.

## Environment variables

| Var | Default | Notes |
|-----|---------|-------|
| `KLYVION_BILLING_ENABLED` | `0` | Master switch. `1` meters synthesis. |
| `KLYVION_SIGNUP_CREDITS` | `5000` | Starter credits per new account. |
| `KLYVION_TOKENS_PER_CHAR` | `1` | Credits charged per character. |
| `KLYVION_STRIPE_SECRET_KEY` | `` | `sk_test_…` (dev) / `sk_live_…` (prod). Empty ⇒ purchasing disabled. |
| `KLYVION_STRIPE_PUBLISHABLE_KEY` | `` | `pk_…` exposed to the browser. |
| `KLYVION_STRIPE_WEBHOOK_SECRET` | `` | `whsec_…` used to verify webhook signatures. |
| `KLYVION_CURRENCY` | `usd` | ISO currency for checkout. |
| `KLYVION_PUBLIC_BASE_URL` | (derived) | Base URL for building checkout success/cancel URLs. |

## HTTP endpoints

- `GET /billing/config` → `{billing_enabled, purchase_enabled, currency, tokens_per_char, publishable_key}`
- `GET /billing/plans` → advertised tiers
- `POST /billing/checkout` `{plan_id}` (login required) → `{checkout_url}`
- `POST /billing/webhook` → Stripe (or fake) completion callback; credits the buyer
