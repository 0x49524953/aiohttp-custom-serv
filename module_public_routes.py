from aiohttp import web
import pathlib
from typing import Literal

from module_misc import domain_name
domain_name: str


# Route Tables
public_routes = web.RouteTableDef()
public_redirects = web.RouteTableDef()

# Routes
public_routes.static('/Resources', pathlib.Path('Resources'))
public_routes.static('/SVG',       pathlib.Path('SVG'))
public_routes.static('/static',    pathlib.Path('static'), show_index=True)


@public_routes.get('/robots.txt')
async def robots(request: web.Request):
    return web.Response(
        body=b"User-agent: Twitterbot/1.0\r\nDisallow:\r\nUser-agent: *\r\nDisallow: /", 
        content_type="text/plain"
    )


@public_routes.get('/favicon.ico') # In-browser Icon
async def favicon(request: web.Request):
    with open('Resources/favicon.ico', 'rb') as fh:
        return web.Response(body=fh.read(), content_type='image/x-icon')


@public_routes.get('/') # Homepage
async def root(request: web.Request):
    with open('index.html', 'rb') as fh:
        return web.Response(body=fh.read(), content_type='text/html')


# Redirect any straggler request (regardless of contents) to homepage
@public_routes.route('*', r'/{uri:\S*}')
async def wildcardMethod(request: web.Request):
    raise web.HTTPFound(f"https://www.{domain_name}/")


# Domain/Port redirect to HTTPS
@public_redirects.route('*', r'/{uri:\S*}')
async def redirect(request: web.Request):
    raw_path = request.raw_path.lstrip('/')
    raise web.HTTPPermanentRedirect(f'https://www.{domain_name}/{raw_path}')
