import flask

from fence.oidc.errors import InvalidClientError
from fence.oidc.jwt_generator import generate_token

from authlib.common.urls import urlparse, url_decode
from authlib.integrations.flask_oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749.authenticate_client import (
    ClientAuthentication as AuthlibClientAuthentication,
)

from authlib.oauth2.rfc6749.errors import (
    InvalidClientError as AuthlibClientError,
    OAuth2Error,
    UnsupportedGrantTypeError,
)
from authlib.integrations.flask_oauth2.requests import FlaskOAuth2Request

from fence import logger
from cdislogging import get_logger

logger = get_logger(__name__)


class ClientAuthentication(AuthlibClientAuthentication):
    """
    For authlib implementation---this class is a callable that goes on the OIDC server
    in order to authenticate OAuth clients.
    """

    def authenticate(self, request, methods, endpoint):
        """
        Override method from authlib
        """
        client = super(ClientAuthentication, self).authenticate(
            request, methods, endpoint
        )
        # don't allow confidential clients to not use auth
        if client.is_confidential:
            m = list(methods)
            if "none" in m:
                m.remove("none")
            try:
                client = super(ClientAuthentication, self).authenticate(
                    request, m, endpoint
                )
            except AuthlibClientError:
                raise InvalidClientError(
                    "OAuth client failed to authenticate; client ID or secret is"
                    " missing or incorrect"
                )
        return client


class OIDCServer(AuthorizationServer):
    """
    Implement the OIDC provider to attach to the flask app.

    Specific OAuth grants (authorization code, refresh token, etc) are added
    on to a server instance using ``OIDCServer.register_grant(grant)``. For
    usage, see ``fence/oidc/server.py``.
    """

    def init_app(self, app, query_client=None, save_token=None):
        if query_client is not None:
            self.query_client = query_client
        if save_token is not None:
            self.save_token = save_token
        self.app = app
        self.generate_token = generate_token
        if getattr(self, "query_client"):
            self.authenticate_client = ClientAuthentication(query_client)

    def create_token_response(self, request=None):
        """Validate token request and create token response.

        :param request: HTTP request instance
        """
        request = self.create_oauth2_request(request)

        for (grant_cls, extensions) in self._token_grants:
            logger.debug("grant_cls.GRANT_TYPE:" + grant_cls.GRANT_TYPE)
            if request.grant_type:
                logger.debug("request.grant_type:" + request.grant_type)
            else:
                logger.debug("request.grant_type is None")

            logger.debug("request.method:" + request.method)
            logger.debug(
                "grant_cls.TOKEN_ENDPOINT_HTTP_METHODS:"
                + " ".join(grant_cls.TOKEN_ENDPOINT_HTTP_METHODS)
            )
        try:
            grant = self.get_token_grant(request)
        except UnsupportedGrantTypeError as error:
            return self.handle_error_response(request, error)

        try:
            grant.validate_token_request()
            args = grant.create_token_response()
            return self.handle_response(*args)
        except OAuth2Error as error:
            return self.handle_error_response(request, error)

    def create_oauth2_request(self, request):
        for key in flask.request.values.keys():
            logger.debug(key + " : " + flask.request.values[key])
        oauth_request = FlaskOAuth2Request(flask.request)
        return oauth_request
