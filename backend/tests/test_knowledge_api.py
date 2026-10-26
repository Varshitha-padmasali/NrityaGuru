import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.db.database import DatabaseNotConfiguredError, get_db
from app.db.seed import load_seed
from app.main import create_app


@pytest.fixture
def make_client(db_session):
    def _make(allow_unverified: bool = True) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, allow_unverified_records=allow_unverified
        )
        return TestClient(app)

    return _make


def test_retrieve_default_returns_only_verified(db_session, make_client):
    load_seed(db_session)
    r = make_client().post("/api/knowledge/retrieve", json={"text": "The river"})
    assert r.status_code == 200
    body = r.json()
    assert body["supported_count"] == 0
    assert body["concepts"][0]["status"] == "unsupported"
    assert "disclaimer" in body


def test_retrieve_with_unverified_returns_labelled_reference(db_session, make_client):
    load_seed(db_session)
    r = make_client().post(
        "/api/knowledge/retrieve", json={"text": "The river", "include_unverified": True}
    )
    assert r.status_code == 200
    ref = r.json()["concepts"][0]["references"][0]
    assert ref["record_id"] == "mudra_pataka"
    assert ref["verification_status"] == "source_cited"
    assert ref["source"]["source_url"].startswith("https://")
    assert ref["limitations"]


def test_unverified_request_forbidden_when_server_disallows(db_session, make_client):
    load_seed(db_session)
    r = make_client(allow_unverified=False).post(
        "/api/knowledge/retrieve", json={"text": "river", "include_unverified": True}
    )
    assert r.status_code == 403


@pytest.mark.parametrize("payload", [{"text": ""}, {"text": "   "}, {"text": "1234"}, {}, {"text": "a" * 1001}])
def test_invalid_retrieve_requests_return_422(make_client, payload):
    assert make_client().post("/api/knowledge/retrieve", json=payload).status_code == 422


def test_mudra_list_default_empty_then_visible(db_session, make_client):
    load_seed(db_session)
    client = make_client()
    assert client.get("/api/mudras").json() == []
    r = client.get("/api/mudras", params={"include_unverified": True})
    assert r.status_code == 200
    assert len(r.json()) == 52
    assert {m["id"] for m in r.json()} >= {"mudra_pataka", "mudra_tripataka", "mudra_ardhapataka"}


def test_mudra_list_supports_search_and_all_52_default_page(db_session, make_client):
    load_seed(db_session)
    client = make_client()
    all_records = client.get("/api/mudras", params={"include_unverified": True})
    assert len(all_records.json()) == 52  # default page includes the complete catalogue
    pataka = next(record for record in all_records.json() if record["id"] == "mudra_pataka")
    assert pataka["dataset_image_count"] == 568
    assert pataka["dataset_images_available"] is True
    assert pataka["recognition_supported"] is False
    kataka = next(record for record in all_records.json() if record["id"] == "mudra_katakamukha")
    assert kataka["dataset_image_count"] == 1487
    assert {item["dataset_folder"] for item in kataka["dataset_classes"]} == {
        "Katakamukha_1", "Katakamukha_2", "Katakamukha_3"
    }
    found = client.get("/api/mudras", params={"include_unverified": True, "q": "kapota"})
    assert [record["name"] for record in found.json()] == ["Kapota"]
    by_name = client.get("/api/mudras/Kapota", params={"include_unverified": True})
    assert by_name.status_code == 200 and by_name.json()["id"] == "mudra_kapota"
    by_dataset_label = client.get("/api/mudras", params={"include_unverified": True, "q": "Katakamukha_2"})
    assert [record["id"] for record in by_dataset_label.json()] == ["mudra_katakamukha"]


def test_mudra_detail_and_404s(db_session, make_client):
    load_seed(db_session)
    client = make_client()
    assert client.get("/api/mudras/mudra_pataka").status_code == 404  # not verified
    assert client.get("/api/mudras/nope", params={"include_unverified": True}).status_code == 404
    ok = client.get("/api/mudras/mudra_pataka", params={"include_unverified": True})
    assert ok.status_code == 200
    assert ok.json()["source"]["source_name"].startswith("List of mudras")
    assert ok.json()["dataset_image_count"] == 568


def test_movements_list_is_empty_but_ok(db_session, make_client):
    load_seed(db_session)
    r = make_client().get("/api/movements", params={"include_unverified": True})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_bad_paging_returns_422(make_client, params):
    assert make_client().get("/api/mudras", params=params).status_code == 422


def test_database_not_configured_returns_503(make_client):
    client = make_client()

    def boom():
        raise DatabaseNotConfiguredError("DATABASE_URL is not set")

    client.app.dependency_overrides[get_db] = boom
    r = client.get("/api/mudras")
    assert r.status_code == 503


def test_database_failure_returns_safe_503(make_client):
    client = make_client()

    def boom():
        raise OperationalError("SELECT 1", {}, Exception("password=hunter2 host=db"))

    client.app.dependency_overrides[get_db] = boom
    r = client.get("/api/mudras")
    assert r.status_code == 503
    assert "hunter2" not in r.text
    assert "Traceback" not in r.text
