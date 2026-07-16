# Google login setup guide

This guide walks you from **zero** — no Google Cloud account — to a working
**"Log in with Google"** button on Klyvion. It covers local development and
production. Google login is **optional**: leave the two credentials unset and
Klyvion runs username/password only, hiding the Google button automatically.

> **Time:** ~10 minutes. **Cost:** free.

---

## How it fits together

Klyvion uses the **OpenID Connect** (OAuth 2.0) flow via Authlib:

```
Browser → GET /auth/google/login → Google consent screen
        → Google redirects back to  GET /auth/google/callback
        → Klyvion verifies the identity, upserts the user, sets the session cookie
```

You need three things from Google, which become environment variables:

| From Google | Environment variable |
|-------------|----------------------|
| OAuth **Client ID** | `KLYVION_GOOGLE_CLIENT_ID` |
| OAuth **Client secret** | `KLYVION_GOOGLE_CLIENT_SECRET` |
| (your server's public URL) | `KLYVION_PUBLIC_BASE_URL` |

The **redirect URI** you register with Google must exactly match
`<base-url>/auth/google/callback`.

---

## Step 1 — Create a Google Cloud project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
   Sign in with any Google account (a personal Gmail is fine).
2. In the top bar, click the **project selector** → **New Project**.
3. Name it e.g. `klyvion` and click **Create**. Select the project once created.

## Step 2 — Configure the OAuth consent screen

Google requires a consent screen before it will issue credentials.

1. Left menu → **APIs & Services** → **OAuth consent screen**.
2. **User type:**
   - **External** — anyone with a Google account can log in (what you want for
     a public demo). Choose this unless you have a Google Workspace org.
   - **Internal** — only users in your Workspace organisation.
3. Click **Create** and fill the **App information**:
   - **App name:** `Klyvion`
   - **User support email:** your email
   - **Developer contact email:** your email
   - (Logo, app domain, etc. are optional for testing.)
4. **Scopes:** click **Add or Remove Scopes** and select the three basic ones
   (they may already be default): `openid`, `.../auth/userinfo.email`,
   `.../auth/userinfo.profile`. Klyvion needs only the user's email and name.
5. **Test users** (External + "Testing" mode): add the Google accounts you'll
   use to log in during development. In Testing mode only these accounts work.
6. **Save and continue** through to the summary.

> **Testing vs Production:** while the app is in **Testing**, only the test
> users you listed can log in, and a scary "unverified app" screen appears —
> that's normal for dev. To open it to the public, click **Publish App** on the
> consent screen. Google verification is only required if you request sensitive
> scopes; the three basic scopes above generally do not need verification.

## Step 3 — Create the OAuth Client ID

1. Left menu → **APIs & Services** → **Credentials**.
2. **+ Create Credentials** → **OAuth client ID**.
3. **Application type:** **Web application**.
4. **Name:** `Klyvion web`.
5. **Authorized redirect URIs** → **+ Add URI**. Add one per environment you
   run. The path is always `/auth/google/callback`:

   | Environment | Redirect URI |
   |-------------|--------------|
   | Local dev | `http://localhost:8000/auth/google/callback` |
   | Production | `https://klyvion.sharadbhandari.com.np/auth/google/callback` |

   > The scheme, host, and port must match **exactly** what the browser hits.
   > `localhost` ≠ `127.0.0.1` to Google — pick one and be consistent. You do
   > **not** add "Authorized JavaScript origins" for this server-side flow.
6. Click **Create**. A dialog shows your **Client ID** and **Client secret** —
   copy both now (you can re-open them later from the Credentials page).

## Step 4 — Set the environment variables

Add to your `.env` (copy from [`.env.example`](../.env.example)):

```bash
KLYVION_GOOGLE_CLIENT_ID=1234567890-abcdef....apps.googleusercontent.com
KLYVION_GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx

# Base URL used to build the redirect URI. Locally this can be omitted (it is
# derived from the request); set it explicitly in production / behind a proxy so
# the redirect matches EXACTLY what you registered in Step 3.
KLYVION_PUBLIC_BASE_URL=https://klyvion.sharadbhandari.com.np

# Recommended so sessions survive restarts (any stable, random >=32-char string):
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
KLYVION_SECRET_KEY=replace-with-a-long-random-value
```

Both `KLYVION_GOOGLE_*` values must be set for the feature to turn on. If either
is blank, Google login stays disabled and the UI hides its button —
username/password login continues to work.

## Step 5 — Run and test

```bash
pip install -e ".[server]"        # installs authlib, httpx, etc.
klyvion serve --host 0.0.0.0 --port 8000
```

1. Open `http://localhost:8000/`.
2. Click **Log in / Sign up** → **Continue with Google**.
3. Complete Google consent with one of your **test users**.
4. You're redirected back signed in; `GET /auth/config` now reports
   `{"google_enabled": true}`.

Verify the server sees the config:

```bash
curl http://localhost:8000/auth/config
# {"google_enabled":true}
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| **Error 400: redirect_uri_mismatch** | The redirect URI Klyvion built does not exactly match one registered in Step 3. Check scheme/host/port and set `KLYVION_PUBLIC_BASE_URL`. Behind a proxy, ensure `X-Forwarded-Proto: https` is passed so the URL is `https`. |
| **"Access blocked: app not verified"** | App is in Testing mode. Either add the account under **Test users**, or **Publish App**. |
| **403 `access_denied`** | The logging-in account is not a listed test user while in Testing mode. |
| **Google button doesn't appear** | One or both `KLYVION_GOOGLE_*` vars are unset/empty. Confirm with `GET /auth/config`. |
| **Sessions drop on restart** | `KLYVION_SECRET_KEY` is unset (ephemeral key). Set a stable value. |
| **`invalid_client`** | Client ID/secret mismatch or trailing whitespace in the env var. Re-copy from the Credentials page. |

## Security notes

- The **client secret** is a real secret. Keep it in `.env` (git-ignored), never
  commit it, and rotate it from the Credentials page if it leaks.
- Klyvion stores only the user's email and display name (from the basic scopes).
- The session is a signed, `HttpOnly`, `SameSite=Lax` cookie — not readable by
  page scripts and it survives the Google redirect round-trip.

## Related

- Environment reference: [`.env.example`](../.env.example)
- Billing (token credits & Stripe): [BILLING.md](BILLING.md) · [STRIPE_SETUP.md](STRIPE_SETUP.md)
