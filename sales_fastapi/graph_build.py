"""Graph preprocessing (networkx) — builds the relationship graph that a future
graph database will store.

Node types
----------
contact       one row from the app contacts table
domain        email/company domain bucket
intent        classified intent (general / sales / procurement / ...)
chat_thread   one WhatsApp export chat
erp_customer  customer from the ERP latest Orders report

Edge types
----------
CONTACT_IN_DOMAIN      contact -> domain
CONTACT_HAS_INTENT     contact -> intent
CHAT_MAPS_TO_CONTACT   chat_thread -> contact      (phone match)
ORDER_BY_CONTACT       erp_customer -> contact     (company match)
MESSAGE_ABOUT          chat_thread -> domain       (chat name contains domain/company token)

Exports: nodes.json, edges.json, graph.gexf (Gephi/Neo4j-import friendly), stats.

networkx is required at runtime (project .venv). Imports are stdlib-only so the
module itself imports anywhere.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .pipeline_templates import first_phone


def _require_nx():
    try:
        import networkx as nx  # type: ignore

        return nx
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "networkx is required for graph preprocessing. Install it in the project venv: "
            ".venv\\Scripts\\python.exe -m pip install networkx"
        ) from exc


# ------------------------------------------------------------------ loaders
def load_contacts_sqlite(db_path: str | Path, user_id: int | None = None) -> list[dict]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    q = "SELECT id, company, name, email, phone, domain, intent, tags, notes, gcs_path FROM contacts"
    args: tuple = ()
    if user_id is not None:
        q += " WHERE user_id = ?"
        args = (user_id,)
    rows = [dict(r) for r in con.execute(q, args)]
    con.close()
    return rows


def load_orders_from_analysis(analysis_json: str | Path) -> list[dict]:
    p = Path(analysis_json)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("sales_2026", {}).get("top_customers", [])


# ------------------------------------------------------------------ build
def _domain_of(contact: dict) -> str:
    d = (contact.get("domain") or "").strip().lower()
    if d:
        return d
    email = (contact.get("email") or "").lower()
    if "@" in email and "placeholder.local" not in email:
        return email.split("@")[-1]
    return ""


def build_graph(contacts: list[dict], chats: list[dict], orders: list[dict]):
    """Build the directed graph. Returns a networkx.DiGraph."""
    nx = _require_nx()
    G = nx.DiGraph()

    for c in contacts:
        cid = f"contact:{c['id']}"
        G.add_node(
            cid,
            kind="contact",
            company=c.get("company") or "",
            name=c.get("name") or "",
            phone=first_phone(c.get("phone", "")),
            source=c.get("gcs_path") or "",
        )
        dom = _domain_of(c)
        if dom:
            did = f"domain:{dom}"
            G.add_node(did, kind="domain", domain=dom)
            G.add_edge(cid, did, kind="CONTACT_IN_DOMAIN")
        intent = (c.get("intent") or "").strip() or "general"
        iid = f"intent:{intent}"
        G.add_node(iid, kind="intent", intent=intent)
        G.add_edge(cid, iid, kind="CONTACT_HAS_INTENT")

    # phone index for chat mapping
    by_phone = {}
    for c in contacts:
        p = first_phone(c.get("phone", ""))
        if p:
            by_phone[p] = c

    for chat in chats:
        tid = f"chat:{chat.get('chat', '')[:80]}"
        G.add_node(
            tid,
            kind="chat_thread",
            file=chat.get("file", ""),
            messages=chat.get("message_count", 0),
            attachments=len(chat.get("attachments", [])),
        )
        # map thread to contact by phone inside the chat title
        for num in re.findall(r"\+?\d[\d ]{8,}\d", chat.get("chat", "")):
            p = first_phone(num)
            if p and p in by_phone:
                G.add_edge(tid, f"contact:{by_phone[p]['id']}", kind="CHAT_MAPS_TO_CONTACT")

    for o in orders:
        oid = f"erp_customer:{o.get('customer', '')[:80]}"
        G.add_node(
            oid, kind="erp_customer", customer=o.get("customer", ""), gross=o.get("gross", 0)
        )
        cl = (o.get("customer") or "").lower()
        if cl:
            for c in contacts:
                comp = (c.get("company") or "").lower()
                if comp and len(comp) >= 6 and (comp in cl or cl in comp):
                    G.add_edge(oid, f"contact:{c['id']}", kind="ORDER_BY_CONTACT")
                    break

    return G


def graph_stats(G) -> dict:
    nx = _require_nx()
    by_kind: dict[str, int] = {}
    for _, data in G.nodes(data=True):
        k = data.get("kind", "?")
        by_kind[k] = by_kind.get(k, 0) + 1
    edge_kinds: dict[str, int] = {}
    for _, _, data in G.edges(data=True):
        k = data.get("kind", "?")
        edge_kinds[k] = edge_kinds.get(k, 0) + 1
    top = sorted(G.degree, key=lambda x: -x[1])[:10]
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "nodes_by_kind": by_kind,
        "edges_by_kind": edge_kinds,
        "density": round(nx.density(G), 6),
        "connected_components": nx.number_weakly_connected_components(G),
        "top_connected": [{"node": n, "degree": d} for n, d in top],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def export_graph(G, out_dir: str | Path) -> dict:
    nx = _require_nx()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    nodes = [{"id": n, **d} for n, d in G.nodes(data=True)]
    edges = [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)]
    (out / "nodes.json").write_text(
        json.dumps(nodes, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    (out / "edges.json").write_text(
        json.dumps(edges, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    stats = graph_stats(G)
    (out / "graph_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        nx.write_gexf(G, str(out / "graph.gexf"))  # Gephi / Neo4j-import friendly
        gexf = True
    except Exception:
        gexf = False
    return {
        "out_dir": str(out),
        "nodes": len(nodes),
        "edges": len(edges),
        "gexf": gexf,
        "stats": stats,
    }
