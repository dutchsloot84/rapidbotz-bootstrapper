import os
import sys
from pathlib import Path

import certifi
import pytest
import requests

# Ensure package import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rbz import Options, resolve_ca_bundle, build_session


def test_resolve_ca_bundle_precedence(monkeypatch, tmp_path):
    cli = tmp_path / "cli.pem"
    env = tmp_path / "env.pem"
    req = tmp_path / "req.pem"
    ssl_file = tmp_path / "ssl.pem"
    for p in (cli, env, req, ssl_file):
        p.write_text("cert")

    opts = Options(ca_bundle=str(cli))
    monkeypatch.setenv("RAPIDBOTZ_CA_BUNDLE", str(env))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(req))
    monkeypatch.setenv("SSL_CERT_FILE", str(ssl_file))
    assert resolve_ca_bundle(opts) == str(cli)

    opts = Options()
    monkeypatch.setenv("RAPIDBOTZ_CA_BUNDLE", str(env))
    assert resolve_ca_bundle(opts) == str(env)

    monkeypatch.delenv("RAPIDBOTZ_CA_BUNDLE")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(req))
    assert resolve_ca_bundle(opts) == str(req)

    monkeypatch.delenv("REQUESTS_CA_BUNDLE")
    monkeypatch.setenv("SSL_CERT_FILE", str(ssl_file))
    assert resolve_ca_bundle(opts) == str(ssl_file)

    monkeypatch.delenv("SSL_CERT_FILE")
    assert resolve_ca_bundle(opts) == certifi.where()


def test_insecure_verify_false():
    opts = Options(insecure=True)
    session = build_session(opts)
    assert session.verify is False


def test_default_timeout(monkeypatch):
    captured = {}

    def fake_request(self, method, url, **kwargs):
        captured['timeout'] = kwargs.get('timeout')
        class Dummy:
            status_code = 200
            def close(self):
                pass
        return Dummy()

    monkeypatch.setattr(requests.Session, 'request', fake_request, raising=False)
    opts = Options(timeout=12)
    session = build_session(opts)
    session.request('GET', 'http://example.com')
    assert captured['timeout'] == 12
    session.request('GET', 'http://example.com', timeout=1)
    assert captured['timeout'] == 1
