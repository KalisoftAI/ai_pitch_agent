# Kalika Enterprises — Real-Time Customer Feedback System

## 1. Project Overview

Build a **QR-based, real-time customer engagement and feedback system** for Kalika Enterprises. The system should connect customers to the product catalogue, delivery updates, product feedback, issue reporting, and customer support through a simple mobile-friendly experience.

The system should ask relevant questions based on the customer's interaction, product, delivery status, and any issue reported. Avoid sending the same generic message at every stage.

### Core objectives

- Collect customer feedback in real time.
- Understand delivery experience and delivery-related problems.
- Capture product-specific feedback and quality issues.
- Make the product catalogue accessible from QR codes and messages.
- Route complaints and requests to the appropriate team.
- Track issue ownership, status, and resolution.
- Give management a dashboard of satisfaction, delivery performance, recurring issues, and improvement opportunities.
- Keep the customer experience simple, interactive, and mobile-first.

## 2. Product Catalogue Scope

The provided Kalika Enterprises catalogue includes:

- Stretch Film
- Shrink Film
- BOPP / Packaging Tape
- Masking Tape
- Strap & Buckles
- VCI Bag & Box
- Tarpauline
- HDPE Bag
- Poly Bag
- Shade Net
- Poly Box
- Hand Gloves
- Hand Sleeves

Use the uploaded catalogue as the source for product descriptions and images. Current prices, stock, and delivery estimates should come from verified business data, not be hard-coded into messages.

## 3. Customer Journey

```text
                 KALIKA ENTERPRISES
                         |
             Customer scans the QR code
                         |
             Open WhatsApp / Feedback Page
                         |
           +-------------+-------------+
           |                           |
      View Catalogue             Existing Customer
           |                           |
    Explore Products          Identify Order / Product
           |                           |
           +-------------+-------------+
                         |
               Choose Interaction
                         |
        +----------------+----------------+
        |                |                |
     Delivery          Product          General
      Status            Issue           Feedback
        |                |                |
   On time / Late    Quality / Size    Service /
   / Not received    / Packaging       Suggestions
        |                |                |
        +----------------+----------------+
                         |
              Ask Relevant Questions
                         |
            Rating + Optional Comments
                         |
              Any Further Assistance?
                   /           \\
                 Yes            No
                  |              |
           Create Support      Thank You
              Request          Message
                  |
           Assign Team Member
                  |
          Track Resolution Status
                  |
          Follow-up with Customer
                  |
           Feedback Dashboard
```

### Core flow

1. Customer scans a QR code.
2. QR opens a WhatsApp conversation or mobile-friendly feedback page.
3. Customer chooses catalogue, delivery, feedback, product issue, or support.
4. The system identifies the product/order when possible.
5. The system asks only the follow-up questions relevant to the chosen response.
6. Customer submits a rating and/or optional comment.
7. If assistance is required, create a support ticket and route it to a team.
8. Send a confirmation/thank-you message.
9. Track the ticket through resolution and ask for follow-up feedback when appropriate.
10. Display feedback and operational metrics on the internal dashboard.

> **Implementation note:** Scanning a QR code alone does not automatically identify a customer or order unless the QR links to a customer/order record or the customer provides the necessary information. For order-specific QR codes, use a secure reference to the order rather than exposing personal information.

## 4. Ready-to-Use WhatsApp Messages

These are draft message templates. Use interactive buttons or lists where supported by the chosen messaging channel. Actual WhatsApp templates, opt-in, and messaging rules must be implemented according to the applicable WhatsApp Business Platform requirements.

### Message 1 — Welcome Message

**Trigger:** Customer scans a general QR code on a delivery challan, invoice, packaging label, or brochure.

**Message:**

> 👋 Hello from Kalika Enterprises!
>
> Thank you for choosing us.
>
> We'd love to make your experience even better. How can we help you today?
>
> 📦 View Product Catalogue  
> 🚚 Check Delivery Status  
> ⭐ Share Feedback  
> 🛠️ Report a Product Issue  
> 💬 Talk to Our Team
>
> Your feedback matters to us!

**Suggested interactive buttons:** `Catalogue` · `Delivery` · `Feedback` · `Report Issue` · `Contact Team`

**Expected behavior:**
- Catalogue opens product categories.
- Delivery asks for or retrieves an order reference.
- Feedback starts the rating flow.
- Report Issue starts issue categorization.
- Contact Team creates or routes a support request, or shows available contact options.

### Message 2 — Delivery Feedback

**Trigger:** Delivery is marked completed, or customer selects the delivery feedback option.

**Message:**

> 🚚 Hi! Your experience matters to us.
>
> How was your recent delivery from Kalika Enterprises?
>
> Choose one option:
>
> ✅ Delivered on time  
> ⏳ Delivered late  
> 📦 Not received yet  
> 🤝 Delivery team feedback
>
> Tap an option to continue.

**Conditional follow-ups:**

- **On time:**  
  “Great! 😊 Was the delivery experience satisfactory?”
- **Delivered late:**  
  “Sorry for the inconvenience. What caused the biggest concern: delayed arrival, communication, or another issue?”
- **Not received:**  
  “We're sorry about that. Please share your order or invoice number so our team can check.”
- **Delivery team feedback:**  
  “How would you rate the coordination and communication from our delivery team?”

**Expected behavior:**
- Retrieve order information from the ERP when it is available and permitted.
- If the order cannot be identified, ask for an order or invoice reference.
- Record delivery feedback separately from product quality feedback.
- Create a delivery support ticket if the customer reports a missing or problematic delivery.

### Message 3 — Product Quality Feedback

**Trigger:** Customer chooses feedback or receives a post-delivery feedback request.

**Message:**

> ⭐ Help Us Improve Our Products!
>
> How satisfied are you with the product you received?
>
> ⭐ Excellent  
> 👍 Good  
> 😐 Average  
> 👎 Needs Improvement
>
> Which product are you reviewing?
>
> 📦 Stretch Film  
> 📦 BOPP / Masking Tape  
> 📦 VCI Bags & Boxes  
> 📦 Tarpaulin / Poly Bags  
> 🧤 Knitted Hand Gloves  
> ➕ Other Product
>
> Your honest feedback helps us improve!

**Follow-up based on rating:**

| Customer rating | Follow-up message |
|---|---|
| Excellent | “Wonderful! 🎉 What did you like most about the product?” |
| Good | “Thank you! What could make it even better?” |
| Average | “We'd love to improve. What could we do differently?” |
| Needs Improvement | “We're sorry we fell short. What issue did you experience?” |

**Expected behavior:**
- Record the rating against the product, customer, and order when identifiable.
- Let the customer select the specific product being reviewed.
- Keep comments optional unless additional details are necessary to resolve a complaint.
- For a low rating, offer relevant issue categories and an option to contact the team.

### Message 4 — Product-Related Issue Reporting

**Trigger:** Customer selects `Report a Product Issue` or provides a low rating.

**Message:**

> 🛠️ Let's resolve your concern.
>
> What issue are you experiencing?
>
> 🔹 Product quality  
> 🔹 Incorrect size or specification  
> 🔹 Damaged packaging  
> 🔹 Quantity mismatch  
> 🔹 Product performance  
> 🔹 Other issue
>
> Please share your order/invoice number and a brief description.
>
> 📸 You can also attach a photo if it helps explain the issue.
>
> Our team will review your concern and follow up.

**Expected system actions:**

1. Create a customer complaint/support ticket.
2. Link the ticket to the customer, product, and order when identifiable.
3. Route the ticket to the relevant team.
4. Track status: `Open` → `Assigned` → `In Progress` → `Resolved`.
5. Notify the customer when a meaningful status update is available.
6. Preserve issue history and resolution notes for internal reporting.

**Suggested ticket fields:**
- Ticket ID
- Created date/time
- Customer/contact reference
- Order/invoice reference, if available
- Product
- Issue category
- Customer description
- Attachments/photo reference
- Priority
- Assigned team/person
- Status
- Internal notes
- First-response timestamp
- Resolution timestamp
- Resolution summary
- Customer follow-up rating

Do not promise a fixed resolution time until service-level targets have been established.

### Message 5 — Product Catalogue Interaction

**Trigger:** Customer scans a catalogue QR code or selects `View Product Catalogue`.

**Message:**

> 📦 Explore the Kalika Enterprises Product Range!
>
> Find the right packaging solution for your business.
>
> Choose a category:
>
> 🎞️ Stretch Film & Shrink Film  
> 📦 BOPP Tape & Masking Tape  
> 🛡️ VCI Bags & Boxes  
> 🚛 Tarpaulin & HDPE Bags  
> 🛍️ Poly Bags & Poly Boxes  
> 🌱 Shade Net  
> 🧤 Knitted Hand Gloves & Hand Sleeves  
> 🔗 Straps & Buckles
>
> Which product would you like to know more about?
>
> Select a product to view its available specifications and request assistance from our team.

**Suggested interactive features:**
- Product category buttons.
- Product images and specifications.
- Product enquiry button.
- Request a quotation.
- Talk to sales.
- Return to feedback.

Use catalogue information as the source for product descriptions and images. Keep current prices, stock, and delivery estimates connected to verified business data.

### Message 6 — Improvement Suggestion

**Trigger:** After feedback submission or at the end of a support interaction.

**Message:**

> 💙 One Last Question!
>
> What is ONE thing Kalika Enterprises could improve to serve you better?
>
> 🚚 Faster Delivery  
> ⭐ Better Product Quality  
> 📦 Improved Packaging  
> 💬 Faster Communication  
> 💰 Better Value  
> ✨ Something Else
>
> You can also type your suggestion below.
>
> Thank you for helping us grow! 🙏

**Expected behavior:**
- Store the selected improvement category.
- Allow optional free-text suggestions.
- Analyze suggestions by frequency, product, and customer interaction type.
- Avoid repeatedly asking the same customer for the same feedback in a short period.

### Message 7 — Thank You and Further Support

**Trigger:** After the customer completes the feedback flow.

**Message:**

> 🙏 Thank You for Your Feedback!
>
> Your opinion helps Kalika Enterprises improve our products, delivery, and customer service.
>
> Would you like any further assistance?
>
> 📦 Explore Products  
> 🚚 Check an Order  
> 🛠️ Follow Up on an Issue  
> 👨‍💼 Contact Our Team
>
> We're here to help you pack, protect, and perform better!

**Expected behavior:**
- End the feedback flow gracefully.
- Keep the support options available.
- If a ticket was created, show its reference number where possible.
- Avoid claiming an issue is resolved until the ticket is actually resolved.

## 5. QR Code Strategy

> **STATUS: NEXT SCOPE.** QR-based entry is not part of the current build. The live pipeline (section 16.9) sends personalised messages directly via wa.me click-to-send. This section stays as the design reference for the QR phase.

Use separate QR entry points so the system can understand where a customer started.

| QR type | Placement | Purpose | Suggested destination |
|---|---|---|---|
| General Feedback QR | Business cards, brochures, reception | General feedback and enquiries | General feedback landing page or WhatsApp menu |
| Delivery QR | Invoice, delivery challan, dispatch documents | Delivery experience and order-related issues | Delivery feedback flow |
| Product QR | Product labels, packaging, catalogue | Product specifications, feedback, and support | Product page or product feedback flow |

### QR implementation requirements

- Assign a unique source identifier to each QR type or placement.
- Use secure references for order-specific QR codes.
- Do not expose names, phone numbers, addresses, or other personal data directly in QR URLs.
- Record scan events only to the extent appropriate and permitted.
- Do not treat a QR scan as proof that the customer is authenticated or that delivery occurred.
- Provide a fallback if the customer cannot use WhatsApp.
- Test QR readability on printed labels, invoices, and packaging at realistic sizes and lighting conditions.

### Suggested mobile landing page

**Headline:** “Your Feedback Builds a Better Tomorrow.”

Display five prominent buttons:

1. ⭐ Rate Your Experience
2. 🚚 Delivery Feedback
3. 📦 Product Catalogue
4. 🛠️ Report an Issue
5. 💬 Talk to Our Team

Keep the page mobile-first, fast-loading, and easy to use with minimal typing. Allow feedback without account creation wherever practical.

## 6. Real-Time Trigger and Automation Rules

The system should react to customer actions and confirmed business events rather than send repetitive generic messages.

| Trigger/event | Recommended action | Timing |
|---|---|---|
| Customer scans general QR | Open welcome menu | Immediately |
| Customer scans catalogue QR | Open product categories | Immediately |
| Order dispatched | Send dispatch notification if enabled | After dispatch confirmation |
| Delivery marked completed | Ask about delivery experience | Shortly after confirmation |
| Feedback rating is low | Ask relevant follow-up question | Immediately |
| Customer reports product damage | Create support ticket | Immediately |
| Complaint assigned to a team | Notify customer if appropriate | After assignment |
| Complaint marked resolved | Ask whether the issue was resolved satisfactorily | After resolution |
| Customer submits feedback | Send thank-you message | Immediately |
| Customer has not responded | Send at most one gentle reminder | After 24–48 hours, subject to consent and messaging rules |

### Team availability and routing

- If the customer requests a person, check the assigned team's working hours and availability when this data is maintained.
- Route the request to the appropriate team or person.
- If nobody is available, record the request and explain the next expected response window.
- Do not display a team member as available unless the system can reliably determine availability.
- Allow reassignment when the assigned person is unavailable or the request belongs to another department.

**Example unavailable message:**

> Our support team is currently unavailable. Your request has been recorded. We'll follow up during our next working hours.

Show this message only when the system can reliably determine team availability.

### Messaging and consent safeguards

- Obtain appropriate customer consent for WhatsApp and other nonessential messaging.
- Follow applicable WhatsApp Business Platform rules and approved-template requirements.
- Provide a clear way to stop nonessential messages.
- Avoid excessive reminders.
- Respect customer preferences and messaging windows.
- Do not send marketing messages merely because a customer submitted a service complaint.

## 7. Real-Time Feedback Dashboard

The internal dashboard should convert feedback into actions for relevant teams.

| Dashboard section | Information shown |
|---|---|
| Customer Satisfaction | Average rating and rating trends |
| Delivery Performance | On-time, delayed, and pending deliveries |
| Product Issues | Complaints by product and issue category |
| Customer Suggestions | Most common improvement requests |
| Open Complaints | Pending issues and assigned owners |
| Resolution Performance | Time to first response and time to resolution |
| Product Interest | Most-viewed categories and enquiry volume |
| Feedback Sources | QR scans and submissions by QR type |

### Suggested dashboard KPIs

- Total feedback submissions.
- Average customer rating.
- Rating distribution.
- Delivery feedback volume and satisfaction.
- Number of product complaints.
- Complaints by product and issue category.
- Open, assigned, in-progress, and resolved tickets.
- Average time to first response.
- Average time to resolution.
- Reopened complaint count, if supported.
- Most frequently selected improvement categories.
- Feedback submission rate from eligible customer interactions.
- QR scans versus completed feedback submissions, where measurement is supported.

### Example alert rules

- **Low product rating:** Notify the responsible quality or sales team.
- **Delivery complaint:** Route to dispatch or logistics.
- **Repeated complaint for the same product:** Flag for investigation.
- **Unassigned complaint:** Alert the supervisor after a configurable period.
- **Unresolved issue:** Follow up according to the agreed service target.

Keep feedback volume separate from resolution performance. A high number of submissions does not automatically mean customer satisfaction has improved.

### Suggested internal dashboard layout

1. **Top KPI cards:** Average rating, new feedback, open complaints, resolved complaints.
2. **Trend chart:** Satisfaction over time.
3. **Category chart:** Product, delivery, packaging, communication, and other issues.
4. **Complaint table:** Ticket ID, date, customer/order reference, product, issue, owner, priority, status.
5. **Recent comments:** Customer comments with suitable access controls.
6. **Filters:** Date range, product, customer/order reference, feedback source, issue category, team, owner, and status.
7. **Export:** Authorized users can export filtered records for operational review.

## 8. Complaint and Resolution Workflow

```text
Customer submits issue
        |
        v
Create ticket and reference number
        |
        v
Identify product/order/customer if possible
        |
        v
Categorize issue and set priority
        |
        v
Assign responsible team/person
        |
        v
Notify team and acknowledge customer
        |
        v
Investigate and update status
        |
        v
Resolve issue and record resolution
        |
        v
Ask customer whether the issue was resolved
        |
        +---- No ----> Reopen / escalate ticket
        |
       Yes
        |
        v
Close ticket and retain history
```

### Recommended ticket statuses

- `Open`
- `Assigned`
- `In Progress`
- `Waiting for Customer`
- `Resolved`
- `Closed`
- `Reopened`

Define status-transition rules so that ticket history remains consistent. For example, a customer response indicating that the issue persists should permit reopening or escalation.

## 9. Recommended System Architecture

The customer-facing experience should be simple. Internal functions can integrate with the existing Kalika ERP-style workflow.

```text
CUSTOMER
   |
   v
QR CODE / WHATSAPP LINK
   |
   v
CUSTOMER FEEDBACK INTERFACE
   |
   +---- Product Catalogue
   +---- Delivery Feedback
   +---- Product Complaints
   +---- General Suggestions
   |
   v
FEEDBACK API / BUSINESS LOGIC
   |
   +---- Customer & Order Lookup
   +---- Feedback Categorization
   +---- Team Assignment
   +---- Notifications
   |
   v
CENTRAL DATABASE
   |
   +---- Feedback Records
   +---- Complaint Tickets
   +---- Customer & Product References
   +---- Status & Resolution History
   |
   v
KALIKA ERP-STYLE DASHBOARD
   |
   +---- Sales
   +---- Quality
   +---- Dispatch
   +---- Customer Support
   +---- Management Reports
```

### Suggested technology components

- **Frontend:** React or Next.js.
- **Backend:** Django REST Framework or FastAPI.
- **Database:** PostgreSQL.
- **Messaging:** WhatsApp Business Platform.
- **QR codes:** QR generation with secure reference identifiers.
- **Notifications:** WhatsApp templates and email, where appropriate.
- **Analytics:** Dashboard integrated into the existing ERP-style interface.

These are suggested options, not requirements to replace the existing technology. Reuse existing customer, order, product, and user data wherever possible, subject to permissions and data quality.

### Integration considerations

- Integrate with the ERP to retrieve customer, order, product, and delivery data where supported.
- Use a stable order/invoice reference to associate feedback with a transaction.
- Avoid duplicate tickets when the same submission is retried.
- Keep a timestamped audit trail for assignment and status changes.
- Handle messaging or API failures without losing feedback.
- Restrict customer and employee data to authorized roles.
- Validate attachments and restrict access to uploaded photos.
- Make notifications retry-safe to prevent duplicate messages.
- Monitor failed integrations and unprocessed events.

## 10. Suggested Data Model

These are recommended logical entities; they are not a claim about the structure of the current ERP database.

### Feedback record

- Feedback ID
- Submission date/time
- Customer reference, if identified
- Order/invoice reference, if identified
- Product reference, if applicable
- Feedback source / QR type
- Interaction type: delivery, product, service, general
- Rating
- Feedback category
- Free-text comment
- Consent/preferences reference, where applicable
- Related ticket ID, if created

### Complaint ticket

- Ticket ID
- Created date/time
- Customer/contact reference
- Order/invoice reference, if available
- Product
- Issue category
- Customer description
- Attachment/photo reference
- Priority
- Assigned team/person
- Status
- Internal notes
- First-response timestamp
- Resolution timestamp
- Resolution summary
- Customer follow-up rating

### QR source record

- QR source ID
- QR type
- Placement/location
- Destination flow
- Associated product or order reference, if applicable
- Active/inactive status
- Created date
- Scan count, where measured appropriately

### Product catalogue reference

- Product ID or SKU
- Product name
- Category
- Catalogue image/document reference
- Approved description
- Available specifications
- Enquiry action
- Active/inactive status

Keep live prices, inventory, and delivery estimates linked to authoritative systems. Do not assume the catalogue PDF contains current live operational values.

## 11. Privacy, Access, and Reliability

- Collect only the information needed to process feedback or resolve the request.
- Explain why contact/order information is requested.
- Use secure references rather than personal data in QR URLs.
- Limit access to customer records, complaints, and attachments.
- Define data-retention and deletion policies appropriate to the business and applicable law.
- Keep a record of important status changes and assignments.
- Do not expose internal notes in customer-facing messages.
- Ensure that customer-visible ticket status does not reveal confidential employee or business information.
- Protect APIs with appropriate authentication, authorization, input validation, and rate limits.
- Use appropriate transport encryption and secure storage.
- Back up records and monitor integration failures.
- Provide a fallback for customers who do not use WhatsApp.

## 12. Implementation Roadmap

### Phase 1 — Feedback MVP

- QR landing page.
- Product catalogue access.
- Star ratings and comments.
- Delivery and product issue categories.
- Feedback storage.
- Basic internal dashboard.
- Basic ticket creation and status tracking.

### Phase 2 — Workflow Automation

- WhatsApp messaging.
- ERP customer and order lookup.
- Automatic complaint creation and assignment.
- Team availability and status notifications.
- Customer acknowledgements and relevant follow-ups.
- Delivery-event triggers.

### Phase 3 — Customer Intelligence

- Product-level feedback analysis.
- Recurring complaint detection.
- Delivery satisfaction trends.
- Customer suggestion analysis.
- Operational performance reporting.
- Trend-based alerts and improvement tracking.

## 13. Testing and Acceptance Checklist

### QR and customer experience

- [ ] Each QR type opens the correct flow.
- [ ] QR codes work on supported mobile devices.
- [ ] General QR codes do not falsely identify a customer.
- [ ] Order-specific QR references do not expose personal information.
- [ ] Catalogue categories and product links work.
- [ ] Customers can return to the main menu.
- [ ] Forms are mobile-friendly and require minimal typing.

### Feedback collection

- [ ] Ratings are saved correctly.
- [ ] Product and delivery feedback are categorized separately.
- [ ] Optional comments can be submitted.
- [ ] Low ratings trigger relevant follow-up questions.
- [ ] Duplicate submissions are handled appropriately.
- [ ] Feedback is associated with the correct order/product when identifiable.

### Complaints and routing

- [ ] Each complaint receives a ticket/reference ID.
- [ ] The correct team receives the ticket.
- [ ] Status changes are timestamped.
- [ ] Unassigned and overdue tickets can be identified.
- [ ] Attachments are safely stored and accessible only to authorized users.
- [ ] A customer can report that an issue remains unresolved.
- [ ] Resolved tickets trigger an appropriate follow-up when permitted.

### Messaging

- [ ] Approved templates are configured where required.
- [ ] Customer consent and opt-out preferences are respected.
- [ ] Failed messages can be retried safely.
- [ ] Reminders are limited and do not become repetitive.
- [ ] The system does not claim delivery, assignment, or resolution without a confirmed event.

### Dashboard and reporting

- [ ] KPI values match stored records.
- [ ] Filters return correct results.
- [ ] Ticket counts match ticket statuses.
- [ ] Feedback and resolution metrics are distinct.
- [ ] Exported data respects user permissions.
- [ ] Dashboard data refreshes at the intended frequency.

## 14. Final Recommended Customer Journey

**Scan QR → Choose an option → Answer 1–3 relevant questions → Submit feedback → Get assistance if needed → Receive a thank-you message.**

Keep the interaction short, make each button useful, and route complaints to a real person. The system should help Kalika Enterprises understand what customers experience, resolve issues systematically, and use recurring feedback to improve products and service.

## 15. Important Implementation Notes

1. The product list above is based on the supplied Kalika Enterprises catalogue.
2. The messages are ready-to-use drafts; the selected messaging platform may require formatting changes and approved templates.
3. QR codes, live order lookup, customer identification, staff availability, notifications, and dashboard metrics require implementation and integration; they do not operate automatically just because the message text is defined.
4. Technology selections are recommendations and should be reconciled with the existing ERP stack before implementation.
5. Establish ownership, response targets, consent practices, and data-retention rules before production launch.

---

## 16. WhatsApp Template & Follow-Up Messaging System — Overview

> Scope: ready-to-use WhatsApp text templates **with attachments**, click-to-send (`wa.me`) deep links,
> category-wise follow-up flows, action→intent→metric mapping for the dashboard, and the Python API
> sync layer (Gemma + Gemini Flash model chain) with task/subtask selection and a regular feedback loop.
> **QR-based sharing is NEXT SCOPE — the current build sends messages only (see 16.9).**
> Built from current live samples: 376 unique contact phones, 9 months of sales registers (5,149 invoices,
> ₹27.58 Cr gross, 124 customers), 48 WhatsApp chat exports, the 13-product rate list, and the
> Kalisoft AI Sales Pipeline FastAPI service (`kalisoft-sales`, asia-south1).

### 16.1 End-to-End Flow (ASCII)

```text
+------------------------- DATA SOURCES (gs://kalika_enterprises) -------------------------+
| sales-contacts/ (376 phones) | kalika_sales2026/ (5,149 invoices) | kalika backup/ (48   |
| WhatsApp chats)              | ERP-V1/Reports/ (orders/dispatch)  | sales-metadata/ docs |
+-------------------------------------------+------------------------------------------------+
                                            v
                              CONTACT & CONTEXT RESOLVER
                              (dedupe phone -> customer/lead,
                               last call status, last order, rates)
                                            v
+-------------------------------- TEMPLATE ENGINE ----------------------------------------+
| Category templates (follow-up / rates / catalogue / order / delivery / payment / expo)   |
|   + variables {name} {company} {product} {rate} {order_no}                               |
|   + attachment picker (catalogue PDF, rate sheet, calc sheet, profile PDF, logo)         |
+-------------------------------------------+----------------------------------------------+
                                            v
                               AI PERSONALIZATION (Python API)
                    POST /api/llm/run  {task, subtask, model_pref}
              model chain: gemma-3-27b-it -> gemma-3-12b-it
                           -> gemini-2.5-flash -> gemini-2.0-flash
              (user selects task & subtask; safe placeholder fallback)
                                            v
+------------------------------ SEND CHANNELS (2 options) ---------------------------------+
| A) CLICK-TO-SEND: https://wa.me/<phone>?text=<urlencoded msg + doc link>                 |
|      -> opens WhatsApp directly with message in the send box (agent taps Send)           |
| B) API SEND: POST /api/whatsapp/send (wechaty gateway) / POST /api/social/whatsapp/      |
|      messages (queue) -> supports media attachments & automation                         |
+-------------------------------------------+----------------------------------------------+
                                            v
                                   CUSTOMER REPLIES / EVENTS
                          POST /api/whatsapp/webhook (inbound capture)
                                            v
+----------------------------------- FEEDBACK LOOP ----------------------------------------+
| intent classify (Gemma) -> update contact status -> recommend next action                 |
| -> schedule follow-up (/api/events/messages/send-due, /api/scheduler/run)                 |
+-------------------------------------------+----------------------------------------------+
                                            v
                            DASHBOARD METRICS  (/api/kpi/* + feedback KPIs)
              delivery rate | reply rate | intent mix | conversion | rating | resolution
```

### 16.2 Attachment (Document) Library

| Doc ID | Document | GCS path | Public link used inside messages | Used with template categories |
|---|---|---|---|---|
| DOC-CAT | Product catalogue PDF | `ERP-V1/New_kalika_enterprises_catalog.pdf` | `https://storage.googleapis.com/kalika_enterprises/ERP-V1/New_kalika_enterprises_catalog.pdf` | catalogue, follow-up, expo |
| DOC-RATE | Rate list (13 products) | `sales-contacts/pune region contacts (1).xlsx` → sheet `Products details` | share as text block in message (rates below) | rates, quotation |
| DOC-POLY | Poly bag calculation sheet | `sales-metadata/POLY BAG CALACULATION SHEET.xlsx` | `https://storage.googleapis.com/kalika_enterprises/sales-metadata/POLY%20BAG%20CALACULATION%20SHEET.xlsx` | quotation, rates |
| DOC-PROF | Company profile | `kalika backup/KALIKA.pdf` | `https://storage.googleapis.com/kalika_enterprises/kalika%20backup/KALIKA.pdf` | first-touch, expo |
| DOC-FEAT | ERP/app features | `ERP-V1/software-docs/Kalika_Feat.pdf` | `https://storage.googleapis.com/kalika_enterprises/ERP-V1/software-docs/Kalika_Feat.pdf` | product/ERP demos |
| DOC-LOGO | Brand logo | `docs/Ecom/kalika logo.jpeg` | `https://storage.googleapis.com/kalika_enterprises/docs/Ecom/kalika%20logo.jpeg` | all (branding) |
| DOC-DASH | Data dashboard summary | `sales-metadata/Kalika_Dashboard_Summary.xlsx` | `https://storage.googleapis.com/kalika_enterprises/sales-metadata/Kalika_Dashboard_Summary.xlsx` | internal reviews |

> Note: `wa.me` links carry **text only** — attachments are shared as the secure HTTPS doc links above inside the
> message body. True media attachments (PDF/image as WhatsApp media) go through the API channel
> (`POST /api/whatsapp/send` / gateway) which supports media payloads.

### 16.3 Message Template Catalog (by category, with variables + attachment)

Variables: `{name}` contact person · `{company}` · `{product}` · `{rate}` · `{order_no}` · `{doc_link}` · `{agent}`

| ID | Category | Intent | Template text (paste-ready) | Attachment |
|---|---|---|---|---|
| WA-FU-01 | Follow-up — Not answered (59+17 cases in lists) | re-engagement | "Namaste {name} ji, this is {agent} from Kalika Enterprises (Ahmednagar). Tried reaching you regarding packaging materials — stretch film, BOPP tape, VCI bags, polybags. Sharing our catalogue: {doc_link}. Please reply YES for a callback or send your requirement here." | DOC-CAT |
| WA-FU-02 | Follow-up — Busy / call later (25+ cases) | re-engagement | "Namaste {name} ji, following up as requested. Kalika Enterprises — manufacturer of stretch film ₹168/kg, BOPP tape ₹30–32/pc, VCI bags ₹182/kg. Rate list & catalogue: {doc_link}. When can I call for 2 minutes?" | DOC-CAT, DOC-RATE |
| WA-FU-03 | Follow-up — Details already sent (Sheet11: 13/22 'Details sent') | nurture | "Namaste {name} ji, earlier we shared Kalika Enterprises product details. Checking if you need current rates or samples for {product}. Polybag calc sheet for reference: {doc_link}. Happy to send a quotation today." | DOC-POLY |
| WA-RT-01 | Rate share (rates seen in order chats) | conversion | "Namaste {name} ji, current Kalika rates — Stretch film 23–51 mic ₹168/kg · VCI bags 50 mic ₹182/kg · Regular polybags ₹170–172/kg · Printed polybags ₹182/kg · BOPP tape 2\" ₹30–32/pc · Hand gloves 40/60/80 gm ₹6.50/8/9–9.50 per pc. GST extra. Order on WhatsApp or reply for PI." | DOC-RATE |
| WA-QT-01 | Quotation follow-up (quotation sent log) | conversion | "Namaste {name} ji, gentle reminder on the Kalika quotation shared for {product}. Prices valid this week. Reply 1 to confirm, 2 to revise quantity, 3 for a call." | DOC-POLY |
| WA-ORD-01 | Order update (order group: 186 order msgs) | retention | "Namaste {name} ji, your Kalika order {order_no} update: {status}. Expected dispatch: {date}. Any change in quantity, reply before 5 PM today. — {agent}" | — |
| WA-DSP-01 | Dispatch update (ERP: 44 partially dispatched) | retention | "Namaste {name} ji, dispatch update for {order_no}: {dispatched_qty} of {schedule_qty} sent today. Balance {balance} planned for {next_date}. E-way/invoice copy: {doc_link}" | invoice/challan link |
| WA-PAY-01 | Payment reminder (45-day terms = 859 invoices) | collections | "Namaste {name} ji, gentle payment reminder from Kalika Enterprises — invoice {order_no} ({amount}) is due as per {terms} terms. Please share UTR once done. Thank you!" | invoice link |
| WA-FBK-01 | Feedback welcome (spec Message 1) | feedback | "👋 Hello from Kalika Enterprises! How can we help today? 📦 Catalogue · 🚚 Delivery Status · ⭐ Feedback · 🛠️ Report Issue · 💬 Talk to Team. Your feedback matters!" | DOC-CAT |
| WA-FBK-02 | Delivery feedback (spec Message 2) | feedback | "🚚 How was your recent Kalika delivery? ✅ On time · ⏳ Late · 📦 Not received · 🤝 Delivery-team feedback. Tap to reply — 10 seconds only." | — |
| WA-EXP-01 | Expo follow-up (Packvision: 111 leads) | re-engagement | "Namaste {name} ji, thank you for visiting Kalika Enterprises at Packvision. As discussed, sharing catalogue + rates: {doc_link}. Can we send samples of {product} this week?" | DOC-CAT, DOC-PROF |
| WA-NEW-01 | First touch (main list: 152 companies) | acquisition | "Namaste {name} ji, {agent} from Kalika Enterprises, Ahmednagar — packaging manufacturer (stretch/shrink film, BOPP & masking tape, VCI, tarpaulin, HDPE/poly bags, gloves). Profile: {doc_link}. Any current requirement?" | DOC-PROF |

### 16.4 Click-to-Send (wa.me) Deep-Link Spec

```text
FORMAT:   https://wa.me/<country_code><phone>?text=<urlencoded(template_text + "\n\n" + doc_link)>
EXAMPLE (WA-RT-01 to +91 98220 00000):
https://wa.me/919822000000?text=Namaste%20Patil%20ji%2C%20current%20Kalika%20rates%20%E2%80%94%20Stretch%20film%20%E2%82%B9168%2Fkg%20%C2%B7%20VCI%20bags%20%E2%82%B9182%2Fkg%20...%20Catalogue%3A%20https%3A%2F%2Fstorage.googleapis.com%2Fkalika_enterprises%2FERP-V1%2FNew_kalika_enterprises_catalog.pdf
```

| Field | Rule |
|---|---|
| phone | 10+ digits, country code, no `+`/spaces (source: 376 unique phones in marketing lists) |
| text | URL-encoded; keep < 1000 chars; emoji allowed |
| attachment | as `https://storage.googleapis.com/...` link inside text (wa.me cannot attach files) |
| behavior | opens WhatsApp app/web directly on the send screen — agent reviews and taps **Send** |
| fallback | invalid numbers (90+ in lists) are filtered before link generation |

### 16.5 Actions → Intent → Dashboard Metrics (recommendation set)

| # | Action (trigger) | Template | Intent class | Primary metric | Secondary metrics | Data source |
|---|---|---|---|---|---|---|
| 1 | Call outcome = not answered → send WA-FU-01 within 2h | WA-FU-01 | re-engagement | reply rate % | callback booked, link clicks | contacts call status (174) |
| 2 | Call outcome = busy/call later → WA-FU-02 next day 10 AM | WA-FU-02 | re-engagement | callback rate % | time-to-callback | call logs (25+) |
| 3 | Details sent ≥3 days ago, no reply → WA-FU-03 | WA-FU-03 | nurture | requirement confirmed % | quotation requests | Sheet11 (13 leads) |
| 4 | Rate requested (chat keyword 'rate') → WA-RT-01 instantly | WA-RT-01 | conversion | quotation sent count | order conversion % | WhatsApp rate threads |
| 5 | Quotation sent +7 days → WA-QT-01 | WA-QT-01 | conversion | quote→order % | revision requests | calling log (Sheet3) |
| 6 | New order in ERP → WA-ORD-01 | WA-ORD-01 | retention | ack rate % | change requests | ERP Orders (89, 10 new) |
| 7 | Partial dispatch in ERP → WA-DSP-01 | WA-DSP-01 | retention | customer ack % | balance-clearance days | Dispatch (44 partial) |
| 8 | Invoice age > terms (45d=859, 60d=384 invoices) → WA-PAY-01 weekly | WA-PAY-01 | collections | collected-in-week % | overdue ageing | sales registers |
| 9 | Delivery completed → WA-FBK-02 after 4h | WA-FBK-02 | feedback | feedback response % | avg rating | dispatch events |
| 10 | Expo lead imported (Packvision 111) → WA-EXP-01 in 24h | WA-EXP-01 | re-engagement | sample-request rate % | meeting booked | events module |
| 11 | New contact added (main list 152) → WA-NEW-01 | WA-NEW-01 | acquisition | first-reply % | opt-out % | contacts module |
| 12 | Low rating / issue words → create ticket + notify team | (spec Msg 4) | support | first-response time | resolution time, reopen % | feedback module |

### 16.6 Python API Sync — Model Chain with User-Selected Task/Subtask

```text
Dashboard UI (user picks):
  TASK     = follow_up | rates | order_update | feedback | payment | expo
  SUBTASK  = template_id (WA-FU-01...) + audience filter + tone (formal/casual/marathi)
      |
      v
GET  /api/llm/tasks            -> list available tasks
GET  /api/llm/plan/{task}      -> show plan (prompt, inputs, outputs) before running
POST /api/llm/run              -> {task, subtask, contacts[], model_pref}
      |
      v
Model chain (gemma_service.py):  gemma-3-27b-it -> gemma-3-12b-it
                                 -> gemini-2.5-flash -> gemini-2.0-flash
                                 -> safe placeholder fallback (always sendable)
      |
      v
Personalized messages -> review table -> per-row [wa.me OPEN-AND-SEND] button
                                     or POST /api/social/whatsapp/messages (queue)
                                     or POST /api/whatsapp/send (gateway, media OK)
```

| API | Purpose | Dashboard usage |
|---|---|---|
| `GET /api/llm/tasks` | list AI tasks | task dropdown |
| `GET /api/llm/plan/{task}` | preview plan | "what will happen" panel |
| `POST /api/llm/run` | run personalization (Gemma→Flash chain) | generate batch |
| `POST /api/social/whatsapp/messages` | queue messages | bulk send queue |
| `POST /api/whatsapp/send` | direct gateway send (supports media) | single/attachment send |
| `POST /api/whatsapp/webhook` | inbound replies | feedback loop input |
| `GET /api/kpi/outreach` | send/open/reply KPIs | outreach tiles |
| `POST /api/events/messages/send-due` | send scheduled follow-ups | daily batch |

### 16.7 Feedback Loop — Regular Execution

```text
        +----------------------+        every night (POST /api/cron/run)
        |  COLLECT             |<------- webhook replies, call logs, ERP events,
        |  (replies/events)    |         quotation responses, payments
        +----------+-----------+
                   v
        |  CLASSIFY            |  Gemma intent classification:
        |  intent + sentiment  |  interested / not-interested / rate-request /
        +----------+-----------+  order-query / complaint / payment-done / wrong-number
                   v
        |  UPDATE STATE        |  contact status, last-intent, next-best-action,
        |                      |  ticket create/close, opt-out honored
        +----------+-----------+
                   v
        |  ACT                 |  schedule next follow-up (max 1 reminder / 24–48h),
        |                      |  escalate complaints, push due messages (send-due)
        +----------+-----------+
                   v
        |  MEASURE             |  /api/kpi/* refresh: reply rate, intent mix,
        +----------------------+  conversion, feedback rating, resolution time
                   |
                   +----> loops back to COLLECT (daily cadence, weekly review)
```

| Cadence | Job | Endpoint |
|---|---|---|
| Real-time | inbound reply → intent + ticket/route | `POST /api/whatsapp/webhook` |
| Hourly | send due scheduled follow-ups | `POST /api/events/messages/send-due` |
| Nightly | full sync: contacts, replies, ERP status → recompute next actions | `POST /api/cron/run` |
| Weekly | payment reminders (WA-PAY-01), quotation ageing (WA-QT-01) | `POST /api/scheduler/run` |
| Monthly | template performance review → retire/rewrite low performers | governance + KPI review |

### 16.8 Dashboard Metric Tiles (powered by the loop)

| Tile | Metric | Source of truth |
|---|---|---|
| Outreach | messages sent / delivered / replied today | whatsapp gateway + webhook |
| Intent mix | interested vs not-interested vs rate-request vs complaint | Gemma classification |
| Follow-up health | due follow-ups, overdue, completed | events scheduler |
| Conversion | quotations sent → orders won (%) | ERP orders + calling log |
| Collections | overdue invoices, collected-this-week | sales registers |
| Satisfaction | avg rating, complaints open/resolved, resolution time | feedback module |
| Channel | wa.me clicks vs API sends vs replies | outreach KPIs |
| Model | Gemma vs Flash usage, fallback count, cost | `/api/kpi/costs`, `/api/governance/usage` |

> Implementation order: (1) template catalog + wa.me generator using current contact lists → (2) webhook +
> intent classification loop → (3) scheduler cadence → (4) KPI tiles. Templates above are drafts from real
> samples — verify WhatsApp Business template approval + consent before automated sending.

### 16.9 Build Status — 30-Oct-2026 (pipeline build started)

**LIVE NOW — customer feedback triggering pipeline** (`/api/pipeline/*`, FastAPI `kalisoft-sales`):

```text
 USER selects SEGMENT (card)            USER selects TEMPLATE (dropdown)
  recent_orders | new_customers | leads   e.g. WA-FU-01 / WA-RT-01 / WA-ORD-01
                 |                            |
                 v                            v
        POST /api/pipeline/preview  -> personalised messages + wa.me link per row
                 |
                 +--> per-row "Open WhatsApp" (wa.me) -> agent taps Send   [SEND PATH A]
                 |
                 +--> POST /api/pipeline/queue -> whatsapp_messages        [SEND PATH B]
                      (status=pending, human-reviewed send path)
```

| Item | Status | Detail |
|---|---|---|
| Segment: recent orders | LIVE | 89 ERP orders loaded from latest ERP-V1 report; 22 matched to contact phones (auto company-name match) |
| Segment: new customers | LIVE | 473 reachable (GCS contact sync, last 7 days, with phone) |
| Segment: leads | LIVE | 477 reachable (call-status / requirement notes; sorted not-answered -> busy -> call-later -> details-sent) |
| Template selection by user | LIVE | 11 templates across segments (WA-ORD-01, WA-FBK-01/02/06, WA-NEW-01/02, WA-FU-01/02/03, WA-RT-01, WA-EXP-01) |
| Personalised messages | LIVE | Variables {name} {company} {order_no} {amount} {status} {rates} {doc links}; agent name from session |
| Send via wa.me click-to-send | LIVE | Per-row link opens WhatsApp with message ready; invalid/landline numbers flagged "no phone" |
| Send via reviewed queue | LIVE | `POST /api/pipeline/queue` -> `whatsapp_messages` (pending) |
| UI | LIVE | "Feedback pipeline" tab — segment cards, template dropdown, preview table, mobile + desktop responsive |
| Attachments | LIVE (as links) | catalogue / profile / poly-calc docs shared as secure GCS links inside message text |
| **QR-based sharing** | **NEXT SCOPE** | QR entry points (general/delivery/product), scan analytics, print-ready QR sheets — not in this build |
| WhatsApp Business API auto-send | NEXT SCOPE | Template approval + unattended sending; current build keeps human tap-to-send |
| ERP live lookup | NEXT SCOPE | Direct ERP API; current build reads the latest published ERP report snapshot |

New endpoints: `GET /api/pipeline/segments` · `GET /api/pipeline/templates?segment=` ·
`POST /api/pipeline/preview` · `POST /api/pipeline/queue` · `GET /api/pipeline/queue`

Next scope queue: (1) QR generation + scan tracking per section 5; (2) Gemma/Flash auto-personalisation
per contact (chain ready in `gemma_service.py`); (3) webhook intent classification driving next-best-action;
(4) WhatsApp Business API template approval for unattended sending.

---

## 17. Backend Crons, Interaction Dump & Graph Pre-Processing — 30-Oct-2026 Update

### 17.1 Updated cron set (backend scheduler)

`POST /api/cron/run` now sweeps **11 registered tasks** (scheduler backend: in-memory locally, Redis in
production; Cloud Scheduler → `/api/scheduler/run` on cron expressions):

| Cron task | Schedule | Purpose |
|---|---|---|
| sync_gcs_contacts | `0 */6 * * *` | Import contacts from GCS bucket |
| refresh_email_connections | `*/30 * * * *` | Re-test IMAP/SMTP connections |
| linkedin_hiring_alerts / reddit_hiring_alerts | `0 8 * * *` | Daily hiring-signal sweeps |
| youtube_signal_scan | `0 9 * * *` | YouTube signal scan (future) |
| whatsapp_reminders | `0 10 * * *` | Queue follow-up reminders |
| events_whatsapp_due | `*/15 * * * *` | Dispatch due event messages |
| **pipeline_feedback_due** | `0 * * * *` | **NEW** — send-due pass over feedback-pipeline queue (recent orders / new customers / leads) |
| **build_interaction_dump** | `0 2 * * *` | **NEW** — parse chat exports + app outbox → `interaction_dump.json` (with attachment details) |
| **rebuild_graph_preprocessing** | `30 2 * * *` | **NEW** — networkx graph build → nodes/edges/gexf (future graph DB) |
| kpi_snapshot | `0 23 * * *` | Nightly KPI snapshot |

### 17.2 Interaction dump (mails + chats → JSON)

`scripts/build_interaction_dump.py` → `gcs_data/interaction_dump.json`. First run stats:

| Metric | Value |
|---|---|
| Chat exports parsed (kalika backup/) | **85 chats** |
| Total messages | **4,419** |
| Unique participants | **89** |
| Attachments catalogued (name + size + media type) | **528** (420 images · 52 documents · 48 contact cards · 7 videos · 1 audio) |
| `<Media omitted>` references in texts | 1,056 |
| Outbound interactions (app whatsapp_messages queue) | 27 |

Each chat entry: `chat, file, gcs path, participants, message_count, date_range, messages[{date,time,sender,text,has_media,attachments_inline}], attachments[{name,size_bytes,media_type}]`.
Each mail entry (normalised): `type, subject, from, to, date, body_preview(200), attachments[{name,size_bytes,media_type}], source`.

```text
 kalika backup/*.zip ──┐
                       ├──> parse (WA text regex + zip listing) ──> interaction_dump.json
 app outbox (sqlite) ──┘                    + classify media         (chats[] + mails[] + stats)
```

### 17.3 Graph pre-processing (networkx) — future graph-database scope

`sales_fastapi/graph_build.py` + `scripts/rebuild_graph.py` → `gcs_data/graph/{nodes.json, edges.json, graph.gexf, graph_stats.json}`.

Current numbers (first build, 30-Oct-2026):

| Metric | Value |
|---|---|
| Nodes | **9,123** (contact 8,795 · domain 222 · intent 6 · chat_thread 85 · erp_customer 15) |
| Edges | **9,419** (CONTACT_HAS_INTENT 8,795 · CONTACT_IN_DOMAIN 611 · ORDER_BY_CONTACT 13 · CHAT_MAPS_TO_CONTACT 0*) |
| Density / components | 0.000113 / 88 weakly-connected |
| Top hubs | intent:general (8,574) · domain:gmail.com (307) · intent:procurement (68) · intent:sales (65) · domain:cummins.com (21) |

*Chat→contact phone mapping produced 0 edges on first run — chat titles carry counterparty numbers that are not yet
contacts; improving this mapping is queued work.

```text
 contacts (8,795) ──HAS_INTENT──> intent nodes (6)
        │
        ├──IN_DOMAIN──> domain nodes (222)            networkx DiGraph
        │                                                    │
 chat threads (85) ──MAPS_TO──> contact (by phone)          v
 erp customers (15) ──BY_CONTACT──> contact (company)   nodes.json + edges.json
                                                         + graph.gexf ──> FUTURE: Neo4j/Neptune
```

**Future scope (graph DB):** load GEXF into Neo4j/Neptune; add REPLIED_TO edges from webhook replies;
MESSAGE_ABOUT product nodes; centrality-based lead scoring; community detection for account clusters.

### 17.4 Tests

`tests/test_graph_and_dump.py` — **10 tests passing** (venv pytest): chat parsing (incl. multi-line continuation +
inline attachment markers + media-omitted), media classification, zip reading, mail-record normalisation with
attachment details, dump stats, phone normalisation (landline rejection for wa.me), template fill + link build,
template catalog integrity, graph build (incl. placeholder-domain exclusion), graph stats + GEXF export.

---

## 18. ERP-Through-Sales, Forecast & Refined UI — 30-Oct-2026

Companion doc: `sales-metadata/Kalika_ERP_Sales_Integration.md` (subtasks, ASCII flows, roles, future stories).

### 18.1 Daily ERP sync (ERP untouched)

```text
ERP app (D:\KaliSoftAI\ERP-System, deployed branch master — NOT modified)
   -> publishes gs://kalika_enterprises/ERP-V1/Reports/kalika_report_YYYY-MM-DD.xlsx
   -> cron erp_dispatch_sync (0 6 * * *)  -> POST /api/erp/sync (admin)
   -> sales DB: erp_dispatch + erp_orders (+ sync_runs audit)
   -> sales dashboard: /api/erp/{status,analytics,dispatch,orders,forecast,rate-calculator}
```

First sync (2026-10-30): **117 dispatch rows** (73 Completed, 44 Partially Dispatched), 69,538 scheduled /
46,405 dispatched (66.7%), **52 customers**, **89 orders ₹94.83 L**, 44 pending follow-ups.

### 18.2 Access model

- **Admin** `ai.solutions@kalisoftai.in` (`ADMIN_EMAILS`): sync, YouTube keys, all reads.
- **Field executive / sales**: read-only dashboards (verified: sync → 403, reads → 200 with `is_admin:false`).
- **ERP users**: unchanged, strictly on the ERP app branch `master`.

### 18.3 New endpoints

| Method | Endpoint | Access |
|---|---|---|
| GET | /api/erp/status | user |
| POST | /api/erp/sync | admin |
| GET | /api/erp/dispatch · /orders · /forecast · /analytics | user |
| POST | /api/erp/rate-calculator | user |
| GET/PUT | /api/erp/settings | admin |
| GET | /api/erp/youtube/status | user |
| POST | /api/erp/youtube/sync | admin |

### 18.4 Refined UI (ERP-aligned, mobile + desktop)

- Inter typography, amber brand (`#f59e0b`), 18px card radius, hover lift, tabular numerals.
- New **ERP & forecast** page: KPI strip, funnel (orders → value → scheduled → dispatched), forecast bars +
  next-month projection, top customers, **daily rate calculator**, YouTube channel-sync card (admin entry,
  manual key add), dispatch table with status filter.
- Mobile breakpoints: 2-col KPI at ≤1100px, 1–2 col at ≤700px/420px, compact topbar, touch-sized controls.
- Existing pages untouched functionally; design tokens apply globally.

### 18.5 YouTube

- Data API v3 channel stats: LIVE (`POST /api/erp/youtube/sync`, daily 07:00 cron).
- Analytics API (watch time / traffic sources): **next scope** — requires OAuth consent + refresh-token storage.

### 18.6 Future scope (tracked as UI stories)

1. YouTube Analytics OAuth.
2. RL/graph event metadata (`events.jsonl`) → pattern reports (template → reply → repeat order lift).
3. Mobile push summary of dispatch slippage.
4. Gemma/Gemini model selection per action with human review gate.

---

## 19. Deploy Guardrails, Model Selection & ERP-UAT Window — 30-Oct-2026

Runbook: `sales-metadata/Kalika_Sales_Deploy_UAT_Runbook.md`.

### 19.1 Guardrail layers (daily preflight)

`GET /api/ops/preflight` (admin) and `POST /api/ops/run-checks` (persists to `sync_runs`).
Layers: **config · security · auth · data · erp · scheduler · llm · uat · storage** — each check returns
`pass/warn/fail` + remediation. **Current: 21 pass · 1 warn (LLM_ENABLED=false) · 0 fail → READY.**

### 19.2 Models with human verification

Default **`gemini-2.5-flash`**; Gemma **`gemma-4-27b-it`**; fallbacks `gemini-2.0-flash(-lite)`; local
`qwen2.5:3b` offline. `HUMAN_REVIEW_REQUIRED=true` for every customer-facing send. Catalog:
`GET /api/ops/models`.

### 19.3 Daily window 20:00–22:00 IST (14:30–16:30 UTC)

| Job | IST | UTC |
|---|---|---|
| daily_guardrail_checks | 20:00 | `30 14 * * *` |
| daily_llm_prompt_refine | 21:00 | `30 15 * * *` |
| daily_uat_report | 22:00 | `30 16 * * *` |
| weekly_uat_review | Mon 20:00 | `30 14 * * 1` |

17 cron tasks total; ERP master remains prod and read-only for us.

### 19.4 Customer journey collection

Stages: awareness → interest → evaluation → purchase → onboarding → retention → advocacy.
Patterns: new_customer · repeat_customer · at_risk · high_value (detect + next-action template per stage).
Endpoints: `POST /api/journey/event`, `GET /api/journey/{stories,behaviours,patterns,summary}`.
UI: **UAT & ops** page shows stories with next action and feedback prompt.

### 19.5 Prompt samples (JSON, weekly refined)

`gs://kalika_enterprises/sales-metadata/weekly_prompts.json` (also `GET /api/ops/prompt-samples`,
local-first with GCS realtime fallback). Five samples (PR-01..PR-05) each with template, variables,
sample input and expected output — viewable and testable in the UAT page.

### 19.6 UAT (one week)

`DEPLOY_ENV=preprod`, `UAT_ENABLED=true`, `UAT_ENABLED_UNTIL=2026-11-06`. Enabled features visible via
`GET /api/ops/uat`: ERP dashboards, forecast, rate calculator, feedback pipeline (human review),
journey + stories, YouTube Data API. Next scope: YouTube Analytics OAuth, RL pattern suggestions.

---

## 20. Voice Transcription & Gemma SLM Pipeline — 30-Oct-2026

Dedicated doc: `sales-metadata/Kalika_Voice_Transcription_SLM.md`.

- **Source:** `gs://kalika_enterprises/call_recording/Vaishnavi-samp/` (3 files, 167.9 s total).
- **Layers:** L0 audio probe (ffmpeg: duration/volume/silence) → L1 transcribe (Gemini flash audio)
  → L2 context → L3 tone → L4 lead extraction.
- **Provider chain:** **Gemma SLM (Ollama) → Gemini 2.5 Flash → heuristic**, mode recorded per record.
- **API-only:** `/api/voice/{status,files,providers,transcribe,ingest,transcripts,stats}` +
  `POST /api/voice/provision/{id}` (contact + journey event).
- **Scheduler:** `voice_transcription_sync` 09:00 IST (`30 3 * * *`); executor `scripts/voice_sync.py`.
- **Live:** audio probed for all 3 files (`pending_ai` until `GEMINI_API_KEY`), demo ingest produced
  lead (VCI bags, 500 kg, phone 9822000000), tone positive/high urgency, contact 8796 + journey
  stage `evaluation`, template `WA-ORD-01`.
- **Enable Gemma:** run Ollama + `ollama pull gemma-4-27b-it`, set `VOICE_SLM_FIRST=true`,
  `VOICE_SLM_MODEL=gemma-4-27b-it`, `LLM_LOCAL_BASE_URL`, and `GEMINI_API_KEY` for audio transcription.
- **Tests:** 14 voice tests (probe, layers, Gemma chain, fallbacks, ingest, provisioning, stats);
  full backend suite: **142 passing**.
