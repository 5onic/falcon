import importlib
import os

import pytest

import falcon
from falcon import testing
import falcon.constants
from falcon.routing import util

try:
    import cython
except ImportError:
    cython = None

FALCON_CUSTOM_HTTP_METHODS = ['FOO', 'BAR']


@pytest.fixture
def resource_things():
    return ThingsResource()


@pytest.fixture
def cleanup_constants():
    # Forcing reload to make sure we used a module import and didn't import
    # the list directly.
    importlib.reload(falcon.constants)
    yield
    falcon.constants.COMBINED_METHODS = list(
        set(falcon.constants.COMBINED_METHODS) - set(FALCON_CUSTOM_HTTP_METHODS)
    )

    if 'FALCON_CUSTOM_HTTP_METHODS' in os.environ:
        del os.environ['FALCON_CUSTOM_HTTP_METHODS']


@pytest.fixture
def custom_http_client(cleanup_constants, resource_things):
    falcon.constants.COMBINED_METHODS += FALCON_CUSTOM_HTTP_METHODS

    app = falcon.App()
    app.add_route('/things', resource_things)
    return testing.TestClient(app)


class ThingsResource:
    def __init__(self):
        self.called = False

        # Test non-callable attribute
        self.on_patch = {}

    # Field names ordered differently than in uri template
    def on_foo(self, req, resp):
        self.called = True
        self.req, self.resp = req, resp
        resp.status = falcon.HTTP_204


def test_map_http_methods(custom_http_client, resource_things):
    method_map = util.map_http_methods(resource_things)

    assert 'FOO' in method_map
    assert 'BAR' not in method_map


@pytest.mark.skipif(cython, reason='Reloading modules on Cython does not work')
@pytest.mark.parametrize('env_str,expected', [
    ('foo', ['FOO']),
    ('FOO', ['FOO']),
    ('FOO,', ['FOO']),
    ('FOO,BAR', ['FOO', 'BAR']),
    ('FOO, BAR', ['FOO', 'BAR']),
    (' foo , BAR ', ['FOO', 'BAR']),
])
def test_environment_override(cleanup_constants, resource_things, env_str, expected):
    # Make sure we don't have anything in there
    for method in expected:
        assert method not in falcon.constants.COMBINED_METHODS

    os.environ['FALCON_CUSTOM_HTTP_METHODS'] = env_str

    # Reload module to pick up environment variable methods
    importlib.reload(falcon.constants)

    # Now it should be there
    for method in expected:
        assert method in falcon.constants.COMBINED_METHODS


def test_foo(custom_http_client, resource_things):
    """FOO is a supported method, so returns HTTP_204"""
    custom_http_client.app.add_route('/things', resource_things)
    response = custom_http_client.simulate_request(path='/things', method='FOO')

    assert 'FOO' in falcon.constants.COMBINED_METHODS
    assert response.status == falcon.HTTP_204
    assert resource_things.called


def test_bar(custom_http_client, resource_things):
    """BAR is not supported by ResourceThing"""
    custom_http_client.app.add_route('/things', resource_things)
    response = custom_http_client.simulate_request(path='/things', method='BAR')

    assert 'BAR' in falcon.constants.COMBINED_METHODS
    assert response.status == falcon.HTTP_405
