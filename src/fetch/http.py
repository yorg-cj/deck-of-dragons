"""
Shared httpx client that uses the system SSL trust store.
Required on corporate networks where a proxy re-signs HTTPS traffic
with a company root CA that Python's bundled certs don't include.
"""
import ssl
import truststore
import httpx

def _make_client() -> httpx.Client:
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return httpx.Client(verify=ctx, timeout=15)

# Module-level client — reused across all fetchers
client = _make_client()
