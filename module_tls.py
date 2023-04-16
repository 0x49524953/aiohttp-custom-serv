import ssl
from module_misc import domain_name

ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
ssl_context.options |= ssl.OP_NO_TLSv1
ssl_context.options |= ssl.OP_NO_TLSv1_1
ssl_context.set_ciphers("ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305")
ssl_context.set_ecdh_curve("secp384r1")

ssl_context.load_cert_chain(
    certfile=f'/etc/letsencrypt/live/{domain_name}/fullchain.pem',
    keyfile=f'/etc/letsencrypt/live/{domain_name}/privkey.pem'
)
