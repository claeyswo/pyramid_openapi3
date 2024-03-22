"""Tests for app creation when using pyramid_openapi3."""

from _pytest.fixtures import SubRequest
from _pytest.logging import LogCaptureFixture
from pyramid.config import Configurator
from pyramid.request import Request
from pyramid.testing import testConfig
from pyramid_openapi3 import MissingEndpointsError

import logging
import os
import pytest
import tempfile
import typing as t

DOCUMENT = b"""
    openapi: "3.1.0"
    info:
      version: "1.0.0"
      title: Foo API
    servers:
      - url: /api/v1
    paths:
      /foo:
        get:
          responses:
            200:
              description: A foo
        post:
          responses:
            200:
              description: A POST foo
      /bar:
        get:
          responses:
            200:
              description: A bar
"""

SPLIT_DOCUMENT = b"""
    openapi: "3.1.0"
    info:
      version: "1.0.0"
      title: Foo API
    servers:
      - url: /api/v1
    paths:
      /foo:
        $ref: "paths.yaml#/foo"
      /bar:
        $ref: "paths.yaml#/bar"
"""

SPLIT_DOCUMENT_PATHS = b"""
    foo:
      get:
        responses:
          200:
            description: A foo
      post:
        responses:
          200:
            description: A POST foo
    bar:
      get:
        responses:
          200:
            description: A bar
"""

# A test for when someone defines a `server.url` to just be `/`
ROOT_SERVER_DOCUMENT = b"""
    openapi: "3.1.0"
    info:
      version: "1.0.0"
      title: Foo API
    servers:
      - url: /
    paths:
      /foo:
        get:
          responses:
            200:
              description: A foo
        post:
          responses:
            200:
              description: A POST foo
      /bar:
        get:
          responses:
            200:
              description: A bar
"""


def foo_view(request: Request) -> str:
    """Return a dummy string."""
    return "Foo"  # pragma: no cover


def bar_view(request: Request) -> str:
    """Return a dummy string."""
    return "Bar"  # pragma: no cover


@pytest.fixture
def document() -> t.Generator[t.IO, None, None]:
    """Load the DOCUMENT into a temp file."""
    with tempfile.NamedTemporaryFile() as document:
        document.write(DOCUMENT)
        document.seek(0)

        yield document


@pytest.fixture
def directory_document() -> t.Generator[str, None, None]:
    """Load the DOCUMENT into a temp file."""
    with tempfile.TemporaryDirectory() as directory:
        spec_name = os.path.join(directory, "openapi.yaml")
        spec_paths_name = os.path.join(directory, "paths.yaml")
        with open(spec_name, "wb") as f:
            f.write(SPLIT_DOCUMENT)
        with open(spec_paths_name, "wb") as f:
            f.write(SPLIT_DOCUMENT_PATHS)

        yield spec_name


@pytest.fixture
def root_server_document() -> t.Generator[t.IO, None, None]:
    """Load the ROOT_SERVER_DOCUMENT into a temp file."""
    with tempfile.NamedTemporaryFile() as document:
        document.write(ROOT_SERVER_DOCUMENT)
        document.seek(0)

        yield document


@pytest.fixture
def simple_config() -> Configurator:
    """Config fixture."""
    with testConfig() as config:
        config.include("pyramid_openapi3")

        yield config


@pytest.fixture
def simple_app_config(
    simple_config: Configurator, document: t.IO
) -> t.Generator[Configurator, None, None]:
    """Incremented fixture that loads the DOCUMENT above into the config."""
    simple_config.pyramid_openapi3_spec(
        document.name, route="/foo.yaml", route_name="foo_api_spec"
    )
    yield simple_config


@pytest.fixture
def split_file_app_config(
    simple_config: Configurator, directory_document: str
) -> t.Generator[Configurator, None, None]:
    """Incremented fixture that loads the SPLIT_DOCUMENT above into the config."""
    simple_config.pyramid_openapi3_spec_directory(
        directory_document, route="/foo", route_name="foo_api_spec"
    )
    yield simple_config


@pytest.fixture
def root_server_app_config(
    simple_config: Configurator, root_server_document: t.IO
) -> t.Generator[Configurator, None, None]:
    """Incremented fixture that loads the ROOT_SERVER_DOCUMENT above into the config."""
    simple_config.pyramid_openapi3_spec(
        root_server_document.name, route="/foo.yaml", route_name="foo_api_spec"
    )
    yield simple_config


app_config = pytest.mark.parametrize(
    "app_config",
    [
        "simple_app_config",
        "split_file_app_config",
    ],
)


@app_config
def test_all_routes(app_config: Configurator, request: SubRequest) -> None:
    """Test case showing that an app can be created with all routes defined."""
    app_config = request.getfixturevalue(app_config)
    app_config.add_route(name="foo", pattern="/foo")
    app_config.add_route(name="bar", pattern="/bar")
    app_config.add_view(
        foo_view, route_name="foo", renderer="string", request_method="OPTIONS"
    )
    app_config.add_view(
        bar_view, route_name="bar", renderer="string", request_method="GET"
    )

    app_config.make_wsgi_app()


@app_config
def test_prefixed_routes(app_config: Configurator, request: SubRequest) -> None:
    """Test case for prefixed routes."""
    app_config = request.getfixturevalue(app_config)
    app_config.add_route(name="foo", pattern="/api/v1/foo")
    app_config.add_route(name="bar", pattern="/api/v1/bar")
    app_config.add_view(
        foo_view, route_name="foo", renderer="string", request_method="OPTIONS"
    )
    app_config.add_view(
        bar_view, route_name="bar", renderer="string", request_method="GET"
    )

    app_config.make_wsgi_app()


@app_config
def test_pyramid_prefixed_context_routes(
    app_config: Configurator, request: SubRequest
) -> None:
    """Test case for prefixed routes using pyramid route_prefix_context."""
    app_config = request.getfixturevalue(app_config)
    with app_config.route_prefix_context("/api/v1"):
        app_config.add_route(name="foo", pattern="/foo")
        app_config.add_route(name="bar", pattern="/bar")
    app_config.add_view(
        foo_view, route_name="foo", renderer="string", request_method="OPTIONS"
    )
    app_config.add_view(
        bar_view, route_name="bar", renderer="string", request_method="GET"
    )

    app_config.make_wsgi_app()


@app_config
def test_missing_routes(app_config: Configurator, request: SubRequest) -> None:
    """Test case showing app creation fails, when defined routes are missing."""
    app_config = request.getfixturevalue(app_config)
    with pytest.raises(MissingEndpointsError) as ex:
        app_config.make_wsgi_app()

    assert str(ex.value) == "Unable to find routes for endpoints: /foo, /bar"


@app_config
def test_disable_endpoint_validation(
    app_config: Configurator, caplog: LogCaptureFixture, request: SubRequest
) -> None:
    """Test case showing app creation whilst disabling endpoint validation."""
    caplog.set_level(logging.INFO)
    app_config = request.getfixturevalue(app_config)
    app_config.registry.settings["pyramid_openapi3.enable_endpoint_validation"] = False
    app_config.add_route(name="foo", pattern="/foo")
    app_config.add_view(
        foo_view, route_name="foo", renderer="string", request_method="GET"
    )

    app_config.make_wsgi_app()

    assert "Endpoint validation against specification is disabled" in caplog.text


def test_unconfigured_app(
    simple_config: Configurator, caplog: LogCaptureFixture
) -> None:
    """Asserts the app can be created if no spec has been defined."""
    caplog.set_level(logging.INFO)
    simple_config.add_route(name="foo", pattern="/foo")
    simple_config.add_view(
        foo_view, route_name="foo", renderer="string", request_method="OPTIONS"
    )

    simple_config.make_wsgi_app()
    assert "pyramid_openapi3 settings not found" in caplog.text


@app_config
def test_routes_setting_generation(
    app_config: Configurator, request: SubRequest
) -> None:
    """Test the `routes` setting is correctly created after app creation."""
    app_config = request.getfixturevalue(app_config)

    # Test that having multiple routes for a single route / pattern still works
    app_config.add_route(name="get_foo", pattern="/foo", request_method="GET")
    app_config.add_route(name="create_foo", pattern="/foo", request_method="POST")

    # Test the simple case of having no predicates on a route
    app_config.add_route(name="bar", pattern="/bar")

    # Add the views (needed for app creation)
    app_config.add_view(
        foo_view, route_name="get_foo", renderer="string", request_method="GET"
    )
    app_config.add_view(
        foo_view, route_name="create_foo", renderer="string", request_method="POST"
    )
    app_config.add_view(
        bar_view, route_name="bar", renderer="string", request_method="GET"
    )

    app_config.make_wsgi_app()

    settings = app_config.registry.settings["pyramid_openapi3"]
    # Assert that the `routes` setting object was created
    assert settings.get("routes") is not None
    # Assert that all 3 route names are in the `routes` setting
    # These should all map to `pyramid_openapi3` since that it the default apiname
    assert settings["routes"]["get_foo"] == "pyramid_openapi3"
    assert settings["routes"]["create_foo"] == "pyramid_openapi3"
    assert settings["routes"]["bar"] == "pyramid_openapi3"


def test_root_server_routes(root_server_app_config: Configurator) -> None:
    """Test case for when you have a server, but with url of /."""
    root_server_app_config.add_route(name="foo", pattern="/foo")
    root_server_app_config.add_route(name="bar", pattern="/bar")
    root_server_app_config.add_view(
        foo_view, route_name="foo", renderer="string", request_method="OPTIONS"
    )
    root_server_app_config.add_view(
        bar_view, route_name="bar", renderer="string", request_method="GET"
    )

    root_server_app_config.make_wsgi_app()
