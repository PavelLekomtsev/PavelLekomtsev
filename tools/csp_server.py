#!/usr/bin/env python3
"""Serve a folder; .svg responses get the same CSP header raw.githubusercontent.com sends.

usage: csp_server.py <dir> <port>
"""
import functools
import http.server
import sys

DIR, PORT = sys.argv[1], int(sys.argv[2])


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        if self.path.split("?")[0].endswith(".svg"):
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; sandbox")
            self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Handler, directory=DIR)).serve_forever()
