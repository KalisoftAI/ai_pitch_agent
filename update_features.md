Sales Agent Application -- Overall Change Log

1. Document Purpose

This document consolidates the application changes, fixes,
authentication work, branding updates, and landing-page improvements
discussed for the Sales Agent application.

Project: Sales Agent / AI Pitch Agent
Project directory: C:\GitHub\ai_pitch_agent
Application architecture: FastAPI backend with frontend application

Status accuracy: Items are marked as Reported completed,
Requested / implementation to verify, or Verification required. A
request or prompt does not by itself prove that the code change has
been implemented.

2. Code Quality and CI Improvements

2.1 Ruff linting and formatting

Reported status: Completed

Reduced Ruff linting errors from 36 to 0.

Fixed the small linting issues identified during the cleanup.

Applied formatting fixes.

Checked that Ruff linting and formatting validations pass.

2.2 Alembic database migration

Reported status: Completed

Created migration:

0006_sales_bi

The migration added or brought the following models and fields under
migration control:

products

product_rates

company_visits

social_metrics

users.role

erp_dispatch

erp_orders

integration_settings

sync_runs

journey_events

voice_transcripts

team_messages

users.password_hash

Additional migration considerations:

Used SQLite-compatible batch operations where required.

Checked migration parity against the application models.

Tested a fresh migration cycle:

Upgrade to Alembic head.

Run alembic check.

Downgrade to base.

Upgrade to head again.

Run alembic check again.

Reported result: Migration checks completed cleanly.

2.3 Prompt sample test fix

Reported status: Completed

Fixed test_prompt_samples.

Added a local fallback file:

data/prompts/weekly_prompts.json

This allows the test to use the local prompt sample data when the
expected external sample is unavailable.

2.4 Test and application validation

Reported results after the CI cleanup:

Ruff check: passed.

Ruff format check: passed.

Pytest: 159 passed.

Application import: passed.

Registered routes: 173.

Follow-up verification: Confirm the actual GitHub Actions CI
pipeline is green on the latest commit.

3. Google Sign-In and Authentication

3.1 Google account restriction

Reported status: Backend implementation completed; end-to-end
verification required

Google Sign-In is intended to allow only these two accounts:

ai.solutions@kalisoftai.in

kalikaenterprises@gmail.com

Other Google accounts must be rejected.

The backend allowlist is the security enforcement point. Hiding or
disabling a frontend button is not a substitute for backend validation.

3.2 Backend implementation reported

Files reported as updated:

sales_fastapi/config.py

sales_fastapi/security.py

sales_fastapi/routers/auth.py

.env.example

tests/test_auth.py

Reported implementation details:

Added configuration for GOOGLE_ALLOWED_EMAILS.

Added Google redirect configuration.

Added Google ID-token verification.

Validates the token signature.

Normalizes the email address.

Rejects missing email addresses.

Requires verified Google email.

Enforces the strict email allowlist.

Reuses the existing authentication flow.

Blocks inactive users.

Safely links an eligible account to an existing placeholder Google
subject where applicable.

Creates a new user only when the Google account is allowlisted.

Assigns the regular sales role to newly created users.

Keeps administrator access governed by the existing RBAC /
admin-email rules.

Avoids writing access tokens or ID tokens to audit logs.

3.3 Authentication endpoints

The reported Google Sign-In flow uses:

POST /api/auth/google --- accepts a Google ID token and returns
the application's JWT/session response.

POST /api/auth/password --- existing username/password login;
intended to remain unchanged.

GET /api/auth/me --- existing authenticated-user endpoint.

3.4 Frontend Google Sign-In

Status: Frontend visibility and implementation must be verified

The login page should visibly provide a Sign in with Google option.

Expected behavior:

Load the official Google Identity Services (GIS) client.

Use the existing GOOGLE_CLIENT_ID.

Receive the Google ID token through the GIS sign-in flow.

Send the ID token to POST /api/auth/google.

Use the application's existing JWT/session handling.

Navigate to the existing dashboard after successful authentication.

Show a clear error message when an account is not on the allowlist.

Keep username/password login available.

Do not expose the Google Client Secret in frontend code.

3.5 Environment configuration

The environment variables discussed include:

GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_ALLOWED_EMAILS=ai.solutions@kalisoftai.in,kalikaenterprises@gmail.com
GOOGLE_REDIRECT_URI=http://localhost:5173

GMAIL_OAUTH_ENABLED=true
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/email/google/callback
FRONTEND_URL=http://localhost:5173

Important distinction:

GOOGLE_REDIRECT_URI was discussed in connection with the frontend
Google sign-in configuration.

GOOGLE_OAUTH_REDIRECT_URI is the Gmail OAuth callback route.

For the GIS popup + ID-token flow, the frontend origin is configured
as an authorized JavaScript origin. A redirect URI is not
necessarily used by that popup flow.

The Google Client Secret must remain server-side and must never be
exposed in frontend bundles.

Use the actual existing .env values; do not replace valid credentials
with placeholders.

3.6 Google Cloud Console configuration discussed

For the Google OAuth web client:

Add http://localhost:5173 as an authorized JavaScript origin.

Add the production frontend origin when deploying.

Do not enter a path such as /static/ as an authorized JavaScript
origin.

Add redirect URIs only for flows that actually use redirects, and
ensure they match the relevant backend callback.

If the OAuth consent screen is in Testing mode, add both permitted
accounts as test users.

3.7 Authentication test coverage

Reported status: Tests added and passing

Added 11 mocked Google authentication tests.

Reported tests/test_auth.py: 16 passed.

Reported full test suite: 170 passed.

Reported Ruff checks: clean.

Reported frontend build: passed.

Required end-to-end verification:

Sign in with ai.solutions@kalisoftai.in.

Sign in with kalikaenterprises@gmail.com.

Attempt sign-in with an unauthorized Google account and confirm
rejection.

Confirm username/password login still works.

Confirm inactive accounts remain blocked.

Confirm the correct role and access permissions are applied.

4. Branding and Logo Replacement

4.1 Existing logo assets

The following assets were supplied for the application:

Kalika logo: C:\GitHub\ai_pitch_agent\Kalika_logo.png

KalisoftAI logo: C:\GitHub\ai_pitch_agent\KalisoftAI logo (1).png

4.2 Logo replacement scope

Status: Requested; implementation must be verified

The requested logo update is limited to replacing existing logo
references:

Replace existing Kalika logo references with Kalika_logo.png.

Replace existing KalisoftAI logo references with
KalisoftAI logo (1).png.

Update only locations where the corresponding logos are already
displayed.

Preserve each logo's original aspect ratio.

Ensure the image assets load correctly.

The original request explicitly limited this task to logo replacement.
It did not authorize unrelated redesign or layout changes as part of
that logo-only task.

5. Landing/Login Page UI and UX Improvements

5.1 Overall design objective

Status: Requested; implementation must be verified

Improve the existing Sales Agent landing/login page using the supplied
screenshot as the visual reference.

The target is a premium, modern SaaS-style interface that presents
KalisoftAI and Kalika branding clearly and provides a clean login
experience.

5.2 Logo presentation on the landing page

Requested changes:

Increase the size of the KalisoftAI and Kalika logos.

Improve alignment and spacing between logos.

Make the logos visually prominent and readable.

Preserve the source image proportions.

Avoid stretching or distortion.

5.3 Landing page visual refinement

Requested changes:

Improve the overall page layout and visual presentation.

Improve typography, spacing, alignment, and visual hierarchy.

Make the left promotional/branding section more engaging.

Refine the right login panel while keeping it clean and easy to use.

Retain the existing brand direction:

Dark green

White / off-white

Orange / yellow accents

Avoid unnecessary clutter and excessive decoration.

5.4 Animation and interaction

Requested enhancements:

Smooth page entrance animation.

Subtle fade-in and slide-in effects for content.

Lightweight animated background/grid effects.

Smooth hover effects for buttons and logos.

Gentle focus and transition effects for form inputs.

Animations should be subtle, performant, and must not interfere with
login interactions or accessibility.

5.5 Responsive design

Requested responsive support for:

Desktop

Laptop

Tablet

Mobile

Expected behavior:

Stack promotional and login sections appropriately on narrow
screens.

Keep both company logos visible and correctly sized.

Adapt font sizes, spacing, and component widths.

Keep buttons and form fields easy to use on touch devices.

Prevent horizontal overflow and unwanted horizontal scrolling.

Maintain a clear visual hierarchy at all viewport sizes.

6. Existing Functionality That Must Remain Unchanged

The visual and branding updates must preserve:

Google Sign-In behavior.

Username/password login.

Existing authentication API contracts.

Existing session/JWT handling.

Existing form validation and error handling.

Existing routing and post-login navigation.

Existing backend behavior.

Existing application sections and functionality.

No backend or database changes are required for the logo replacement or
landing-page visual refinement.

7. Consolidated Verification Checklist

Code quality and CI

Ruff lint passes.

Ruff format check passes.

Full pytest suite passes.

Latest GitHub Actions CI run is green.

Application starts and imports successfully.

Database migrations

Alembic upgrade to head succeeds.

alembic check reports no model/migration differences.

Downgrade and fresh upgrade cycle succeeds in a test
environment.

Existing data is preserved appropriately.

Google authentication

Google Sign-In button is visible on the login page.

First allowlisted account can sign in.

Second allowlisted account can sign in.

Unauthorized Google accounts are rejected by the backend.

Unverified or missing-email tokens are rejected.

Inactive accounts are blocked.

Existing username/password login works.

JWT/session handling and dashboard navigation work.

Client Secret is not exposed in frontend code or logs.

Branding

Kalika logo references use the supplied Kalika asset.

KalisoftAI logo references use the supplied KalisoftAI asset.

Existing logo locations are updated consistently.

Logos retain their original aspect ratios.

No broken image paths remain.

Landing page UI/UX

Logos are larger and visually balanced.

Layout, typography, spacing, and visual hierarchy are improved.

Existing brand colors are retained.

Animations are smooth and lightweight.

Hover and focus states work correctly.

Desktop layout is correct.

Tablet layout is correct.

Mobile layout is correct.

No horizontal overflow occurs.

Login functionality remains unchanged.

Build

Frontend production build succeeds.

No new console errors are introduced.

Final changes are reviewed before commit.

8. Summary of Reported and Requested Work

Area                    Work                    Status

Code quality            Ruff errors reduced     Reported completed
from 36 to 0

Database                Alembic migration       Reported completed
0006_sales_bi created
and tested

Tests                   Prompt sample fallback  Reported completed
added

CI validation           Ruff, pytest, app       Reported completed;
import and route checks latest GitHub CI to
verify

Google Sign-In backend  Strict two-email        Reported completed
allowlist and ID-token
verification

Google Sign-In frontend Visible GIS button and  Verify in application
complete login flow

Logo replacement        Replace existing        Requested; verify
Kalika/KalisoftAI logo  implementation
references

Landing page design     Improve visual quality  Requested; verify
and logo presentation   implementation

Animations              Add subtle entrance,    Requested; verify
background, hover and   implementation
input transitions



feat(branding): update existing Kalika and KalisoftAI logos

Landing page UI

feat(ui): enhance responsive login landing page

If all verified changes are committed together

feat: improve authentication, branding, and landing page UI

10. Final Note

This change log combines the work reported during the project discussion
and the additional implementation scope requested afterward. Before
using it as a final release record, compare it with the Git diff,
confirm which requested frontend changes have actually been implemented,
and update the status labels accordingly.