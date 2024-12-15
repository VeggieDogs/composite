from flask import Flask, redirect, request, url_for, session
from authlib.integrations.flask_client import OAuth
from flask import Flask, request, jsonify, g
import asyncio
import aiohttp
from collections import defaultdict
import json
from flask_cors import CORS
import requests
import time  # To measure execution time
import logging  # For logging
import os
from dotenv import load_dotenv
import uuid
import jwt
from datetime import datetime, timedelta

def generate_correlation_id():
    return str(uuid.uuid4())
# Initialize Flask app
app = Flask(__name__)
CORS(app)
# URLs of atomic services

PRODUCT_SERVICE_URL = os.getenv('PRODUCT_SERVICE_URL', f'http://localhost:5001/')
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', f'http://localhost:5002/')
ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', f'http://localhost:5003/')

COMPOSITE_PORT = os.getenv('COMPOSITE_PORT', 5000)

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', '12345678')
JWT_ALGORITHM = 'HS256'

def generate_jwt_token(user_info, grants=None):
    # Default grants if not provided
    if grants is None:
        grants = ['read', 'profile']
    
    # Token payload
    payload = {
        'sub': user_info.get('sub'),  # Subject (unique user identifier)
        'email': user_info.get('email'),
        'name': user_info.get('name'),
        'grants': grants,
        'iat': datetime.utcnow(),  # Issued at
        'exp': datetime.utcnow() + timedelta(hours=2)  # Expiration time
    }
    
    # Generate token
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def validate_jwt_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        return None
    except jwt.InvalidTokenError:
        logger.error("Invalid token")
        return None

app.secret_key = '1234567'  # Replace with your secret key
app.permanent_session_lifetime = timedelta(minutes = 5)

    # Create a logger instance for the app
logger = logging.getLogger(__name__)

# Configure the logger instance
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()  # Send logs to stdout
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Store the URLs in a list for easy iteration
urls = [
    {"ms": "users", "rel": "search_user_by_id", "href": USER_SERVICE_URL},
    {"ms": "products","rel": "search_products_by_user_id", "href": PRODUCT_SERVICE_URL},
    {"ms": "orders","rel": "search_orders_by_id", "href": ORDER_SERVICE_URL},
]

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

@app.before_request
def log_request():
    """Start the timer to measure request execution time and log request details."""
    g.start_time = time.time()
    correlation_id = request.headers.get('X-Correlation-ID', generate_correlation_id())
    g.correlation_id = correlation_id  # Store it in Flask's context (g)
    g.headers = {'X-Correlation-ID': correlation_id}
    logger.info(f"BEFORE_REQUEST -- CID: {correlation_id}")
    logger.info(f"Incoming {request.method} request to {request.path}")
    logger.info(f"Query parameters: {request.args}\n")
# Then in your authorize route, you can use:
@app.route('/authorize')
def authorize():
    google = oauth.create_client('google')
    token = google.authorize_access_token()
    resp = google.get('userinfo')  # This will now work because base URL is set
    user_info = resp.json()

    jwt_token = generate_jwt_token(user_info)
    session['profile'] = user_info
    session['jwt_token'] = jwt_token
    return redirect('http://localhost:3000/search')

@app.after_request
def log_response(response):
    """Log response details after processing."""
    execution_time = time.time() - g.start_time
    logger.info(f"AFTER_REQUEST -- CID:{g.correlation_id} ")
    logger.info(f"Response status: {response.status_code} | Time taken: {execution_time:.4f} seconds\n")
    return response

async def send_post_request(url, orders):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=orders) as response:
                if response.status == 201:
                    result = await response.json()
                    logger.info(f"POST request successful: {result}")
                else:
                    logger.error(f"Failed POST request with status {response.status}")
        except Exception as e:
            logger.error(f"Error occurred: {e}")

# Homepage route
async def process_requests_in_background(data_list):
    if type(data_list) != list:
        data_list = [data_list]
    tasks = [send_post_request(f'{ORDER_SERVICE_URL}post_order', data) for data in data_list]
    await asyncio.gather(*tasks)

def call_get(url):
    """Helper function to call a GET request to an atomic service."""
    try:
        logger.info(f"Calling GET {url}")
        response = requests.get(url, headers=g.headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err}")
        return None
    except Exception as err:
        logger.error(f"An error occurred: {err}")
        return None
# Login route
@app.route('/login')
def login():
    google = oauth.create_client('google')
    redirect_uri = url_for('authorize', _external = True)
    return google.authorize_redirect(redirect_uri)

def call_get_urls(urls, user_id=None):
    """Calls multiple atomic services and returns aggregated results."""
    result = defaultdict(list)
    for u in urls:
        get = u['href']+ u['rel'] + f'?user_id={user_id}'
        r = call_get(get)
        if r is not None:
            t = r.get(u["ms"])
            result[u["ms"]].append(t)
        else:
            logger.warning(f"No response from {u['href']}")
    return result

@app.route('/<microservice>', methods=['GET', 'POST'])
async def composite(microservice):
    """Handle composite requests for users, products, or orders."""
    try:
        if request.method == 'GET':
            response = handle_get_request(microservice)
        elif request.method == 'POST' and microservice == 'post_product':
            response = forward_post_to_products()
        elif request.method == 'POST' and microservice == 'post_order':
            data_list = request.get_json()
            await process_requests_in_background(data_list)
            return jsonify({"message": "Request accepted and processing"}), 202
        else:
            return jsonify({"error": "Invalid request"}), 400
        return response
    except Exception as e:
        logger.error(f"Error handling composite request: {e}")
        return jsonify({"error": "An error occurred while processing the request"}), 500

def handle_get_request(microservice):
    """Handles GET requests."""
    if microservice == 'orders':
        param = request.args.get('order_id')
        return requests.get(urls[2]['href'] + (f'search_order?order_id={param}' if param else '')).json()
    elif microservice == 'products':
        param = request.args.get('product_name')
        url = urls[1]['href'] + (f'search_product?product_name={param}' if param else '')
        response = requests.get(url, headers=g.headers)
        return response.json()
    elif microservice == 'users':
        param = request.args.get('username')
        return requests.get(urls[0]['href'] + (f'search_user?username={param}' if param else '')).json()
    elif microservice == 'all':
        param = request.args.get('user_id')
        return call_get_urls(urls, param)
    return {"error": "Unknown microservice"}

# Dashboard route (fake website after login)
@app.route('/dashboard')
def dashboard():
    profile = session.get('profile')
    profile = session.get('jwt_token')
    if not profile:
        return redirect('/')

    token_payload = validate_jwt_token(jwt_token)

    if not token_payload:
        return redirect('/logout')

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

def forward_post_to_products():
    """Forwards the POST request to the products microservice."""
    data = request.json  # Extract JSON from the incoming request
    product_url = urls[1]['href']  # URL for the products microservice

    logger.info(f"Forwarding POST request to: {product_url}/post_product")

    try:
        # Forward the request to the product microservice
        response = requests.post(f"{product_url}/post_product", json=data)

        # If the response status code is 201, return success
        if response.status_code == 201:
            logger.info("Product posted successfully.")
            return jsonify({"message": "Product posted successfully"}), 201

        else:
            # Safely attempt to parse the JSON response
            try:
                response_data = response.json()
            except ValueError:  # Handle non-JSON responses
                response_data = {"error": response.text}

            logger.error(f"Error from product microservice: {response.status_code} - {response_data}")
            return jsonify(response_data), response.status_code

    except requests.exceptions.RequestException as e:
        # Handle network or other request-related errors
        logger.exception("Exception occurred while forwarding request to product microservice.")
        return jsonify({
            "error": "Failed to connect to product microservice.",
            "details": str(e)
        }), 500

# Logout route
@app.route('/logout')
def logout():
    session.pop('profile', None)
    return redirect('/')

@app.route('/')
def health_check():
    return {"status": "Composite service is up"}, 200

def main():
    app.run(host='0.0.0.0', port=COMPOSITE_PORT, debug=True)

if __name__ == '__main__':
    main()
