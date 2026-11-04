import sys
sys.path.insert(0, ".")
from sales_fastapi.database import SessionLocal
from sales_fastapi.models import User
from sales_fastapi.security import create_access_token

db = SessionLocal()
user = db.query(User).filter(User.email == "ai.solutions@kalisoftai.in").first()
token, _ = create_access_token(user)
print(token)
db.close()
