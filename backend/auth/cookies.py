"""Set/clear the auth cookies on a Response.

Three cookies:
  - cb_access  (httpOnly) short-lived access JWT
  - cb_refresh (httpOnly, scoped to the refresh endpoint) long-lived refresh JWT
  - cb_csrf    (readable by JS) double-submit CSRF token, must echo the access
               token's `csrf` claim on unsafe requests

Secure flag defaults off so cookies work over plain http on a LAN/home box; set
COOKIE_SECURE=1 when serving over https.
"""

import os

from fastapi import Response

from .tokens import ACCESS_TTL_SECONDS, REFRESH_TTL_SECONDS

ACCESS_COOKIE = "cb_access"
REFRESH_COOKIE = "cb_refresh"
CSRF_COOKIE = "cb_csrf"
REFRESH_PATH = "/api/auth"


def _secure() -> bool:
    return os.getenv("COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"}


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str, csrf: str) -> None:
    secure = _secure()
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=ACCESS_TTL_SECONDS,
        httponly=True, samesite="lax", secure=secure, path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=REFRESH_TTL_SECONDS,
        httponly=True, samesite="lax", secure=secure, path=REFRESH_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, max_age=REFRESH_TTL_SECONDS,
        httponly=False, samesite="lax", secure=secure, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")
