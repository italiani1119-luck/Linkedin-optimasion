"""Gunakan trust store sistem (Windows/macOS/Linux).

Berguna jika antivirus/proxy perusahaan melakukan inspeksi TLS: certifi bawaan
Python tidak mengenal CA proxy tersebut, sedangkan trust store OS mengenalnya.
"""
import logging

_injected = False

try:
    import truststore

    truststore.inject_into_ssl()
    _injected = True
except Exception:  # truststore opsional; fallback ke certifi
    logging.getLogger(__name__).warning("truststore tidak tersedia; memakai certifi bawaan.")
