import os
from dataclasses import dataclass
from typing import Dict, Optional

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class Options:
    timeout: float = 30.0
    ca_bundle: Optional[str] = None
    proxies: Optional[Dict[str, str]] = None
    insecure: bool = False
    retries: int = 3
    backoff_factor: float = 0.5
    user_agent: str = "rapidbotz-bootstrapper/1.0"
    extra_headers: Optional[Dict[str, str]] = None


def resolve_ca_bundle(options: Options):
    if options.insecure:
        return False
    if options.ca_bundle:
        return options.ca_bundle
    env = os.getenv("RAPIDBOTZ_CA_BUNDLE")
    if env:
        return env
    env = os.getenv("REQUESTS_CA_BUNDLE")
    if env:
        return env
    env = os.getenv("SSL_CERT_FILE")
    if env:
        return env
    return certifi.where()


def build_session(options: Options) -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=options.retries,
        connect=options.retries,
        read=options.retries,
        status=options.retries,
        backoff_factor=options.backoff_factor,
        status_forcelist=[502, 503, 504],
        allowed_methods={"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"},
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.verify = resolve_ca_bundle(options)

    if options.proxies:
        session.proxies.update(options.proxies)

    session.headers["User-Agent"] = options.user_agent
    if options.extra_headers:
        session.headers.update(options.extra_headers)

    return session
