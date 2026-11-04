"""Default outreach templates for Kalisoft AI products.

Seeded per user on demand. Placeholders use ``{{...}}`` and are rendered from the
contact record (name, company, intent, ...) plus sender context.
"""

from __future__ import annotations

CHANNELS = ["email", "whatsapp", "linkedin", "wechat"]
STRATEGIES = ["cold_outreach", "follow_up", "nurture", "proposal", "closing", "re_engage"]
FUNNEL_STAGES = ["awareness", "interest", "consideration", "decision", "retention"]

SENDER = {
    "sender_name": "Kalisoft AI",
    "sender_email": "ai.solutions@kalisoftai.in",
    "product": "Kalisoft AI Sales Automation",
    "calendar_link": "https://kalisoftai.in/demo",
}

DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "Cold outreach — AI sales automation",
        "channel": "email",
        "strategy": "cold_outreach",
        "funnel_stage": "awareness",
        "subject": "{{company}} — automating your outbound with AI?",
        "body": (
            "Hi {{name}},\n\n"
            "I work with {{company}}'s peers on {{product}}. We help sales teams "
            "discover leads, personalise outreach and follow up automatically — so "
            "reps spend time on conversations, not busywork.\n\n"
            "Would a 15-minute walkthrough be useful? {{calendar_link}}\n\n"
            "Warm regards,\n{{sender_name}}"
        ),
    },
    {
        "name": "Cold outreach — procurement AI",
        "channel": "email",
        "strategy": "cold_outreach",
        "funnel_stage": "awareness",
        "subject": "Smarter procurement sourcing for {{company}}",
        "body": (
            "Hi {{name}},\n\n"
            "{{company}} sources across many suppliers. Our procurement AI agent "
            "consolidates supplier discovery, RFQ drafting and follow-ups into one "
            "assistant.\n\n"
            "Open to a short demo? {{calendar_link}}\n\n{{sender_name}}"
        ),
    },
    {
        "name": "Follow-up — after no reply",
        "channel": "email",
        "strategy": "follow_up",
        "funnel_stage": "interest",
        "subject": "Re: {{company}} + AI sales automation",
        "body": (
            "Hi {{name}},\n\n"
            "Just circling back on my note. Most teams start with one workflow — "
            "lead discovery or automated follow-ups — and expand from there.\n\n"
            "Is this a priority for {{company}} this quarter?\n\n{{sender_name}}"
        ),
    },
    {
        "name": "Value nurture — SLM case study",
        "channel": "email",
        "strategy": "nurture",
        "funnel_stage": "consideration",
        "subject": "How a mid-market team cut outreach cost 60% with small models",
        "body": (
            "Hi {{name}},\n\n"
            "Short read: by routing routine tasks to small language models and only "
            "escalating to large models when needed, a sales team cut inference cost "
            "60% while keeping reply quality.\n\n"
            "Happy to share the playbook for {{company}}.\n\n{{sender_name}}"
        ),
    },
    {
        "name": "WhatsApp intro — quick hello",
        "channel": "whatsapp",
        "strategy": "cold_outreach",
        "funnel_stage": "awareness",
        "subject": "",
        "body": (
            "Hi {{name}}, this is {{sender_name}}. We help companies like {{company}} "
            "automate lead discovery and follow-ups with AI. May I share a 1-page overview?"
        ),
    },
    {
        "name": "WhatsApp follow-up — demo nudge",
        "channel": "whatsapp",
        "strategy": "follow_up",
        "funnel_stage": "interest",
        "subject": "",
        "body": (
            "Hi {{name}}, following up on the AI sales automation overview. "
            "Would tomorrow or Thursday suit a quick 15-min demo? — {{sender_name}}"
        ),
    },
    {
        "name": "LinkedIn connect — procurement",
        "channel": "linkedin",
        "strategy": "cold_outreach",
        "funnel_stage": "awareness",
        "subject": "Connect",
        "body": (
            "Hi {{name}}, I help procurement teams at {{company}}'s scale automate "
            "supplier discovery and RFQ follow-ups. Would value connecting."
        ),
    },
    {
        "name": "LinkedIn follow-up — share resource",
        "channel": "linkedin",
        "strategy": "nurture",
        "funnel_stage": "consideration",
        "subject": "",
        "body": (
            "Thanks for connecting, {{name}}. Sharing a short overview of how AI "
            "agents streamline {{company}}'s sourcing-to-outreach flow. Happy to discuss."
        ),
    },
    {
        "name": "WeChat intro — AI agent demo",
        "channel": "wechat",
        "strategy": "cold_outreach",
        "funnel_stage": "awareness",
        "subject": "",
        "body": (
            "Hi {{name}}, {{sender_name}} here. We build AI sales agents for "
            "discovery, outreach and follow-up. Would you like a quick demo for {{company}}?"
        ),
    },
    {
        "name": "Proposal — pilot scope",
        "channel": "email",
        "strategy": "proposal",
        "funnel_stage": "decision",
        "subject": "{{company}} — 30-day AI sales pilot",
        "body": (
            "Hi {{name}},\n\n"
            "Based on our discussion, here is a 30-day pilot: 1) connect your data, "
            "2) automate discovery + outreach for one segment, 3) review results and "
            "expand. I can send the scope today.\n\n{{sender_name}}"
        ),
    },
    {
        "name": "Closing — start this month",
        "channel": "email",
        "strategy": "closing",
        "funnel_stage": "decision",
        "subject": "Shall we get {{company}} started this month?",
        "body": (
            "Hi {{name}},\n\n"
            "Everything is ready on our side — we can onboard {{company}} this month "
            "and have the first campaigns live within a week.\n\n"
            "Shall I send the agreement?\n\n{{sender_name}}"
        ),
    },
    {
        "name": "Re-engage — dormant lead",
        "channel": "whatsapp",
        "strategy": "re_engage",
        "funnel_stage": "retention",
        "subject": "",
        "body": (
            "Hi {{name}}, it's been a while. We've shipped new AI agents for "
            "{{company}}'s use case — happy to give you a fresh look whenever suits."
        ),
    },
]
