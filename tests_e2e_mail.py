import os, sys, tempfile, json
os.environ.setdefault("ENV", "development")
sys.path.insert(0, ".")
import sqlalchemy as sa
import sales_fastapi.database as dbmod

tmp = tempfile.mktemp(suffix=".db")
dbmod.engine = sa.create_engine(f"sqlite:///{tmp}", connect_args={"check_same_thread": False})
dbmod.SessionLocal = sa.orm.sessionmaker(bind=dbmod.engine, autoflush=False, autocommit=False)
from sales_fastapi.models import Base, User, EmailConnection, MessageTemplate, MarketingCompany
Base.metadata.create_all(bind=dbmod.engine)
from sales_fastapi import mail_sync
from sales_fastapi.routers import email as email_router, campaigns as camp_router, marketing_companies as mc_router, templates as tpl_router
from sales_fastapi.security import get_current_user, encrypt_secret

db = dbmod.SessionLocal()
u = User(google_sub="sub-1", email="kalika@test.local", name="Kalika", password_hash="x", role="admin", domain="kalisoftai.in")
db.add(u); db.commit(); db.refresh(u)
conn = EmailConnection(user_id=u.id, email_address="kalika@gmail.com", imap_host="imap.gmail.com", smtp_host="smtp.gmail.com", secret_encrypted=encrypt_secret("app-pass"))
db.add(conn); db.commit(); db.refresh(conn)
tpl = MessageTemplate(user_id=u.id, channel="whatsapp", name="WA Rate", category="rates", body="Hi {{contact_name}} at {{company_name}}, quick rates for {{product_name}} - call {{mobile}}, regards {{designation}}")
tpl2 = MessageTemplate(user_id=u.id, channel="email", name="EM", subject="Rate for {{company}}", body="<p>Hi {{name}}, {{product_name}} offer for {{company_name}}. Email {{email}}</p>")
mc = MarketingCompany(user_id=u.id, company="GlobePack", company_key="globepack", contact_name="Meera", email="meera@globepack.com", phone="9156031472", category="packaging")
mc2 = MarketingCompany(user_id=u.id, company="BadCo", company_key="badco", contact_name="X", email="not-an-email", phone="123", category="packaging")
db.add_all([tpl, tpl2, mc, mc2]); db.commit()


class FakeGCS:
    store = {}

    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name; self.available = True; self._client = None; self.blobs = FakeGCS.store

    def upload_bytes(self, name, data, ct=""): self.blobs[name] = data; return True
    def upload_json(self, name, payload): self.blobs[name] = json.dumps(payload); return True


mail_sync.GCSStorage = lambda bucket_name=None: FakeGCS(bucket_name)

import email as em


def mkraw(uid, mid, frm, subj, date):
    return em.message_from_string(f"Message-ID: <{mid}>\nFrom: {frm}\nTo: kalika@gmail.com\nSubject: {subj}\nDate: {date}\n\nBody text {uid}").as_bytes()


class FakeExtractor:
    def __init__(self, host, port, user, pw): pass
    def connect(self): return True
    def get_uidvalidity(self): return 999
    def disconnect(self): pass

    def sync_emails(self, **kw):
        last = kw.get("last_uid") or 0
        msgs = [
            {"uid": "101", "message_id": "<a@x>", "subject": "RFQ stretch film", "from": "Buyer <buy@a.com>", "to": "kalika@gmail.com", "date": "Sat, 08 Nov 2026 10:00:00 +0530", "intent": "sales", "body": "Need quotes", "snippet": "Need quotes", "attachments": [], "_attachments_data": [], "_raw": mkraw(101, "a@x", "buy@a.com", "RFQ", "Sat, 08 Nov 2026")},
            {"uid": "102", "message_id": "<b@x>", "subject": "Payment advice", "from": "Accounts <p@b.com>", "to": "kalika@gmail.com", "date": "Sun, 09 Nov 2026 09:00:00 +0530", "intent": "payment", "body": "PO paid", "snippet": "PO paid", "attachments": [{"name": "inv.pdf", "mime_type": "application/pdf", "size": 3}], "_attachments_data": [{"name": "inv.pdf", "mime_type": "application/pdf", "data": b"PDF", "size": 3}], "_raw": mkraw(102, "b@x", "p@b.com", "Pay", "Sun, 09 Nov 2026")},
            {"uid": "103", "message_id": "<a@x>", "subject": "RFQ dup", "from": "Buyer <buy@a.com>", "to": "kalika@gmail.com", "date": "Sun, 09 Nov 2026 09:10:00 +0530", "intent": "sales", "body": "dup", "snippet": "dup", "attachments": [], "_attachments_data": [], "_raw": mkraw(103, "a@x", "buy@a.com", "RFQdup", "Sun, 09 Nov 2026")},
        ]
        return [m for m in msgs if int(m["uid"]) > last]


mail_sync.EmailExtractor = FakeExtractor

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sales_fastapi.database import get_db

app = FastAPI()
app.include_router(email_router.router, prefix="/api")
app.include_router(camp_router.router, prefix="/api")
app.include_router(mc_router.router, prefix="/api")
app.include_router(tpl_router.router, prefix="/api")
def _db(): yield db
app.dependency_overrides[get_db] = _db
app.dependency_overrides[get_current_user] = lambda: u
c = TestClient(app)

j = c.post(f"/api/email/connections/{conn.id}/sync", json={"batch": 25}).json()
assert j["fetched"] == 3 and j["new"] == 2 and j["duplicates_skipped"] == 1, j
assert j["raw_uploaded"] == 2 and j["processed_uploaded"] == 2 and j["attachments_uploaded"] == 1
assert any(b.startswith("Kalika_gmail_data/raw/2026-11-08/") for b in FakeGCS.store)
assert any("attachments/2026-11-09/" in b for b in FakeGCS.store)
print("sync1 OK: dedup + raw/processed/attachments to Kalika_gmail_data")

j2 = c.post(f"/api/email/connections/{conn.id}/sync", json={"batch": 25}).json()
assert j2["new"] == 0 and j2["raw_uploaded"] == 0, j2
st = c.get(f"/api/email/connections/{conn.id}/sync/state").json()
assert st["last_uid"] == 103 and st["uidvalidity"] == 999, st
j3 = c.post(f"/api/email/connections/{conn.id}/sync", json={"batch": 25}).json()
assert j3["fetched"] == 0, j3
print("sync2/3 OK: checkpoint advances past duplicates; nothing re-fetched")

proc = [v for k, v in FakeGCS.store.items() if "processed/" in k][0]
pj = json.loads(proc)
recs = {m["subject"] for m in pj["mails"]}
assert recs == {"RFQ stretch film", "Payment advice"}
m = [x for x in pj["mails"] if x["subject"] == "Payment advice"][0]
assert m["intent"] in ("payment", "order") and m["attachment_count"] == 1 and m["from_email"] == "p@b.com"
print("processed OK: sender/company/intent/date/attachments extracted")

an = c.get("/api/email/sync/analytics?days=30").json()
assert an["mail"]["processed"] >= 2 and an["sync_health"]["last_status"] == "ok"
print("analytics OK:", {k: an["mail"][k] for k in ("fetched", "processed", "duplicates_skipped")})

cd = c.post("/api/campaigns", json={"name": "EM test", "channel": "email", "strategy": "cold_outreach", "template_id": tpl2.id, "use_ai": False, "filter": {"limit": 10, "contact_type": "marketing_companies", "contact_ids": [mc.id, mc2.id]}}).json()
assert cd["total"] == 1 and cd["messages"][0]["to_address"] == "meera@globepack.com"
assert "{{" not in cd["messages"][0]["rendered_body"] and "Meera" in cd["messages"][0]["rendered_body"] and "GlobePack" in cd["messages"][0]["rendered_subject"]
print("email campaign OK: invalid recipient excluded, {{tokens}} fully resolved")

r = c.post("/api/campaigns", json={"name": "WA test", "channel": "whatsapp", "strategy": "cold_outreach", "template_id": tpl.id, "use_ai": False, "filter": {"limit": 10, "contact_type": "marketing_companies", "contact_ids": [mc.id, mc2.id]}})
assert r.status_code == 201
cd2 = r.json()
assert cd2["total"] == 1 and "{{" not in cd2["messages"][0]["rendered_body"]
assert "9156031472" in cd2["messages"][0]["rendered_body"] and "Team" in cd2["messages"][0]["rendered_body"]
print("whatsapp campaign OK: mobile maps to {{mobile}}, missing designation -> 'Team' fallback")

class FakeMailSender:
    def __init__(self, *a, **k): pass
    def send(self, to, subject, body, from_email=None, **kw): return {"sent": True, "to": to, "from": from_email, "message_id": "<test@x>"}

email_router.MailSender = FakeMailSender
ts = c.post(f"/api/email/connections/{conn.id}/test-send", json={"template_id": tpl2.id, "contact_id": mc.id, "contact_type": "marketing_companies"})
j = ts.json()
assert ts.status_code == 200 and "{{" not in j["preview_body"] and "GlobePack" in j["preview_body"] and j["to"] == "kalika@gmail.com"
print("test-send OK (defaults to own mailbox):", j["to"], "|", j["subject"])

rr = c.post("/api/email/retention/cleanup").json()
assert rr["mail_touched"] == False and "removed" in rr
print("retention OK:", rr["removed"])

ed = c.patch(f"/api/templates/{tpl2.id}", json={"subject": "Updated rate for {{company_name}}"})
assert ed.status_code == 200 and "Updated rate" in ed.json()["subject"]
print("template PATCH edit OK")

print("== contact-selection upgrade tests ==")
# seed duplicates: same email twice, same phone twice
mc3 = MarketingCompany(user_id=u.id, company="GlobePack Ltd", company_key="globepack-ltd", contact_name="Meera", email="meera@globepack.com", phone="9156031472", category="packaging")
mc4 = MarketingCompany(user_id=u.id, company="NoDetail Co", company_key="nodetail", contact_name="Nobody", email="", phone="", category="other")
db.add_all([mc3, mc4]); db.commit()

r = c.get("/api/marketing-companies?limit=2&offset=0"); rows1 = r.json()
r = c.get("/api/marketing-companies?limit=2&offset=2"); rows2 = r.json()
assert r.status_code == 200 and len(rows1) == 2
ids1 = {x["id"] for x in rows1}; ids2 = {x["id"] for x in rows2}
assert ids1.isdisjoint(ids2), "offset pagination must not repeat rows"
print("pagination OK: offset returns disjoint pages")

r = c.get("/api/marketing-companies?missing_email=true"); me = r.json()
assert all(not x["email"] for x in me) and len(me) >= 1
r = c.get("/api/marketing-companies?missing_phone=true"); mp = r.json()
assert all(not x["phone"] for x in mp)
print("missing-detail filters OK:", len(me), len(mp))

r = c.get("/api/marketing-companies?email_test=1") if False else c.get("/api/marketing-companies?has_email=true")
assert all(x["email"] for x in r.json())
print("channel-availability filter OK")

r = c.get("/api/marketing-companies/duplicates"); d = r.json()
assert r.status_code == 200
emails_d = [set(g["ids"]) for g in d["by_email"]]
assert any({mc.id, mc3.id} == s or {mc.id, mc3.id} <= s for s in emails_d), d["by_email"]
assert d["total_duplicate_rows"] >= 2
print("duplicate detection OK:", d["total_duplicate_rows"], "dup rows")

seg = c.post("/api/marketing-companies/segments", json={"name": "Packaging hot", "filters": {"category": "packaging", "has_email": True}})
assert seg.status_code == 201 and any(s["name"] == "Packaging hot" for s in seg.json()["segments"])
ls = c.get("/api/marketing-companies/segments")
assert any(s["name"] == "Packaging hot" for s in ls.json()["segments"])
seg2 = c.post("/api/marketing-companies/segments", json={"name": "Packaging hot", "filters": {"category": "packaging"}})
assert len([s for s in seg2.json()["segments"] if s["name"] == "Packaging hot"]) == 1, "re-save must upsert not duplicate"
dl = c.delete("/api/marketing-companies/segments/Packaging hot")
assert not any(s["name"] == "Packaging hot" for s in dl.json()["segments"])
print("saved segments OK (upsert + delete)")

print("== format guards ==")
html_wa = c.post("/api/templates", json={"channel": "whatsapp", "name": "Bad WA", "subject": "", "body": "<p>Hi {{contact_name}}</p>"})
assert html_wa.status_code == 400, html_wa.json()
print("WhatsApp HTML template rejected:", html_wa.json()["detail"][:60])
patch_html = c.patch(f"/api/templates/{tpl.id}", json={"body": "<b>not plain</b>"})
assert patch_html.status_code == 400, patch_html.json()
patch_ok = c.patch(f"/api/templates/{tpl.id}", json={"body": "Hi {{contact_name}}, rates for {{company_name}}"})
assert patch_ok.status_code == 200
print("template PATCH validation OK")

r = c.post("/api/campaigns", json={"name": "WA HTML", "channel": "whatsapp", "strategy": "cold_outreach", "template_id": tpl2.id, "use_ai": False, "filter": {"limit": 10, "contact_type": "marketing_companies", "contact_ids": [mc.id]}})
assert r.status_code == 400 and "WhatsApp" in r.json()["detail"]
print("WA campaign with HTML template blocked:", r.json()["detail"][:70])
r = c.post("/api/campaigns", json={"name": "WA plain override", "channel": "whatsapp", "strategy": "cold_outreach", "template_id": tpl2.id, "use_ai": False, "body_override": "Hi {{contact_name}}, quick chat about {{company_name}}?", "filter": {"limit": 10, "contact_type": "marketing_companies", "contact_ids": [mc.id]}})
assert r.status_code == 201, r.json()
assert "{{" not in r.json()["messages"][0]["rendered_body"]
print("WA campaign with user-written plain override OK")

print("ALL E2E TESTS PASSED")
