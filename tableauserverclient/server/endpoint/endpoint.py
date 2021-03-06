from .exceptions import ServerResponseError, EndpointUnavailableError
from functools import wraps

import logging

try:
    from distutils2.version import NormalizedVersion as Version
except ImportError:
    from distutils.version import LooseVersion as Version

logger = logging.getLogger('tableau.endpoint')

Success_codes = [200, 201, 204]


class Endpoint(object):
    def __init__(self, parent_srv):
        self.parent_srv = parent_srv

    @staticmethod
    def _make_common_headers(auth_token, content_type):
        headers = {}
        if auth_token is not None:
            headers['x-tableau-auth'] = auth_token
        if content_type is not None:
            headers['content-type'] = content_type

        return headers

    def _make_request(self, method, url, content=None, request_object=None,
                      auth_token=None, content_type=None, parameters=None):
        if request_object is not None:
            url = request_object.apply_query_params(url)
        parameters = parameters or {}
        parameters.update(self.parent_srv.http_options)
        parameters['headers'] = Endpoint._make_common_headers(auth_token, content_type)

        if content is not None:
            parameters['data'] = content

        server_response = method(url, **parameters)
        self._check_status(server_response)

        # This check is to determine if the response is a text response (xml or otherwise)
        # so that we do not attempt to log bytes and other binary data.
        if server_response.encoding:
            logger.debug(u'Server response from {0}:\n\t{1}'.format(
                url, server_response.content.decode(server_response.encoding)))
        return server_response

    @staticmethod
    def _check_status(server_response):
        if server_response.status_code not in Success_codes:
            raise ServerResponseError.from_response(server_response.content)

    def get_unauthenticated_request(self, url, request_object=None):
        return self._make_request(self.parent_srv.session.get, url, request_object=request_object)

    def get_request(self, url, request_object=None, parameters=None):
        return self._make_request(self.parent_srv.session.get, url, auth_token=self.parent_srv.auth_token,
                                  request_object=request_object, parameters=parameters)

    def delete_request(self, url):
        # We don't return anything for a delete
        self._make_request(self.parent_srv.session.delete, url, auth_token=self.parent_srv.auth_token)

    def put_request(self, url, xml_request, content_type='text/xml'):
        return self._make_request(self.parent_srv.session.put, url,
                                  content=xml_request,
                                  auth_token=self.parent_srv.auth_token,
                                  content_type=content_type)

    def post_request(self, url, xml_request, content_type='text/xml'):
        return self._make_request(self.parent_srv.session.post, url,
                                  content=xml_request,
                                  auth_token=self.parent_srv.auth_token,
                                  content_type=content_type)


def api(version):
    '''Annotate the minimum supported version for an endpoint.

    Checks the version on the server object and compares normalized versions.
    It will raise an exception if the server version is > the version specified.

    Args:
        `version` minimum version that supports the endpoint. String.
    Raises:
        EndpointUnavailableError
    Returns:
        None

    Example:
    >>> @api(version="2.3")
    >>> def get(self, req_options=None):
    >>>     ...
    '''
    def _decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            server_version = Version(self.parent_srv.version)
            minimum_supported = Version(version)
            if server_version < minimum_supported:
                error = "This endpoint is not available in API version {}. Requires {}".format(
                    server_version, minimum_supported)
                raise EndpointUnavailableError(error)
            return func(self, *args, **kwargs)
        return wrapper
    return _decorator
