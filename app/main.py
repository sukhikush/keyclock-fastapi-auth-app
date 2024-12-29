from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.responses import JSONResponse
from pydantic import BaseModel
from types import SimpleNamespace
from app.middleware import RBACMiddleware
from app.decodeJWT import decodeJWT
from app.config import KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import os
import requests
import json


class UserData(BaseModel):
    roles: object
    preferred_username: str

app = FastAPI()


# Add the RBAC middleware
app.add_middleware(RBACMiddleware)

# Set up templates for the frontend
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)




@app.get("/", response_class=HTMLResponse)
def get_root():
    """
    Root endpoint that returns a SPA which manages login page and user details page.
    """
    # Simple UI for Login and User Details
    return templates.TemplateResponse(
        "index.html",
        {
            "request": {}, 
            "config": {
                "KEYCLOAK_URL" : KEYCLOAK_URL, 
                "KEYCLOAK_REALM" : KEYCLOAK_REALM, 
                "KEYCLOAK_CLIENT_ID" : KEYCLOAK_CLIENT_ID,
            }
        },
    )



@app.get('/logout',response_class=HTMLResponse)
def get_logout(
    request: Request, response: Response
):
    """
    Logout removes cookies and redirects to keycloak logout page.
    Deletes cookies for authentication and provides a logout template with Keycloak configuration.
    """

    # deleting cookies
    response.set_cookie(key="token", value="", httponly=True,secure=True,max_age=0)
    response.set_cookie(key="usrData", value="", httponly=False,max_age=0)

    # Logout template to redirect keycloak for logout
    return templates.TemplateResponse(
        "logout.html",
        {
            "request": request, 
            "config": {
                "KEYCLOAK_URL" : KEYCLOAK_URL, 
                "KEYCLOAK_REALM" : KEYCLOAK_REALM, 
                "KEYCLOAK_CLIENT_ID" : KEYCLOAK_CLIENT_ID,
            }
        },
        headers=response.headers 
    ) 


@app.get("/callback")
def get_callback(
    code: str
):
    """
    callback route to manage authentication. This is called via keycloak.
    """
    try:

        # Fetching Tokens from Keycloak

        url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
        headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
        body = f"grant_type=authorization_code&client_id={KEYCLOAK_CLIENT_ID}&code={code}&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback"

        fetched_token = requests.post(url, headers=headers, data=body)

        # Check the response status code
        if fetched_token.status_code == 200:
            token_json = fetched_token.json()

            access_token = token_json.get("access_token")
            jwtPayload = decodeJWT(access_token)


            # Combine roles and preferred_username into a single value to store in the cookiee

            roles = jwtPayload.get("realm_access", {}).get("roles", [])
            preferred_username = jwtPayload.get("preferred_username", '')
            cookie_value = UserData(roles=roles,preferred_username=preferred_username).json()

            # Redirecting back to Home page
            redirect = RedirectResponse(url=f"/", status_code=303)

            # Set session cookies
            redirect.set_cookie(key="token", value=access_token, httponly=True,secure=True,)
            redirect.set_cookie(key="usrData", value=cookie_value, httponly=False)
            
            return redirect
        else:
            return JSONResponse(status_code=500, content={"error": "Error while generating token"})

    except Exception as e:  # Catch any other unexpected exceptions.
        print(f"Unexpected error during token verification: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
    

@app.get("/api/v1/secure-endpoint")
def secure_endpoint(request: Request):
    """
    secure_endpoint only acessible by Admin
    """
    # Simple Secured route only acessible to admin

    roles = getattr(request.state, "roles", None)
    
    if "admin" not in roles:
        raise HTTPException(
            status_code=403, detail="Access denied: Admin role required"
        )
    
    return {"message": "Access Granted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)