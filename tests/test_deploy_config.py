import importlib.util
import json
from pathlib import Path

import pytest

from api import merge as merge_module

REPO_ROOT = Path(__file__).resolve().parents[1]
VERCEL_CONFIG = REPO_ROOT / "vercel.json"
FUNCTION_FILE = "api/merge.py"
FUNCTION_ROUTE = "/api/merge"

# Vercel loads a Python framework from these exact filenames, at the project
# root or inside one of these directories, and then reads a top-level `app`.
# A Flask preset claims every request, including `/`, so the Next.js site stops
# serving; see tests/test_deploy_config.py::test_no_python_framework_entrypoint.
FRAMEWORK_ENTRYPOINTS = (
    "app.py",
    "index.py",
    "server.py",
    "main.py",
    "wsgi.py",
    "asgi.py",
)
FRAMEWORK_ENTRYPOINT_DIRS = (REPO_ROOT, "src", "app", "api")


@pytest.fixture(scope="module")
def vercel_config():
    return json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))


def test_framework_preset_is_pinned_to_nextjs(vercel_config):
    assert vercel_config["framework"] == "nextjs"


def test_no_python_framework_entrypoint():
    found = sorted(
        f"{directory}/{name}"
        for directory in FRAMEWORK_ENTRYPOINT_DIRS
        for name in FRAMEWORK_ENTRYPOINTS
        if (REPO_ROOT / directory / name).is_file()
    )

    assert found == [], (
        "A Python framework entrypoint re-enables Flask preset detection, "
        "which takes precedence over the file-based function and the Next.js "
        f"pages. Found: {found}"
    )


def test_function_config_points_at_the_merge_function(vercel_config):
    assert list(vercel_config["functions"]) == [FUNCTION_FILE]
    assert (REPO_ROOT / FUNCTION_FILE).is_file()


def test_rewrite_destinations_resolve_to_the_function_route(vercel_config):
    sources = {}

    for rewrite in vercel_config["rewrites"]:
        sources[rewrite["source"]] = rewrite["destination"]
        assert rewrite["destination"] == FUNCTION_ROUTE

    assert sources["/api/:path*"] == FUNCTION_ROUTE
    assert sources["/health"] == FUNCTION_ROUTE


def test_function_file_loads_standalone_with_a_wsgi_app():
    spec = importlib.util.spec_from_file_location(
        "vc_handler", REPO_ROOT / FUNCTION_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.app)
    assert callable(module.app.wsgi_app)


def test_flask_serves_the_function_route_and_the_health_alias():
    rules = {rule.rule for rule in merge_module.app.url_map.iter_rules()}

    assert FUNCTION_ROUTE in rules
    assert "/health" in rules


def test_the_architecture_diagram_still_describes_the_routing(vercel_config):
    """The README diagram is the one place all three routing facts meet.

    `POST /api/merge`, `GET /health` and the two `vercel.json` rewrites are what
    the browser, Flask and the platform each have to agree on, and a wrong
    preset has already taken this site down once. A diagram drifts silently, so
    every route and rewrite is asserted against the drawing, along with the
    content type the function actually sends.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    diagram = readme.split("## Architecture", 1)[1].split("```")[1]

    # `static` is the endpoint Flask registers for its own static folder, not a
    # route this function declares.
    flask_routes = sorted(
        rule.rule
        for rule in merge_module.app.url_map.iter_rules()
        if rule.endpoint != "static"
    )
    for route in flask_routes:
        assert route in diagram, f"Flask route {route} is not in the diagram"

    for rewrite in vercel_config["rewrites"]:
        for key in ("source", "destination"):
            assert rewrite[key] in diagram, (
                f"vercel.json {key} {rewrite[key]!r} is not in the diagram"
            )

    assert merge_module.OUTPUT_MIME in diagram, (
        f"the diagram does not name the response type {merge_module.OUTPUT_MIME!r}"
    )
