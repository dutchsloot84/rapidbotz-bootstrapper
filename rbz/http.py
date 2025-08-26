from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


def _default_user_agent() -> str:
    """Return default User-Agent string."""
    version_file = Path(__file__).resolve().parent.parent / "version.txt"
    try:
        version = version_file.read_text().strip()
    except Exception:
        version = "0"
    return f"rapidbotz-bootstrapper/{version}"


@dataclass
class Options:
    timeout: float = 10.0
    ca_bundle: Optional[str] = None
    proxies: Optional[Dict[str, str]] = None
    insecure: bool = False
    retries: Retry = field(
        default_factory=lambda: Retry(
            total=3, connect=3, read=3, backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
        )
    )
    headers: Dict[str, str] = field(default_factory=dict)
    user_agent: str = field(default_factory=_default_user_agent)


def resolve_ca_bundle(options: Options) -> str:
    """Resolve CA bundle path from options and environment.

    Precedence:
    1. CLI --ca-bundle (options.ca_bundle)
    2. RAPIDBOTZ_CA_BUNDLE environment variable
    3. REQUESTS_CA_BUNDLE or SSL_CERT_FILE environment variables
    4. certifi.where()
    """
    if options.ca_bundle:
        return options.ca_bundle

    env = os.environ.get("RAPIDBOTZ_CA_BUNDLE")
    if env:
        return env

    for var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        env = os.environ.get(var)
        if env:
            return env

    return certifi.where()


def build_session(options: Options) -> requests.Session:
    """Build a configured requests session based on Options."""
    session = requests.Session()

    if options.insecure:
        warnings.warn("--insecure disables certificate verification; use only for local testing.")
        session.verify = False
    else:
        session.verify = resolve_ca_bundle(options)

    if options.proxies:
        session.proxies.update(options.proxies)

    adapter = HTTPAdapter(max_retries=options.retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {**options.headers, "User-Agent": options.user_agent}
    session.headers.update(headers)

    return session
