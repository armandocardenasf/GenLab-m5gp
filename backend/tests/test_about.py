from fastapi.testclient import TestClient

from genlab_api.main import app


def test_about_endpoint_is_public_and_complete():
    response = TestClient(app).get("/api/v1/about")
    assert response.status_code == 200
    payload = response.json()

    assert payload["product_name"] == "GenLab M5GP"
    assert payload["version"] == "1.0.0"
    assert payload["copyright"]["holder"] == "Dr. Luis Armando Cardenas Florido"
    assert "Tecnológico Nacional de México" in payload["supporting_institutions"]
    assert "Instituto Tecnológico de Ensenada" in payload["supporting_institutions"]
    assert len(payload["references"]) == 2
    assert payload["references"][0]["repository_url"].endswith("/m5gp")
    assert payload["references"][1]["repository_url"].endswith("/m5gp-2.0")
    assert payload["source_code"]["repository_url"].endswith("/GenLab-m5gp")
    assert payload["legal"]["public_source"] is True


def test_about_endpoint_is_in_openapi():
    payload = TestClient(app).get("/openapi.json").json()
    assert "/api/v1/about" in payload["paths"]
