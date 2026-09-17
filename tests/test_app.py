import os
os.environ["DATABASE_URL"] = "sqlite:///./kittylol_test.db"
os.environ["ADMIN_USERNAME"] = "test"
os.environ["ADMIN_PASSWORD"] = "testpass"
os.environ["SESSION_SECRET"] = "test-secret"

from fastapi.testclient import TestClient
from app.main import app, Base, engine, SessionLocal, Script, Token

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "kittylol-api"


def test_login_script_token_loader():
    r = client.post("/login", data={"username":"test","password":"testpass"}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post("/dashboard/scripts", data={"name":"Demo","version":"1.0.0","content":"print('kitty')"}, follow_redirects=False)
    assert r.status_code == 303
    with SessionLocal() as s:
        script = s.query(Script).first()
        assert script
        sid = script.id
    r = client.post("/dashboard/tokens", data={"script_id":sid,"expires_days":0}, follow_redirects=False)
    assert r.status_code == 303
    with SessionLocal() as s:
        token = s.query(Token).first()
        value = token.value
    r = client.get(f"/files/v4/loader/{value}.lua", headers={"accept":"*/*","user-agent":"Roblox"})
    assert r.status_code == 200
    assert "print('kitty')" in r.text
    r = client.get(f"/files/v4/loader/{value}.lua", headers={"accept":"text/html","user-agent":"Mozilla/5.0"})
    assert r.status_code == 200
    assert "KITTYLOL LOADER" in r.text
