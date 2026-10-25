import app.routes as routes

VALID = {"customer_id": "cust_001", "amount": 49.99, "currency": "USD"}


def force_success(monkeypatch):
    monkeypatch.setattr(routes.random, "random", lambda: 0.0)


def force_failure(monkeypatch):
    monkeypatch.setattr(routes.random, "random", lambda: 0.99)


def test_health_check(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_transaction_success(client, monkeypatch):
    force_success(monkeypatch)
    r = client.post("/transactions", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "success"
    assert body["failure_reason"] is None
    assert body["retry_count"] == 0


def test_create_transaction_failure(client, monkeypatch):
    force_failure(monkeypatch)
    r = client.post("/transactions", json=VALID)
    assert r.status_code == 201
    assert r.json()["status"] == "failed"
    assert r.json()["failure_reason"] in routes.FAILURE_REASONS


def test_rejects_negative_amount(client):
    r = client.post("/transactions", json={**VALID, "amount": -5})
    assert r.status_code == 422


def test_rejects_bad_currency(client):
    r = client.post("/transactions", json={**VALID, "currency": "usd"})
    assert r.status_code == 422


def test_idempotency_returns_same_transaction(client):
    payload = {**VALID, "idempotency_key": "order-12345-abc"}
    first = client.post("/transactions", json=payload).json()
    second = client.post("/transactions", json=payload).json()
    assert first["transaction_id"] == second["transaction_id"]
    assert len(client.get("/transactions").json()) == 1


def test_get_transaction_and_404(client):
    created = client.post("/transactions", json=VALID).json()
    r = client.get(f"/transactions/{created['transaction_id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert client.get("/transactions/does-not-exist").status_code == 404


def test_list_filters_by_status(client, monkeypatch):
    force_success(monkeypatch)
    client.post("/transactions", json=VALID)
    force_failure(monkeypatch)
    client.post("/transactions", json=VALID)

    failed = client.get("/transactions", params={"status": "failed"}).json()
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    assert client.get("/transactions", params={"status": "bogus"}).status_code == 422


def test_retry_successful_transaction_is_rejected(client, monkeypatch):
    force_success(monkeypatch)
    txn = client.post("/transactions", json=VALID).json()
    r = client.post(f"/transactions/{txn['transaction_id']}/retry")
    assert r.status_code == 409


def test_retry_can_recover_failed_transaction(client, monkeypatch):
    force_failure(monkeypatch)
    txn = client.post("/transactions", json=VALID).json()
    force_success(monkeypatch)
    r = client.post(f"/transactions/{txn['transaction_id']}/retry")
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert r.json()["retry_count"] == 1


def test_retry_cap(client, monkeypatch):
    force_failure(monkeypatch)
    txn = client.post("/transactions", json=VALID).json()
    url = f"/transactions/{txn['transaction_id']}/retry"
    for _ in range(routes.MAX_RETRIES):
        assert client.post(url).status_code == 200
    assert client.post(url).status_code == 409


def test_retry_unknown_transaction(client):
    assert client.post("/transactions/nope/retry").status_code == 404