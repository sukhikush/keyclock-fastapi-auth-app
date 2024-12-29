from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.decodeJWT import decodeJWT
from app.config import KEYCLOAK_CLIENT_ID, KEYCLOAK_REALM, KEYCLOAK_URL
import traceback


class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        excluded_routes = ["/","/callback","/logout"]

        if request.url.path in excluded_routes:
            return await call_next(request)

        try:
            token = request.cookies.get("token")

            jwtPayload = decodeJWT(token)

            if "realm_access" in str(jwtPayload):
                roles = jwtPayload.get("realm_access", {}).get("roles", [])
            else:
                roles = []

            request.state.roles = roles
        
        except Exception as e:  # Catch any other unexpected exceptions.
            print(f"Unexpected error during token fetch: {e}")
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
        
        return await call_next(request)
