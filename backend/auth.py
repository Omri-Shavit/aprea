"""Authentication: verify Google Sign-In ID tokens and enforce @aprea.com access.

This is the REAL access control. The frontend login screen only decides what UI
to show; it can be bypassed by calling the API directly. So every protected
route depends on `require_user`, which:

  1. reads the `Authorization: Bearer <id_token>` header,
  2. cryptographically verifies the Google-issued ID token (signature, expiry,
     and that its audience == our OAuth client id) using Google's public keys,
  3. requires a verified email in the allowed Workspace domain (aprea.com).

Configuration (environment variables):
  REQUIRE_AUTH          "true" to enforce (default "false" so local dev is open)
  GOOGLE_CLIENT_ID      the OAuth 2.0 Web client id (same one the frontend uses)
  ALLOWED_EMAIL_DOMAIN  domain to allow (default "aprea.com")
"""

import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "aprea.com")

_bearer = HTTPBearer(auto_error=False)
_google_request = google_requests.Request()


def require_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    """FastAPI dependency. Returns the verified user claims, or raises 401/403."""
    if not REQUIRE_AUTH:
        return None  # local dev: auth disabled

    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Server auth is misconfigured: GOOGLE_CLIENT_ID is not set.",
        )

    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")

    try:
        claims = id_token.verify_oauth2_token(
            creds.credentials, _google_request, GOOGLE_CLIENT_ID
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}")

    if not claims.get("email_verified"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email is not verified.")

    email = (claims.get("email") or "").lower()
    hosted_domain = claims.get("hd")
    if hosted_domain != ALLOWED_EMAIL_DOMAIN and not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Access is restricted to @{ALLOWED_EMAIL_DOMAIN} accounts.",
        )

    return {"email": email, "name": claims.get("name"), "sub": claims.get("sub")}
