"""Las pruebas unitarias nunca deben consultar servicios externos."""
import pytest
import requests


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('HTTP externo no simulado en una prueba unitaria')
    monkeypatch.setattr(requests.sessions.Session,'request',forbidden)
