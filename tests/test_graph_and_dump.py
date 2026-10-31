"""Tests for: interaction dump parsing (chats + mail-shaped records),
pipeline template personalisation, and networkx graph preprocessing.

Runs light: imports only stdlib + networkx modules (no FastAPI app).
"""

import json
import sys
from pathlib import Path

import pytest

# networkx is installed in the project venv (used by the cron scripts). When the
# suite runs on the system interpreter, skip the graph tests instead of erroring.
pytest.importorskip("networkx", reason="networkx installed in .venv only")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sales_fastapi.graph_build import build_graph, export_graph, graph_stats  # noqa: E402
from sales_fastapi.interaction_dump import (  # noqa: E402
    build_dump,
    classify_media,
    mail_record,
    parse_whatsapp_chat,
    read_chat_zip,
)
from sales_fastapi.pipeline_templates import (  # noqa: E402
    TEMPLATES,
    fill,
    first_phone,
    norm_phone,
    wa_link,
)

CHAT_SAMPLE = """28/11/2024, 9:41:22 pm - Narayan KALIKA: Order 400mm cable tie
28/11/2024, 9:42:10 pm - Damini Kalika Production Karande: Baby Core order
29/11/2024, 10:01 am - Narayan KALIKA: IMG-20241129-WA0007.jpg (file attached)
29/11/2024, 10:02 am - Narayan KALIKA: <Media omitted>
multi-line continuation text
29/11/2024, 10:05 am - KALIKA TARPOULIN: PO shared
"""

MAIL_SAMPLE = dict(
    subject="RE: Quotation for VCI bags",
    sender="Purchase Dept <purchase@acmeplast.in>",
    to="sales@kalikaindia.com",
    date="2026-10-28",
    body="Please find our requirement of 500 kg VCI bags. Confirm rate and delivery.",
    attachments=[{"name": "requirement.pdf", "size": 40213}, {"name": "photo.jpg", "size": 88122}],
)


# ---------------------------------------------------------------- chat parsing
def test_parse_chat_messages_and_continuation():
    parsed = parse_whatsapp_chat(CHAT_SAMPLE)
    assert parsed["message_count"] == 5
    assert parsed["participants"] == [
        "Damini Kalika Production Karande",
        "KALIKA TARPOULIN",
        "Narayan KALIKA",
    ]
    assert parsed["date_range"] == {"first": "2024-11-28", "last": "2024-11-29"}
    # multi-line continuation folds into previous message
    assert "multi-line continuation" in parsed["messages"][3]["text"]
    # media markers
    assert parsed["media_omitted_count"] == 1
    assert parsed["messages"][2]["attachments_inline"] == ["IMG-20241129-WA0007.jpg"]


def test_classify_media():
    assert classify_media("a.JPG") == "image"
    assert classify_media("clip.mp4") == "video"
    assert classify_media("voice.aac") == "audio"
    assert classify_media("quote.pdf") == "document"
    assert classify_media("card.vcf") == "contact_card"
    assert classify_media("x.unknown") == "other"


def test_read_chat_zip(tmp_path):
    import zipfile

    zp = tmp_path / "WhatsApp Chat with TestBuyer.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("WhatsApp Chat with TestBuyer.txt", CHAT_SAMPLE)
        z.writestr("IMG-20241129-WA0007.jpg", b"\xff\xd8\xff")
        z.writestr("DOC.pdf", b"%PDF")
    chat = read_chat_zip(zp)
    assert chat["chat"] == "TestBuyer"
    assert chat["message_count"] == 5
    assert len(chat["attachments"]) == 2
    assert {a["media_type"] for a in chat["attachments"]} == {"image", "document"}


# ---------------------------------------------------------------- dump build
def test_dump_with_mail_and_chat():
    chats = [
        {
            "chat": "Kalika Order's",
            "message_count": 5,
            "participants": ["A", "B"],
            "attachments": [{"name": "a.jpg", "size_bytes": 10, "media_type": "image"}],
            "media_omitted_count": 1,
            "messages": [],
        }
    ]
    mails = [mail_record(**MAIL_SAMPLE)]
    dump = build_dump(chats, mails, sources=["test"])
    assert dump["stats"]["chats"] == 1
    assert dump["stats"]["messages"] == 5
    assert dump["stats"]["attachments"] == 1
    assert dump["stats"]["media_by_type"] == {"image": 1}
    assert dump["stats"]["mails"] == 1
    assert dump["mails"][0]["attachments"][0]["media_type"] == "document"
    assert dump["mails"][0]["body_preview"].startswith("Please find our requirement")


def test_mail_record_defaults():
    m = mail_record()
    assert m["type"] == "email" and m["attachments"] == [] and m["source"] == "imap"


# ---------------------------------------------------------------- pipeline helpers
def test_phone_normalisation():
    assert norm_phone("98220 00000") == "919822000000"
    assert norm_phone("+91 98220 00000") == "919822000000"
    assert norm_phone("123") == ""
    assert first_phone("020 2605 2352; +91 98500 77152") == "919850077152"
    assert first_phone("") == ""


def test_template_fill_and_wa_link():
    msg = fill(
        TEMPLATES["recent_orders"][0]["text"],
        name="Patil",
        company="ACME",
        order_no="LOC-101",
        amount="12,500",
        status="Dispatched",
        agent="Ai.Solutions",
    )
    assert "LOC-101" in msg and "Patil" in msg and "12,500" in msg
    assert "{" not in msg  # no unfilled variables
    link = wa_link("919822000000", msg)
    assert link.startswith("https://wa.me/919822000000?text=")
    assert "LOC-101" in link


def test_template_catalog_integrity():
    for segment, templates in TEMPLATES.items():
        assert templates, segment
        ids = [t["id"] for t in templates]
        assert len(ids) == len(set(ids))
        for t in templates:
            assert t["text"] and t["name"] and t["intent"]


# ---------------------------------------------------------------- graph build
@pytest.fixture()
def sample_graph():
    contacts = [
        {
            "id": 1,
            "company": "Acme Plast",
            "name": "Patil",
            "email": "p@acmeplast.in",
            "phone": "98220 00000",
            "domain": "",
            "intent": "sales",
            "gcs_path": "sales-contacts/x.xlsx#s",
        },
        {
            "id": 2,
            "company": "Samarth Enterprises",
            "name": "Manisha",
            "email": "samrthsales@gmail.com",
            "phone": "9175341970",
            "domain": "",
            "intent": "procurement",
            "gcs_path": "",
        },
        {
            "id": 3,
            "company": "NoDomain Co",
            "name": "",
            "email": "unknown-x@placeholder.local",
            "phone": "",
            "domain": "",
            "intent": "general",
            "gcs_path": "",
        },
    ]
    chats = [
        {
            "chat": "+91 98220 00000",
            "file": "WhatsApp Chat with +91 98220 00000.zip",
            "message_count": 42,
            "attachments": [{"name": "a.jpg"}],
        },
        {
            "chat": "Kalika Order's",
            "file": "WhatsApp Chat with Kalika Order's .zip",
            "message_count": 429,
            "attachments": [],
        },
    ]
    orders = [{"customer": "Acme Plast Industries", "gross": 125000.0}]
    return build_graph(contacts, chats, orders)


def test_graph_nodes_edges(sample_graph):
    G = sample_graph
    assert G.number_of_nodes() > 0 and G.number_of_edges() > 0
    kinds = {d["kind"] for _, d in G.nodes(data=True)}
    assert {"contact", "domain", "intent", "chat_thread", "erp_customer"} <= kinds
    # phone-based chat mapping edge exists
    assert any(d.get("kind") == "CHAT_MAPS_TO_CONTACT" for _, _, d in G.edges(data=True))
    # erp customer matched to contact 1 by company substring
    assert any(d.get("kind") == "ORDER_BY_CONTACT" for _, _, d in G.edges(data=True))
    # placeholder email must not create a domain node
    assert not any(n == "domain:placeholder.local" for n in G.nodes)


def test_graph_stats_and_export(sample_graph, tmp_path):
    stats = graph_stats(sample_graph)
    assert stats["nodes"] == sample_graph.number_of_nodes()
    assert stats["edges_by_kind"]
    assert 0 <= stats["density"] <= 1
    result = export_graph(sample_graph, tmp_path)
    nodes = json.loads((tmp_path / "nodes.json").read_text(encoding="utf-8"))
    edges = json.loads((tmp_path / "edges.json").read_text(encoding="utf-8"))
    assert len(nodes) == stats["nodes"] and len(edges) == stats["edges"]
    assert result["gexf"] is True
