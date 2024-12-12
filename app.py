from flask import Flask, redirect, request, url_for, session
from authlib.integrations.flask_client import OAuth
import os
from datetime import timedelta

# Initialize Flask app
app = Flask(__name__)
app.secret_key = '1234567'  # Replace with your secret key
app.permanent_session_lifetime = timedelta(minutes = 5)

# OAuth 2 client setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id='199330867043-0mhq3ask42fedk3istp4u5vvajb4o4k5.apps.googleusercontent.com',
    client_secret='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',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    api_base_url='https://www.googleapis.com/oauth2/v3/',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Then in your authorize route, you can use:
@app.route('/authorize')
def authorize():
    google = oauth.create_client('google')
    token = google.authorize_access_token()
    resp = google.get('userinfo')  # This will now work because base URL is set
    user_info = resp.json()
    session['profile'] = user_info
    return redirect('/dashboard')


# Homepage route
@app.route('/')
def home():
    return '''
        <html>
            <head>
                <title>OAuth2 Google Login</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background-color: #f0f2f5;
                    }
                    .login-container {
                        text-align: center;
                        padding: 20px;
                        background-color: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    }
                    .login-button {
                        background-color: #4285f4;
                        color: white;
                        padding: 10px 20px;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 16px;
                        text-decoration: none;
                    }
                    .login-button:hover {
                        background-color: #357abd;
                    }
                </style>
            </head>
            <body>
                <div class="login-container">
                    <h1>Welcome</h1>
                    <a href="/login" class="login-button">Login with Google</a>
                </div>
            </body>
        </html>
    '''


# Login route
@app.route('/login')
def login():
    google = oauth.create_client('google')
    redirect_uri = url_for('authorize', _external = True)
    return google.authorize_redirect(redirect_uri)



# Dashboard route (fake website after login)
@app.route('/dashboard')
def dashboard():
    profile = session.get('profile')
    if not profile:
        return redirect('/')

    return f'''
        <html>
            <head>
                <title>Dashboard</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 0;
                        padding: 20px;
                        background-color: #f0f2f5;
                    }}
                    .dashboard-container {{
                        max-width: 800px;
                        margin: 0 auto;
                        background-color: white;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    }}
                    .welcome-message {{
                        color: #1a73e8;
                    }}
                    .user-info {{
                        margin-top: 20px;
                        padding: 15px;
                        background-color: #f8f9fa;
                        border-radius: 4px;
                    }}
                    .logout-button {{
                        background-color: #dc3545;
                        color: white;
                        padding: 10px 20px;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        text-decoration: none;
                        display: inline-block;
                        margin-top: 20px;
                    }}
                    .logout-button:hover {{
                        background-color: #c82333;
                    }}
                </style>
            </head>
            <body>
                <div class="dashboard-container">
                    <h1 class="welcome-message">Welcome to Your Dashboard</h1>
                    <div class="user-info">
                        <h2>User Profile</h2>
                        <p><strong>Name:</strong> {profile.get('name', 'N/A')}</p>
                        <p><strong>Email:</strong> {profile.get('email', 'N/A')}</p>
                    </div>
                    <a href="/logout" class="logout-button">Logout</a>
                </div>
            </body>
        </html>
    '''


# Logout route
@app.route('/logout')
def logout():
    session.pop('profile', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug = True)
