from aiohttp import web
import pathlib
from typing import Literal

from module_misc import domain_name
domain_name: str

from module_private_routes import routes, redirects

# Route Tables
routes: web.RouteTableDef
redirects: web.RouteTableDef

# Routes
routes.static('/Resources', pathlib.Path('Resources'))
routes.static('/SVG',       pathlib.Path('SVG'))
routes.static('/static',    pathlib.Path('static'), show_index=True)


@routes.get('/robots.txt')
async def robots(request: web.Request):
    return web.Response(
        body=b"User-agent: Twitterbot/1.0\r\nDisallow:\r\nUser-agent: *\r\nDisallow: /", 
        content_type="text/plain"
    )


@routes.get('/favicon.ico') # In-browser Icon
async def favicon(request: web.Request):
    with open('Resources/favicon.ico', 'rb') as fh:
        return web.Response(body=fh.read(), content_type='image/x-icon')


@routes.get('/') # Homepage
async def root(request: web.Request):
    with open('index.html', 'rb') as fh:
        return web.Response(body=fh.read(), content_type='text/html')


# Redirect any straggler request (regardless of contents) to homepage
@routes.route('*', r'/{uri:\S*}')
async def wildcardMethod(request: web.Request):
    raise web.HTTPFound(f"https://www.{domain_name}/")


# Domain/Port redirect to HTTPS
@redirects.route('*', r'/{uri:\S*}')
async def redirect(request: web.Request):
    raw_path = request.raw_path.lstrip('/')
    raise web.HTTPPermanentRedirect(f'https://www.{domain_name}/{raw_path}')
