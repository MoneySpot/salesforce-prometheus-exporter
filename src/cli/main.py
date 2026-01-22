import logging
import secrets
from functools import wraps
from importlib.metadata import entry_points
from os import environ
from wsgiref.simple_server import make_server

logging.basicConfig(level=logging.INFO)

from click import INT, group, option, pass_context
from click_plugins import with_plugins
from flask import Flask
from prometheus_client import make_wsgi_app
from prometheus_client.core import REGISTRY
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from cli.collect import Collector

app = Flask(__name__)


def get_api_key():
    """Get API key from environment variable."""
    return environ.get("API_KEY")


def require_auth(wsgi_app):
    """Middleware to require API key authentication."""

    @wraps(wsgi_app)
    def auth_wrapper(env, start_response):
        api_key = get_api_key()

        # If no API key configured, allow all requests
        if not api_key:
            return wsgi_app(env, start_response)

        # Check Authorization header (Bearer token)
        auth_header = env.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if secrets.compare_digest(token, api_key):
                return wsgi_app(env, start_response)

        # Check X-API-Key header
        x_api_key = env.get("HTTP_X_API_KEY", "")
        if x_api_key and secrets.compare_digest(x_api_key, api_key):
            return wsgi_app(env, start_response)

        # Check query parameter (for testing, less secure)
        query_string = env.get("QUERY_STRING", "")
        query_key = None
        for param in query_string.split("&"):
            if param.startswith("api_key="):
                query_key = param[8:]
                break
        if query_key and secrets.compare_digest(query_key, api_key):
            return wsgi_app(env, start_response)

        # Authentication failed
        start_response(
            "401 Unauthorized",
            [
                ("Content-Type", "text/plain"),
                ("WWW-Authenticate", "Bearer"),
            ],
        )
        return [b"Unauthorized: Invalid or missing API key"]

    return auth_wrapper


@with_plugins(entry_points(group="click_command_tree"))
@group()
@pass_context
def main(context):
    """
    main entry point for salesforce exporter
    """
    pass


def health(env, start_response):
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"OK"]


def home(env, start_response):
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"<h1> Salesforce Prometheus Exporter (SFDC) </h1>"]


@main.command("start-server")
@pass_context
@option("--port", default=None, type=INT)
def server(context, port):
    """
    Starting wsgi server for prometheus exporter.
    """
    # Respect PORT env var (for Fly.io), fall back to --port flag, then default to 3000
    if port is None:
        port = int(environ.get("PORT", 3000))
    logging.info("Registering Salesforce metrics collector...")
    REGISTRY.register(Collector())

    # Wrap metrics endpoint with auth, leave health/home unprotected
    metrics_app = require_auth(make_wsgi_app())

    app.wsgi_app = DispatcherMiddleware(
        app.wsgi_app, {"/": home, "/health": health, "/metrics": metrics_app}
    )

    if get_api_key():
        logging.info("API key authentication enabled for /metrics endpoint")
    else:
        logging.warning("No API_KEY set - /metrics endpoint is unprotected!")

    logging.info(f"Starting WSGI server on port {port}...")
    logging.info(f"Metrics available at http://0.0.0.0:{port}/metrics")
    httpd = make_server(host="", port=port, app=app)
    httpd.serve_forever()
