from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from storage3.exceptions import StorageApiError

from app.config import settings
from app.main import app
from app.routers import companies as routes
from app.services import logos
from tests.test_companies import BODY, MemoryDB, headers


def png(color="red", size=(1024, 256)):
    output = BytesIO()
    Image.new("RGBA", size, color).save(output, format="PNG")
    return output.getvalue()


class Bucket:
    def __init__(self):
        self.files = {}

    def upload(self, path, data, options):
        assert options["content-type"] == "image/webp"
        self.files[path] = data

    def create_signed_urls(self, paths, _ttl):
        return [{"path": path, "signedURL": f"https://storage.example/{path}?token=test" if path in self.files else None} for path in paths]

    def remove(self, paths):
        for path in paths:
            self.files.pop(path, None)


@pytest.fixture
def workspace(monkeypatch):
    db, bucket = MemoryDB(), Bucket()
    db.storage = SimpleNamespace(from_=lambda _: bucket)
    monkeypatch.setattr(routes, "get_db", lambda: db)
    monkeypatch.setattr(logos, "get_db", lambda: db)
    monkeypatch.setattr(settings, "demo_seed", False)
    monkeypatch.setattr(routes.news, "sync_company", lambda _: None)
    with TestClient(app) as client:
        cid = client.post("/api/v1/companies", json=BODY, headers=headers()).json()["id"]
        yield client, cid, bucket


def test_logo_is_decoded_resized_restored_replaced_and_removed(workspace):
    client, cid, bucket = workspace
    endpoint = f"/api/v1/companies/{cid}/logo"
    response = client.put(endpoint, files={"file": ("logo.png", png(), "image/png")}, headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()["logoUrl"].startswith(f"https://storage.example/o1/{cid}/logo.webp?")
    stored = bucket.files[f"o1/{cid}/logo.webp"]
    with Image.open(BytesIO(stored)) as image:
        assert image.format == "WEBP" and image.size == (512, 128)
    with TestClient(app) as returning:
        company = returning.get(f"/api/v1/companies/{cid}", headers=headers()).json()
        assert company["logoUrl"]
        assert returning.get("/api/v1/companies", headers=headers()).json()[0]["logoUrl"]
    assert client.put(endpoint, files={"file": ("next.png", png("blue"), "image/png")}, headers=headers()).status_code == 200
    assert len(bucket.files) == 1 and bucket.files[f"o1/{cid}/logo.webp"] != stored
    assert client.delete(endpoint, headers=headers()).status_code == 204
    assert not bucket.files
    assert client.get(f"/api/v1/companies/{cid}", headers=headers()).json()["logoUrl"] is None


def test_another_account_cannot_upload_or_delete_a_logo(workspace):
    client, cid, bucket = workspace
    endpoint = f"/api/v1/companies/{cid}/logo"
    assert client.put(endpoint, files={"file": ("logo.png", png(), "image/png")}, headers=headers("o2", "u2")).status_code == 404
    assert client.delete(endpoint, headers=headers("o2", "u2")).status_code == 404
    assert not bucket.files


@pytest.mark.parametrize("data,status", [(b"<svg onload='alert(1)'/>", 415), (b"\x89PNG\r\n\x1a\ninvalid", 415), (b"x" * (logos.MAX_BYTES + 1), 413)])
def test_invalid_or_oversized_image_is_not_stored(workspace, data, status):
    client, cid, bucket = workspace
    response = client.put(f"/api/v1/companies/{cid}/logo", files={"file": ("logo.png", data, "image/png")}, headers=headers())
    assert response.status_code == status
    assert not bucket.files


def test_excessive_dimensions_rejected():
    with pytest.raises(HTTPException) as error:
        logos.normalize(png(size=(8193, 1)))
    assert error.value.status_code == 413


def test_company_delete_removes_its_logo(workspace):
    client, cid, bucket = workspace
    client.put(f"/api/v1/companies/{cid}/logo", files={"file": ("logo.png", png(), "image/png")}, headers=headers())
    assert client.delete(f"/api/v1/companies/{cid}", headers=headers()).status_code == 204
    assert not bucket.files


def test_logo_storage_outage_does_not_block_workspace(workspace, monkeypatch):
    client, _cid, bucket = workspace
    def unavailable(*_):
        raise StorageApiError("unavailable", "503", 503)
    monkeypatch.setattr(bucket, "create_signed_urls", unavailable)
    response = client.get("/api/v1/companies", headers=headers())
    assert response.status_code == 200 and response.json()[0]["logoUrl"] is None
