import socket
import pytest

@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("net disabled"))
    )
