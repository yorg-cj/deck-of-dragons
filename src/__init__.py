# Patch SSL globally so all libraries (httpx, transformers, huggingface_hub, etc.)
# use the system trust store. Required on corporate networks with a proxy CA.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
