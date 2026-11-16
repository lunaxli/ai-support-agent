from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.api.routes import support
from app.models import UserCreate
from app.support.ai_schemas import Draft
from app.support.providers import MockProvider, ProviderError
from app.support.workflow import SupportWorkflow

BASE = "/api/v1/tickets/"
PASSWORD = "support-test-password"


def identity(client, db, label):
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"{label}-{uuid4().hex}@example.com",
            password=PASSWORD,
        ),
    )
    token = client.post(
        "/api/v1/login/access-token",
        data={
            "username": user.email,
            "password": PASSWORD,
        },
    ).json()["access_token"]
    return str(user.id), {"Authorization": f"Bearer {token}"}


def create(
    client, headers, subject="重置登录密码", description="忘记登录密码，如何重置？"
):
    response = client.post(
        BASE, headers=headers, json={"subject": subject, "description": description}
    )
    assert response.status_code == 201, response.text
    return response.json()


def detail(client, headers, ticket):
    response = client.get(BASE + ticket["id"], headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def analyze(client, headers, ticket):
    return client.post(
        BASE + ticket["id"] + "/analyses",
        headers=headers,
        params={"version": ticket["version"]},
    )


def review(client, headers, ticket, analysis, decision, reply=None):
    return client.post(
        BASE + ticket["id"] + "/reviews",
        headers=headers,
        json={
            "version": ticket["version"],
            "analysis_id": analysis["id"],
            "decision": decision,
            "note": "已核对",
            "final_reply": reply,
        },
    )


def test_scope_crud_and_version(client: TestClient, db: Session):
    _, customer = identity(client, db, "owner")
    _, outsider = identity(client, db, "outsider")
    assert client.get(BASE).status_code == 401
    ticket = create(client, customer)
    path = BASE + ticket["id"]
    assert client.get(BASE, headers=outsider).json() == {"count": 0, "data": []}
    assert client.get(path, headers=outsider).status_code == 404
    assert (
        client.put(
            path,
            headers=outsider,
            json={
                "subject": "越权",
                "description": "越权",
                "version": ticket["version"],
            },
        ).status_code
        == 404
    )
    assert (
        client.delete(
            path, headers=outsider, params={"version": ticket["version"]}
        ).status_code
        == 404
    )
    assert analyze(client, customer, ticket).status_code == 403
    assert (
        client.patch(
            path + "/status",
            headers=customer,
            json={
                "status": "in_progress",
                "version": ticket["version"],
            },
        ).status_code
        == 403
    )
    saved = client.put(
        path,
        headers=customer,
        json={
            "subject": "更新标题",
            "description": "更新描述",
            "version": ticket["version"],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["version"] == ticket["version"] + 1
    assert (
        client.delete(
            path, headers=customer, params={"version": ticket["version"]}
        ).status_code
        == 409
    )
    assert (
        client.delete(
            path, headers=customer, params={"version": saved.json()["version"]}
        ).status_code
        == 204
    )
    assert client.get(path, headers=customer).status_code == 404


def test_agent_approval_and_customer_projection(client, db, superuser_token_headers):
    _, customer = identity(client, db, "customer")
    staff_id, staff = identity(client, db, "agent")
    grant = BASE + "staff/" + staff_id
    assert (
        client.put(grant, headers=staff, json={"is_support_agent": True}).status_code
        == 403
    )
    assert (
        client.put(
            grant, headers=superuser_token_headers, json={"is_support_agent": True}
        ).status_code
        == 200
    )
    assert client.get(BASE + "capabilities", headers=staff).json()["can_review"]
    ticket = create(client, customer)
    response = analyze(client, staff, ticket)
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert analysis["provider"] == "mock"
    assert analysis["category"] == "account"
    assert analysis["route"] == "draft_ready"
    assert analysis["sources"][0]["passage_id"] == "account.md#1"
    assert analysis["sources"][0]["excerpt"] in analysis["draft"]
    pending = detail(client, staff, ticket)
    assert pending["status"] == "waiting_review"
    customer_view = detail(client, customer, ticket)
    assert (
        customer_view["analyses"]
        == customer_view["logs"]
        == customer_view["reviews"]
        == []
    )
    assert customer_view["final_reply"] is None
    assert review(client, customer, pending, analysis, "approved").status_code == 403

    result = review(client, staff, pending, analysis, "approved")
    assert result.status_code == 201, result.text
    assert result.json()["reviewer_id"] == staff_id
    assert review(client, staff, pending, analysis, "approved").status_code == 409
    saved = detail(client, customer, ticket)
    assert saved["status"] == "resolved" and saved["final_reply"] == analysis["draft"]
    assert [log["action"] for log in detail(client, staff, ticket)["logs"]] == [
        "ticket_created",
        "analysis_recorded",
        "review_recorded",
    ]
    assert (
        client.put(
            grant, headers=superuser_token_headers, json={"is_support_agent": False}
        ).status_code
        == 200
    )
    assert client.get(BASE + ticket["id"], headers=staff).status_code == 404


def test_risk_and_no_evidence(client, superuser_token_headers):
    staff = superuser_token_headers
    tickets = [
        ("退款申请", "账单出现重复扣款，请退款", "risk"),
        ("离线蓝牙标签", "可否配置蓝牙温度标签？", "no_evidence"),
    ]
    for subject, description, reason in tickets:
        ticket = create(client, staff, subject, description)
        first = analyze(client, staff, ticket).json()
        assert first["reason"] == reason and first["draft"] is None
        pending = detail(client, staff, ticket)
        assert review(client, staff, pending, first, "approved").status_code == 422
        assert review(client, staff, pending, first, "rejected").status_code == 201
        reopened = detail(client, staff, ticket)
        assert reopened["status"] == "in_progress"
        second = analyze(client, staff, reopened).json()
        again = detail(client, staff, ticket)
        assert (
            review(client, staff, again, first, "approved", "人工答复").status_code
            == 409
        )
        assert (
            review(client, staff, again, second, "approved", "人工答复").status_code
            == 201
        )
        assert detail(client, staff, ticket)["final_reply"] == "人工答复"


def test_concurrent_analysis_only_commits_once(
    client, superuser_token_headers, monkeypatch
):
    staff = superuser_token_headers
    ticket = create(client, staff)
    barrier = Barrier(2)
    real_run = support.run_analysis

    def delayed(subject, description):
        barrier.wait(timeout=10)
        return real_run(subject, description)

    monkeypatch.setattr(support, "run_analysis", delayed)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: analyze(client, staff, ticket), range(2))
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert len(detail(client, staff, ticket)["analyses"]) == 1


def test_bad_citation_and_model_failure():
    class BadCitation(MockProvider):
        def draft(self, subject, description, passages):
            return Draft(reply="无效草稿", source_ids=["missing.md#1"])

    class Timeout(MockProvider):
        def classify(self, subject, description):
            raise ProviderError("Timeout")

    for provider, reason in (
        (BadCitation(), "insufficient_evidence"),
        (Timeout(), "model_error"),
    ):
        result = SupportWorkflow(provider, support.KB).run(
            "重置登录密码", "忘记登录密码"
        )
        assert result.route == "human_review" and result.reason == reason
        assert result.draft is None and result.sources == []
