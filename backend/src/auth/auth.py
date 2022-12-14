from dotenv import load_dotenv
import os
import json
from flask import request, _request_ctx_stack
from functools import wraps
from jose import jwt
from urllib.request import urlopen

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
ALGORITHMS = [os.getenv("ALGORITHM")]
API_AUDIENCE = os.getenv("API_AUDIENCE")

# AuthError Exception


class AuthError(Exception):
    '''
AuthError Exception
A standardized way to communicate auth failure modes
'''

    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


# Auth Header

'''
get_token_auth_header() method
    - attempts to get the header from the request
    - raises an AuthError if no header is present
    - attempts to split bearer and the token
    - raises an AuthError if the header is malformed
    returns the token part of the header
'''


def get_token_auth_header():
    """ Obtains the access token from the Authorization header """

    auth_header = request.headers.get("Authorization", None)

    if not auth_header:
        raise AuthError({
            "code": "authorization_header_missing",
            "description": "Authorization header missing."
        }, 401)

    parts = auth_header.split()

    if parts[0].lower() != "bearer":
        raise AuthError({
            "code": "invalid_header",
            "description": "Authorization header must start with 'Bearer'"
        }, 401)

    if len(parts) == 1:
        raise AuthError({
            "code": "invalid_header",
            "description": "Token not found."
        }, 401)

    if len(parts) > 2:
        raise AuthError({
            "code": "invalid_header",
            "description": "Authorization header must be 'Bearer token'"
        }, 401)

    token = parts[1]
    return token


'''
check_permissions(permission, payload) method
    @INPUTS
        permission: string permission (i.e. 'post:drink')
        payload: decoded jwt payload
    - raises an AuthError if permissions are not included in the payload
        !!NOTE make sure to enable RBAC in auth0 and also add permissions
    - raises an AuthError if the requested permission string is not found payload permissions array
    - Returns True if permission is found
'''


def check_permissions(permission, payload):
    """ Validate claims and check the requested permission """

    if "permissions" not in payload:
        raise AuthError({
            "code": "invalid_claims",
            "description": "Permissions not included in JWT."
        }, 400)

    if permission not in payload["permissions"]:
        raise AuthError({
            "code": "unauthorized",
            "description": "Permission not found."
        }, 403)

    return True


'''
verify_decode_jwt(token) method
    @INPUTS
        token: a json web token (string)
    - ensures token is an Auth0 token with key id (kid)
    - verifies the token using Auth0 /.well-known/jwks.json
    - decodes the payload from the token
    - validates the claims
    return the decoded payload
    !!NOTE urlopen has a common certificate error described here: https://stackoverflow.com/questions/50236117/scraping-ssl-certificate-verify-failed-error-for-http-en-wikipedia-org
'''


def verify_and_decode_jwt(token):
    """ Verify if token is valid and return payload """

    json_url = urlopen(f'https://{AUTH0_DOMAIN}/.well-known/jwks.json')
    jwks = json.loads(json_url.read())
    unverified_header = jwt.get_unverified_header(token)
    rsa_key = {}

    if 'kid' not in unverified_header:
        raise AuthError({
            "code": "invalid_header",
            "description": "Authorization malformed."
        }, 401)

    for key in jwks["keys"]:
        if unverified_header["kid"] == key["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }

    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=API_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/"
            )
            return payload

        except jwt.ExpiredSignatureError:
            raise AuthError({
                "code": "token_expired",
                "description": "Token expired."
            }, 401)

        except jwt.JWTClaimsError:
            raise AuthError({
                "code": "invalid_claims",
                "description": "Invalid claims. Please check the audience and issuer."
            }, 401)

        except Exception:
            raise AuthError({
                "code": "invalid_token",
                "description": "Unable to parse token."
            }, 400)
    raise AuthError({
        "code": "invalid_header",
        "description": "Unable to find the appropriate key."
    }, 400)


'''
@requires_auth(permission) decorator method
    @INPUTS
        permission: string permission (i.e. 'post:drink')
    return the decorator which passes the decoded payload to the decorated method
'''


def requires_auth(permission=""):
    def requires_auth_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = get_token_auth_header()
            payload = verify_and_decode_jwt(token)
            check_permissions(permission, payload)

            return f(payload, *args, **kwargs)
        return wrapper
    return requires_auth_decorator
