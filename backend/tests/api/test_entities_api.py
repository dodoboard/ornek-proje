from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

CHARACTER = {"name": "Ada", "adult_age": 27, "style": "minimal chic", "color_palette": ["#aabbcc"]}


# --------------------------------------------------------------------------- characters


def test_character_crud_roundtrip(client: TestClient) -> None:
    created = client.post("/api/characters", json=CHARACTER)
    assert created.status_code == 201
    body = created.json()
    assert body["id"].startswith("CHR_")
    assert body["color_palette"] == ["#AABBCC"]
    assert body["default_language"] == "tr"

    listing = client.get("/api/characters", params={"q": "ad"}).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == body["id"]

    patched = client.patch(f"/api/characters/{body['id']}", json={"hair": "short black"}).json()
    assert patched["hair"] == "short black"
    assert patched["name"] == "Ada"

    assert client.delete(f"/api/characters/{body['id']}").status_code == 204
    assert client.get(f"/api/characters/{body['id']}").status_code == 404


@pytest.mark.parametrize("age", [17, 0, 121])
def test_character_age_must_be_adult(client: TestClient, age: int) -> None:
    response = client.post("/api/characters", json={**CHARACTER, "adult_age": age})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "text",
    [
        "a cute schoolgirl",
        "looks like a teenager",
        "16 years old",
        "genç bir ergen",
        "17 yaşında",
        "çocuk gibi",
    ],
)
def test_character_text_rejects_minor_references(client: TestClient, text: str) -> None:
    response = client.post("/api/characters", json={**CHARACTER, "description": text})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "text", ["works at the canteen", "skincare for 25 years old adults", "Kids brand? no"]
)
def test_minor_filter_word_boundaries(client: TestClient, text: str) -> None:
    status = client.post("/api/characters", json={**CHARACTER, "description": text}).status_code
    expected = 422 if "Kids" in text else 201
    assert status == expected


def test_patch_rejects_null_for_required_field(client: TestClient) -> None:
    character = client.post("/api/characters", json=CHARACTER).json()
    response = client.patch(f"/api/characters/{character['id']}", json={"name": None})
    assert response.status_code == 422


def test_real_person_requires_active_face_consent(client: TestClient) -> None:
    real = {**CHARACTER, "is_real_person": True}
    assert client.post("/api/characters", json=real).json()["error"]["code"] == "CONSENT_REQUIRED"

    voice = client.post(
        "/api/consents",
        json={"subject_type": "voice", "subject_name": "Jane", "granted_by": "Me", "confirm": True},
    ).json()
    wrong = client.post("/api/characters", json={**real, "consent_id": voice["id"]})
    assert wrong.json()["error"]["code"] == "CONSENT_REQUIRED"

    face = client.post(
        "/api/consents",
        json={"subject_type": "face", "subject_name": "Jane", "granted_by": "Me", "confirm": True},
    ).json()
    assert face["statement"] == "I have permission to use this person's likeness."
    ok = client.post("/api/characters", json={**real, "consent_id": face["id"]})
    assert ok.status_code == 201

    client.post(f"/api/consents/{face['id']}/revoke")
    blocked = client.patch(f"/api/characters/{ok.json()['id']}", json={"hair": "blond"})
    assert blocked.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_consent_requires_explicit_confirmation(client: TestClient) -> None:
    body = {"subject_type": "face", "subject_name": "Jane", "granted_by": "Me", "confirm": False}
    assert client.post("/api/consents", json=body).status_code == 422


def test_character_asset_roles(client: TestClient, upload: Callable[..., dict]) -> None:
    character = client.post("/api/characters", json=CHARACTER).json()
    asset = upload()
    url = f"/api/characters/{character['id']}/assets"

    attached = client.post(url, json={"asset_id": asset["id"], "role": "canonical"})
    assert attached.status_code == 201
    assert attached.json()["assets"][0]["asset"]["id"] == asset["id"]

    assert client.post(url, json={"asset_id": asset["id"], "role": "canonical"}).status_code == 409
    assert client.post(url, json={"asset_id": asset["id"], "role": "drone"}).status_code == 415
    assert client.post(url, json={"asset_id": "AST_missing", "role": "reference"}).status_code == 404

    assert client.delete(f"{url}/{asset['id']}").status_code == 204
    assert client.get(f"/api/characters/{character['id']}").json()["assets"] == []


# --------------------------------------------------------------------------- products


def test_product_price_requires_currency(client: TestClient) -> None:
    assert client.post("/api/products", json={"name": "P", "price": "10.50"}).status_code == 422
    product = client.post("/api/products", json={"name": "P", "price": "10.50", "currency": "try"}).json()
    assert product["currency"] == "TRY"
    assert product["price"] == "10.50"
    assert client.patch(f"/api/products/{product['id']}", json={"currency": None}).status_code == 422


def test_product_website_must_be_http(client: TestClient) -> None:
    bad = client.post("/api/products", json={"name": "P", "website": "javascript:alert(1)"})
    assert bad.status_code == 422
    ok = client.post("/api/products", json={"name": "P", "website": "https://example.com/p"})
    assert ok.json()["website"] == "https://example.com/p"


def test_product_features_are_cleaned(client: TestClient) -> None:
    product = client.post("/api/products", json={"name": "P", "features": [" 50 ml ", "", "  "]}).json()
    assert product["features"] == ["50 ml"]


# --------------------------------------------------------------------------- properties


def test_land_with_verified_facts(client: TestClient) -> None:
    land = client.post(
        "/api/properties",
        json={
            "category": "land",
            "title": "Seaside plot",
            "land_square_meters": 1250,
            "zoning": "Konut, TAKS 0.20",
            "parcel_info": "Ada 101, Parsel 5",
            "latitude": 36.85,
            "longitude": 28.27,
            "price": "4500000",
            "currency": "TRY",
            "mark_facts_verified": True,
        },
    ).json()
    assert land["facts_verified_at"] is not None
    assert land["electricity"] is None  # unknown stays unknown

    renamed = client.patch(f"/api/properties/{land['id']}", json={"title": "Seaside plot (new)"}).json()
    assert renamed["facts_verified_at"] is not None  # non-fact edit keeps verification

    edited = client.patch(f"/api/properties/{land['id']}", json={"zoning": "Tarla"}).json()
    assert edited["facts_verified_at"] is None  # fact edit invalidates verification

    reverified = client.patch(f"/api/properties/{land['id']}", json={"mark_facts_verified": True}).json()
    assert reverified["facts_verified_at"] is not None


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": 36.8},
        {"latitude": 95, "longitude": 10},
        {"square_meters": -5},
        {"price": "100"},
    ],
)
def test_property_fact_validation(client: TestClient, payload: dict) -> None:
    response = client.post("/api/properties", json={"category": "property", "title": "Villa", **payload})
    assert response.status_code == 422


def test_property_filter_by_category(client: TestClient) -> None:
    client.post("/api/properties", json={"category": "property", "title": "Villa", "rooms": "4+1"})
    client.post("/api/properties", json={"category": "land", "title": "Plot"})
    lands = client.get("/api/properties", params={"category": "land"}).json()
    assert [p["title"] for p in lands["items"]] == ["Plot"]


def test_property_footage_requires_video(client: TestClient, upload: Callable[..., dict]) -> None:
    prop = client.post("/api/properties", json={"category": "property", "title": "Villa"}).json()
    image = upload()
    url = f"/api/properties/{prop['id']}/assets"
    assert client.post(url, json={"asset_id": image["id"], "role": "footage"}).status_code == 415
    assert client.post(url, json={"asset_id": image["id"], "role": "photo"}).status_code == 201


# --------------------------------------------------------------------------- projects


def test_project_crud_and_references(client: TestClient) -> None:
    character = client.post("/api/characters", json=CHARACTER).json()
    product = client.post("/api/products", json={"name": "Perfume"}).json()

    missing = client.post("/api/projects", json={"type": "product_ad", "name": "X", "product_id": "PRD_nope"})
    assert missing.status_code == 404

    project = client.post(
        "/api/projects",
        json={
            "type": "product_ad",
            "name": "Launch",
            "character_id": character["id"],
            "product_id": product["id"],
            "settings": {"platform": "tiktok", "duration_s": 15, "aspect_ratio": "9:16", "tone": "luxury"},
        },
    ).json()
    assert project["settings"]["platform"] == "tiktok"

    bad_settings = client.patch(f"/api/projects/{project['id']}", json={"settings": {"duration_s": 45}})
    assert bad_settings.status_code == 422

    # Deleting a referenced entity nulls the reference instead of failing.
    client.delete(f"/api/characters/{character['id']}")
    assert client.get(f"/api/projects/{project['id']}").json()["character_id"] is None

    listing = client.get("/api/projects", params={"type": "product_ad"}).json()
    assert listing["total"] == 1
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204


def test_pagination_bounds(client: TestClient) -> None:
    for i in range(3):
        client.post("/api/products", json={"name": f"P{i}"})
    page = client.get("/api/products", params={"limit": 2, "offset": 1}).json()
    assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (3, 2, 1, 2)
    assert client.get("/api/products", params={"limit": 0}).status_code == 422
    assert client.get("/api/products", params={"limit": 500}).status_code == 422
