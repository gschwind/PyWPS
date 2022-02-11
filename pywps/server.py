#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from http.server import BaseHTTPRequestHandler
from werkzeug.serving import WSGIRequestHandler, BaseWSGIServer

from socketserver import TCPServer
from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import NotFound

class WPSServer(BaseWSGIServer):
    def __init__(self, addr, port, service):
        super().__init__(addr, port, app=service)

    def service_actions(self):
        print("timeout")

    def serve_forever(self, poll_interval=10):
        super().serve_forever(poll_interval)

