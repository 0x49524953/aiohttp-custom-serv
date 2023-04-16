from aiohttp import web
from typing import List, Coroutine
import os
import sys
import logging
import asyncio
import pathlib

os.chdir('/srv/http')
assert pathlib.Path('/srv/http').resolve() == pathlib.Path().resolve()

logging.basicConfig(format="%(message)s", level=logging.DEBUG)

# Import TLS context
from module_tls import ssl_context

# Import custom/modified classes
from module_classes import AccessLogger, CustomApplication, CustomUrlDispatcher
AccessLogger: web.AccessLogger
CustomApplication: web.Application
CustomUrlDispatcher: web.UrlDispatcher

# Import non-sensitive routes
from module_public_routes import public_routes, public_redirects
public_routes:      web.RouteTableDef
public_redirects:   web.RouteTableDef

# Import sensitive routes
# Includes private info!
from module_private_routes import private_routes
private_routes:     web.RouteTableDef

# Import domain name
from module_misc import domain_name, alt_domain_name
domain_name:        str # i.e. 'example_a.com'
alt_domain_name:    str # i.e. 'example_b.com'

# Main application for something like 'www.example_a.com'
www = CustomApplication()
www._router = CustomUrlDispatcher()
www.add_routes(public_routes)
www.add_routes(private_routes)

# Application to handle redirects for:
# '*.example_a.com'
# '*.example_b.com'
# 'example_a.com'
# 'example_b.com'
# Everything is redirected using the 'redirects()'
# coroutine defined in 'module_public_routes.py'
alt_subdomains = CustomApplication()
alt_subdomains.add_routes(public_redirects)

# Application to handle HTTPS/TLS traffic
https = CustomApplication()
https.add_domain(f'www.{domain_name}',      www) # Funnel all requests into this domain
https.add_domain(f'*.{domain_name}',        alt_subdomains)
https.add_domain(f'{domain_name}',          alt_subdomains)
https.add_domain(f'*.{alt_domain_name}',    alt_subdomains)
https.add_domain(f'{alt_domain_name}',      alt_subdomains)

# Application to redirect plaintext traffic to an encrypted channel
http = CustomApplication()
http.add_domain(f'*.{domain_name}',         alt_subdomains)
http.add_domain(f'{domain_name}',           alt_subdomains)
http.add_domain(f'*.{alt_domain_name}',     alt_subdomains)
http.add_domain(f'{alt_domain_name}',       alt_subdomains)


# List of 'aiohttp.web.AppRunner's to run the app, I guess
runners: List[web.AppRunner] = []

# Run an app
async def startsite(app, port, logger, ssl_context=None) -> Coroutine:
    runner = web.AppRunner(app, access_log_class=logger)
    runners.append(runner)
    await runner.setup()

    if ssl_context: # HTTPS
        site = web.TCPSite(runner, port=port, ssl_context=ssl_context)
    else: # Clear traffic
        site = web.TCPSite(runner, port=port)

    await site.start()

# Run *my* apps
async def amain():
    try:
        await startsite(https, 443, AccessLogger, ssl_context=ssl_context)
        await startsite(http,   80, AccessLogger)
        await asyncio.get_running_loop().create_future()
    finally:
        await asyncio.gather(*(runner.cleanup() for runner in runners))
    return 0


def main():
    try: return asyncio.run(amain())
    except KeyboardInterrupt: return 0


if __name__ == "__main__":
    sys.exit(main())
