# For AccessLogger
# For Application
import asyncio
import logging
# For StaticResource
import pathlib
import traceback
from contextlib import suppress
from html import escape as html_escape
from http import HTTPStatus
# For UrlDispatcher
from typing import List, Optional
from urllib.parse import quote as url_encode

from aiohttp import web, web_urldispatcher
from aiohttp.abc import AbstractAccessLogger
from aiohttp.typedefs import PathLike
# For RequestHandler
from aiohttp.web_protocol import RequestHandler

import module_misc
module_misc.font_url:   str # Path to custom font
module_misc.stylesheet: str # Path to custom stylesheet


class AccessLogger(web.AccessLogger):
    def log(self, request: web.Request, response: web.StreamResponse, time: float) -> None:
        # Output as:
        # [http(s)://domain-host] remoteIP StatusCode "HTTPMethod /path" HTTP/Version.Number [Response size in bytes] "UserAgent String"
        self.logger.info(
            f'[{request.scheme}://{request.host}] '
            f'{request.remote} {response.status} '
            f'"{request.method} {request.path_qs} '
            f'HTTP/{request.version.major}.{request.version.minor}" '
            f'[{response.body_length} bytes] '
            f'"{request.headers.get("User-Agent", "-")}"'
        )


class CustomRequestHandler(web.RequestHandler):
    def handle_error(
        self,
        request: web.BaseRequest,
        status: int = 500,
        exc: web.Optional[BaseException] = None,
        message: web.Optional[str] = None,
    ) -> web.StreamResponse:
        """Handle errors.
        Returns HTTP response with specific status code. Logs additional
        information. It always closes current connection."""
        ignored_codes: List[int] = [400,]

        # some data already got sent, connection is broken
        if request.writer.output_size > 0:
            raise ConnectionError(
                "Response is sent already, cannot send another response "
                "with the error message"
            )

        ct = "text/plain"
        if status == HTTPStatus.INTERNAL_SERVER_ERROR:
            title = "{0.value} {0.phrase}".format(HTTPStatus.INTERNAL_SERVER_ERROR)
            msg = HTTPStatus.INTERNAL_SERVER_ERROR.description
            tb = None
            if self._loop.get_debug():
                with suppress(Exception):
                    tb = traceback.format_exc()

            if "text/html" in request.headers.get("Accept", ""):
                if tb:
                    tb = html_escape(tb)
                    msg = f"<h2>Traceback:</h2>\n<pre>{tb}</pre>"
                message = (
                    "<html><head>"
                    "<title>{title}</title>"
                    "</head><body>\n<h1>{title}</h1>"
                    "\n{msg}\n</body></html>\n"
                ).format(title=title, msg=msg)
                ct = "text/html"
            else:
                if tb:
                    msg = tb
                message = title + "\n\n" + msg

        resp = web.Response(status=status, text=message, content_type=ct)
        resp.force_close()

        ## Don't print ignored codes to log,
        if status not in ignored_codes:
            self.log_exception("Error handling request", exc_info=exc)
        
        self.log_access(request, resp, 0)

        return resp


class CustomServer(web.Server):
    def __call__(self) -> RequestHandler:
        return CustomRequestHandler(
            self, 
            loop=self._loop, 
            **self._kwargs
        )


class CustomApplication(web.Application):
    def _make_handler(
        self, 
        *, 
        loop: web.Optional[asyncio.AbstractEventLoop], 
        access_log_class: web.Type[AbstractAccessLogger], 
        **kwargs: web.Any
    ) -> web.Server:
        if not issubclass(access_log_class, AbstractAccessLogger):
            raise TypeError(
                "access_log_class must be subclass of "
                "aiohttp.abc.AbstractAccessLogger, got {}".format(access_log_class)
            )

        self._set_loop(loop)
        self.freeze()

        kwargs["debug"] = self._debug
        kwargs["access_log_class"] = access_log_class
        if self._handler_args:
            for k, v in self._handler_args.items():
                kwargs[k] = v

        return CustomServer(
            self._handle,  # type: ignore
            request_factory=self._make_request,
            loop=self._loop,
            **kwargs,
        )


class CustomStaticResource(web.StaticResource):
    async def _handle(self, request: web.Request) -> web.StreamResponse:
        # Type hinting helpers
        this_directory: pathlib.Path = self._directory
        this_logger: logging.Logger = request.app.logger
        HTTPNotFound = web.HTTPNotFound(content_type='text/html')
        HTTPForbidden = web.HTTPForbidden(content_type='text/html')

        rel_url: str = request.match_info["filename"]
        try:
            filename: pathlib.Path = pathlib.Path(rel_url)

            if filename.anchor:
                # rel_url is an absolute name like
                # /static/\\machine_name\c$ or /static/D:\path
                # where the static dir is totally different
                raise HTTPForbidden

            filepath: pathlib.Path = this_directory.joinpath(filename).resolve()

            if not self._follow_symlinks:
                filepath.relative_to(self._directory)

        except (ValueError, FileNotFoundError) as error:
            raise HTTPNotFound from error

        except web.HTTPForbidden:
            raise

        except Exception as error:
            # perm error or other kind!
            this_logger.exception(error)
            raise HTTPNotFound from error

        if filepath.exists():
            if filepath.is_dir():
                if self._show_index: 
                    try: 
                        return web.Response(
                            body=self._directory_as_html(filepath, request.path).encode('utf8'),
                            content_type="text/html"
                        )

                    except PermissionError: 
                        raise HTTPForbidden

                else: raise HTTPForbidden

            elif filepath.is_file():
                return web.FileResponse(filepath, chunk_size=self._chunk_size)

        else: raise HTTPNotFound

    def _directory_as_html(
        self,
        filepath: pathlib.Path,
        request_path: PathLike,
        newline:str = "\n",
        tab:str = "    "
    ) -> str:
        assert filepath.is_dir()

        virtual_path = pathlib.Path(request_path)
        index_header = f"<h1>Index of <wbr>{html_escape(request_path)}</h1>"
        head = (
            '<meta charset="utf-8" />',
            f'<link rel="preload" href="{module_misc.stylesheet}" as="style" type="text/css">',
            f'<link rel="preload" href="{module_misc.font_url}" as="font" type="font/ttf" crossorigin />',
            f"<title>Index of {html_escape(request_path)}</title>",
            f'<link rel="stylesheet" href="{module_misc.stylesheet}" />'
        )

        #           # Display name:  URL construction
        parent =    { '../':        (virtual_path/'..').as_posix() }
        folders =   { i.name + '/': (virtual_path/i.name).as_posix() for i in filepath.iterdir() if i.is_dir() }
        files =     { i.name:       (virtual_path/i.name).as_posix() for i in filepath.iterdir() if i.is_file() }
        list_items = parent | folders | files

        ul = (
            '<li>'
                f'<a href="{url_encode(url)}">'
                    f'{html_escape(text)}'
                '</a>'
            f'</li>' for text, url in list_items.items()
        )

        body = (
            index_header,
            "<ul>",
            *(tab + i for i in ul),
            "</ul>"
        )

        html_contents = (
            "<head>",
            *(tab + i for i in head),
            "</head>",
            "<body>",
            *(tab + i for i in body),
            "</body>"
        )

        page = (
            "<!DOCTYPE html>",
            "<html>",
            *(tab + i for i in html_contents),
            "</html>"
        )

        return newline.join(page)


class CustomUrlDispatcher(web.UrlDispatcher):
    def add_static(
        self, prefix: str, 
        path: PathLike, 
        *, 
        name: Optional[str] = None, 
        expect_handler: Optional[web_urldispatcher._ExpectHandler] = None, 
        chunk_size: int = 256 * 1024, 
        show_index: bool = False, 
        follow_symlinks: bool = False, 
        append_version: bool = False
        #with_notify: bool = False
    ) -> web.AbstractResource:
        """Add static files view.

        prefix - url prefix
        path - folder with files

        """
        assert prefix.startswith("/")
        prefix = prefix[:-1] if prefix.endswith("/") else prefix
        resource = CustomStaticResource(
            prefix,
            path,
            name=name,
            expect_handler=expect_handler,
            chunk_size=chunk_size,
            show_index=show_index,
            follow_symlinks=follow_symlinks,
            append_version=append_version
            #with_notify=with_notify   * TODO *
        )
        self.register_resource(resource)
        return resource