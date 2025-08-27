import argparse
import os
import socket
import ssl
import sys
import tempfile
from datetime import datetime

import certifi
import requests
import urllib3

from rbz.http import Options, resolve_ca_bundle, build_session


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnose SSL configuration")
    parser.add_argument("--ca-bundle", help="Path to a custom CA bundle")
    parser.add_argument("--proxy", help="Proxy URL for both HTTP and HTTPS")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    return parser.parse_args()


def print_versions():
    print(f"Python: {sys.version}")
    print(f"OpenSSL: {ssl.OPENSSL_VERSION}")
    print(f"requests: {requests.__version__}")
    print(f"urllib3: {urllib3.__version__}")
    print(f"certifi: {certifi.__version__}")


def print_env_proxies():
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        print(f"{var}={os.environ.get(var)}")


def describe_ca_source(options: Options, ca_path: str) -> str:
    if options.ca_bundle:
        return f"--ca-bundle ({ca_path})"
    if os.environ.get("RAPIDBOTZ_CA_BUNDLE"):
        return f"RAPIDBOTZ_CA_BUNDLE ({ca_path})"
    if os.environ.get("REQUESTS_CA_BUNDLE"):
        return f"REQUESTS_CA_BUNDLE ({ca_path})"
    if os.environ.get("SSL_CERT_FILE"):
        return f"SSL_CERT_FILE ({ca_path})"
    return f"certifi ({ca_path})"


def fetch_github_cert(session: requests.Session):
    host = "api.github.com"
    try:
        ctx = ssl.create_default_context()
        if session.verify and isinstance(session.verify, str):
            ctx.load_verify_locations(session.verify)
        with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
            s.settimeout(5)
            s.connect((host, 443))
            der = s.getpeercert(True)
    except Exception as e:
        print(f"Error fetching certificate: {e}")
        return False

    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(der)
    tmp.close()
    cert = ssl._ssl._test_decode_cert(tmp.name)
    os.unlink(tmp.name)
    subject = dict(x[0] for x in cert["subject"])
    issuer = dict(x[0] for x in cert["issuer"])
    sans = [san[1] for san in cert.get("subjectAltName", [])]
    not_before = cert.get("notBefore")
    not_after = cert.get("notAfter")
    print("Certificate subject:", subject)
    print("Certificate issuer:", issuer)
    print("Subject Alt Names:", sans)
    print("Validity:", not_before, "to", not_after)
    issuer_str = " ".join(issuer.values())
    if "Netskope" in issuer_str or "Corporate" in issuer_str:
        print("LIKELY TLS inspection in place")
        return False
    return True


def main():
    args = parse_args()
    proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None
    options = Options(ca_bundle=args.ca_bundle, proxies=proxies, insecure=args.insecure)
    session = build_session(options)

    print_versions()
    print("Effective CA bundle:", describe_ca_source(options, resolve_ca_bundle(options)))
    print_env_proxies()
    print("ssl.get_default_verify_paths():", ssl.get_default_verify_paths())

    ok = fetch_github_cert(session)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
