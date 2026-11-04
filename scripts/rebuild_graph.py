"""Cron script: rebuild the preprocessing graph (networkx) and export
nodes.json / edges.json / graph.gexf / graph_stats.json into gcs_data/graph/.

Inputs: app contacts (sqlite) + interaction dump (chats) + top ERP customers
(analysis.json). Run with the project venv:
    .venv\\Scripts\\python.exe scripts\\rebuild_graph.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sales_fastapi.graph_build import (  # noqa: E402
    build_graph, export_graph, load_contacts_sqlite, load_orders_from_analysis,
)

BASE = Path(__file__).resolve().parents[1]
DB = BASE / "sales_pipeline.db"
DUMP = BASE / "gcs_data" / "interaction_dump.json"
ANALYSIS = BASE / "analysis.json"
OUT = BASE / "gcs_data" / "graph"


def main() -> None:
    contacts = load_contacts_sqlite(DB)
    chats = []
    if DUMP.exists():
        chats = json.loads(DUMP.read_text(encoding="utf-8")).get("chats", [])
    orders = load_orders_from_analysis(ANALYSIS)
    print(f"inputs: {len(contacts)} contacts, {len(chats)} chats, {len(orders)} erp customers")

    G = build_graph(contacts, chats, orders)
    result = export_graph(G, OUT)
    print(json.dumps(result["stats"], indent=2, ensure_ascii=False))
    print("exported to", result["out_dir"], "| gexf:", result["gexf"])


if __name__ == "__main__":
    main()
