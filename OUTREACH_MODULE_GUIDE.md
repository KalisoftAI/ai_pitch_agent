# Outreach Module Guide

This guide covers the refined outreach flow: template selection, preview, contact selection, channel selection, review, sending, progress, and customer forms.

## 1. Guided send workflow

Open **Marketing → Send & templates**. The workflow bar shows six stages:

1. **Template** - search/filter the Kalika template library, preview, edit, duplicate, or select a template.
2. **Preview** - personalize the message using a sample recipient before contacts are selected; check missing values and invalid placeholders.
3. **Contacts** - sync, filter, select, normalize, de-duplicate, and export recipients.
4. **Channel** - choose Email, WhatsApp, or Both and attach poster/video/catalogue assets.
5. **Review** - confirm template, channel, recipient counts, personalization warnings, then send now or send for review.
6. **Insights** - open the insights tab for sent/viewed/failed counts and campaign analytics.

After sending, a progress panel shows per-recipient status, retries, approval actions, and campaign history.

## 2. Validation rules

- Email normalization removes invisible characters, splits multi-address cells, lowercases the value, and selects the first syntactically valid address.
- Phone normalization keeps digits only. A phone is WhatsApp/call-ready when it has at least 8 digits.
- Invalid emails/phones are shown with inactive channel icons and are excluded from channel counts.
- `POST /api/marketing-companies/normalize-emails` repairs stored email syntax. It never changes verification status; there is no verification column in the current schema.
- `filterByChannel` in `frontend/src/validation.js` and the backend `channel` query parameter use the same ready-to-send rules.

## 3. Contact selection and channel filtering

- Channel filter chips: **All**, **Email**, **WhatsApp**, **Phone**.
- The table and mobile cards update immediately; selection survives filtering and pagination through an internal cache.
- Toolbar actions: **Select all on page**, **Select all matching**, **Clear selection**, **Normalize emails**, **Remove dupes**, **Export CSV**, and **Continue**.
- The selected-count badge is a live region for accessibility.
- Channel icons use Mail, MessageCircle, and PhoneCall glyphs instead of text badges.

## 4. Customer feedback and review forms

Admins can manage public form links in **Marketing → Forms & feedback**:

- Feedback form URL (default: `/static/forms/feedback.html`)
- Product review URL (default: `/static/forms/review.html`)
- Meeting/enquiry URL (default mailto link)

Links are stored in `IntegrationSetting` under key `outreach_form_links`. During personalization, known contact fields (`contact_name`, `company`, `email`, `phone`, `order_number`, `product_name`) are appended as query parameters to http(s) form URLs. Public submissions are stored in the existing `Feedback` table with categories `customer_feedback` and `product_review`, page `outreach_customer_form`.

Relevant endpoints:

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/forms/config` | public | Effective form links |
| POST | `/api/public/forms/feedback` | public | Submit customer feedback |
| POST | `/api/public/forms/review` | public | Submit product review |
| GET | `/api/outreach-forms/links` | authenticated | Read editable links |
| PUT | `/api/outreach-forms/links` | authenticated | Save editable links |
| GET | `/api/outreach-forms/submissions` | authenticated | Recent form submissions |

## 5. Email and WhatsApp templates

- WA-11 and WA-13 include `{{FEEDBACK_FORM_URL}}` quick feedback links.
- WA-12 uses the configured review link note.
- Placeholders such as `{{contact_name}}`, `{{company_name}}`, `{{product_name}}`, `{{FEEDBACK_FORM_URL}}`, `{{REVIEW_LINK}}`, and `{{MEETING_LINK}}` resolve per recipient.
- HTML templates cannot be sent over WhatsApp. The Preview stage offers conversion to plain text or saving a WhatsApp text template.

## 6. Local development

```powershell
C:\Python314\python.exe -m uvicorn sales_fastapi.main:app --reload --port 8000
npm --prefix frontend run dev
```

Validation commands:

```powershell
C:\Python314\Scripts\ruff.exe check sales_fastapi
C:\Python314\python.exe tests_e2e_mail.py
npm --prefix frontend run build
```

No browser automation is available in this environment; UI verification is limited to the Vite production build and API-level tests.

## 7. Data and safety notes

- Backend, database models, authorization, and unrelated modules are unchanged.
- Email normalization is syntax-only and does not invent verification state.
- Form link editing and submissions are authenticated; public form submission endpoints are intentionally open.
- The local dev database is a snapshot; production database access is not read-only from this environment.
- New work stays on `feature/outreach-module-refinement`; do not merge into `main` from this workflow.
