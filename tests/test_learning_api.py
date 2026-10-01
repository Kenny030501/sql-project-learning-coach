from backend.curriculum import BY_ID


def test_progress_hint_answer_and_duplicate(client):
    s = client.post("/api/start", json={"task_id": "quality", "revision": 0}).json()
    old = s["revision"]
    h = client.post("/api/hint", json={"task_id": "quality", "revision": old}).json()
    assert h["level"] == 1
    assert client.post("/api/hint", json={"task_id": "quality", "revision": old}).status_code == 400
    s = h["session"]
    result = client.post(
        "/api/run",
        json={"task_id": "quality", "revision": s["revision"], "sql": BY_ID["quality"]["answer"]},
    ).json()
    assert result["result"]["passed"]
    assert result["session"]["tasks"]["quality"]["independent"] is False


def test_solution_excludes_independence(client):
    s = client.post("/api/start", json={"task_id": "quality", "revision": 0}).json()
    r = client.post(
        "/api/run",
        json={"task_id": "quality", "revision": s["revision"], "sql": BY_ID["quality"]["answer"]},
    ).json()
    assert r["session"]["tasks"]["quality"]["independent"]
    r = client.post(
        "/api/solution", json={"task_id": "quality", "revision": r["session"]["revision"]}
    ).json()
    assert not r["session"]["tasks"]["quality"]["independent"]


def test_invalid_sql_counts_failed_attempt(client):
    s = client.post("/api/start", json={"task_id": "scale", "revision": 0}).json()
    r = client.post(
        "/api/run", json={"task_id": "scale", "revision": s["revision"], "sql": "DROP TABLE orders"}
    ).json()
    assert not r["result"]["passed"]
    assert r["session"]["tasks"]["scale"]["attempts"] == 1


def test_private_solutions_not_in_catalog(client):
    tasks = client.get("/api/curriculum").json()["tasks"]
    assert len(tasks) == 8
    assert all("answer" not in t and "hints" not in t for t in tasks)


def test_business_requires_two_query_results(client):
    s = client.post("/api/start", json={"task_id": "decision", "revision": 0}).json()
    r = client.post(
        "/api/business",
        json={"text": "我的业务建议需要证据", "consent": True, "revision": s["revision"]},
    )
    assert r.status_code == 400 and "至少2个" in r.json()["error"]
