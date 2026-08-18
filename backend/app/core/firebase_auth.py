"""
Verifies Firebase ID tokens without the Firebase Admin SDK - deliberately,
since Admin SDK verification needs a GCP service account
(GOOGLE_APPLICATION_CREDENTIALS), which is the same credential the OCR and
face-verification services are still blocked waiting on. Firebase documents
this as a supported alternative ("verify ID tokens using a third-party JWT
library"): the token is a standard RS256 JWT, and its signing keys are
published at a public, unauthenticated JWKS endpoint - so verification here
has no dependency on that credential arriving.

Used only to gate the operations (admin) dashboard. The onboarding flow's
anonymous Firebase sign-ins are unaffected - anonymous tokens have no email
claim, so require_admin rejects them the same way it rejects anyone not on
the ADMIN_EMAILS allowlist.
"""

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.core.config import settings

_JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
_jwk_client = PyJWKClient(_JWKS_URL)


def _decode_firebase_token(token: str) -> dict:
    if not settings.firebase_project_id:
        raise HTTPException(status_code=500, detail="Server auth is not configured (FIREBASE_PROJECT_ID missing)")

    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.firebase_project_id,
            issuer=f"https://securetoken.google.com/{settings.firebase_project_id}",
            # A few seconds of clock skew between this machine and Google's
            # token-issuing servers is normal, not a sign of tampering -
            # without leeway, decode() spuriously rejects fresh tokens
            # whenever local time lags by even a couple of seconds.
            leeway=60,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid auth token: {exc}") from exc

    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid auth token: missing subject")

    return claims


def require_admin(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency for the operations router. Raises 401 for a
    missing/invalid token, 403 if the token's email isn't on the allowlist."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    claims = _decode_firebase_token(token)

    email = (claims.get("email") or "").strip().lower()
    if not email or email not in settings.admin_email_list:
        raise HTTPException(status_code=403, detail="Not authorized for the operations dashboard")

    return claims
