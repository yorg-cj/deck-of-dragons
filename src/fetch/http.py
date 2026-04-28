"""
Shared httpx client. On corporate networks with a proxy CA, uses the system
trust store via truststore. Falls back to default SSL verification otherwise.
"""
import ssl
import httpx

def _make_client() -> httpx.Client:
    try:
        import truststore
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return httpx.Client(verify=ctx, timeout=15)
    except ImportError:
        return httpx.Client(timeout=15)

# Module-level client — reused across all fetchers
client = _make_client()
