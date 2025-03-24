from authlib.integrations.flask_client import OAuth
from flask import Blueprint, redirect, url_for, Flask

bp = Blueprint('auth', __name__, url_prefix='/auth')


def make_google_oauth(app: Flask):
    oauth = OAuth(app)

    google = oauth.register(
        name='google',
        client_id='YOUR_GOOGLE_CLIENT_ID',
        client_secret='YOUR_GOOGLE_CLIENT_SECRET',
        access_token_url='https://accounts.google.com/o/oauth2/token',
        access_token_params=None,
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        authorize_params=None,
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        client_kwargs={'scope': 'openid email profile'},
    )
    return google


@bp.route('/login/google')
def login_google():
    google = make_google_oauth(bp.app)  # Получаем google из blueprint
    redirect_uri = url_for('auth.authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri)


@bp.route('/login/google/authorize')
def authorize_google():
    google = make_google_oauth(bp.app)  # Получаем google из blueprint
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.json()

    print(f"User info from Google: {user_info}")

    return redirect(url_for('main.index'))
