def test_request_id_is_returned_for_success_and_http_errors(client):
    success = client.get("/", headers={"X-Request-ID": "trace-success"})
    assert success.status_code == 200
    assert success.headers["X-Request-ID"] == "trace-success"

    unauthorized = client.get("/api/career/dashboard", headers={"X-Request-ID": "trace-auth"})
    assert unauthorized.status_code == 401
    assert unauthorized.headers["X-Request-ID"] == "trace-auth"
    assert unauthorized.json()["requestId"] == "trace-auth"
