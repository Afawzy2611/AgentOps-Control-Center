def test_server_uses_render_port_and_all_interfaces(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    from app import server
    assert server.get_server_config() == ("0.0.0.0", 10000)
