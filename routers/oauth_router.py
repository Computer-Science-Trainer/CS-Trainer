
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import RedirectResponse
import os
from authlib.integrations.starlette_client import OAuth
from services.user_service import get_user_by_email, save_user
from security import create_access_token

router = APIRouter()

oauth = OAuth()
oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# Frontend URL to redirect to after OAuth
auth_frontend = os.getenv("FRONTEND_URL", "http://localhost:3000")


@router.get("/{provider}/login")
async def oauth_login(provider: str, request: Request):
    if provider not in ("github", "google"):
        raise HTTPException(status_code=404, detail="Unknown provider")
    redirect_uri = request.url_for("oauth_callback", provider=provider)
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def oauth_callback(provider: str, request: Request):
    if provider not in ("github", "google"):
        raise HTTPException(status_code=404, detail="Unknown provider")

    if "error" in request.query_params:
        error_description = request.query_params.get(
            "error_description", "Access denied")
        return RedirectResponse(
            f"{auth_frontend}/callback?error={error_description}")

    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)
    if provider == "github":
        resp = await client.get("user", token=token)
        profile = resp.json()
        email = profile.get("email")
        if not email:
            emails = await client.get("user/emails", token=token)
            primary = next(
                (e for e in emails.json() if e.get("primary")),
                emails.json()[0])
            email = primary.get("email")
        username = profile.get("login")
    else:
        try:
            userinfo = await client.parse_id_token(request, token)
        except Exception:
            userinfo_endpoint = client.server_metadata.get("userinfo_endpoint")
            resp = await client.get(userinfo_endpoint, token=token)
            userinfo = resp.json()
        email = userinfo.get("email")
        username = userinfo.get("name") or email.split("@")[0]
    user = get_user_by_email(email)
    if not user:
        save_user(email, "", username, True, "")
        user = get_user_by_email(email)
    access_token = create_access_token({"sub": email, "user_id": user["id"]})
    redirect_url = f"{auth_frontend}/callback?token={access_token}"
    return RedirectResponse(redirect_url)
