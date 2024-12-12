import os
import time
import json
import logging
import asyncio
import aiohttp
import requests
import jwt
import datetime
from collections import defaultdict
from flask import Flask, request, jsonify, g, redirect, url_for, session
from flask_cors import CORS
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

load_dotenv()  # Loads .env file if present

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
CORS(app, origins="http://localhost:3000", methods=["GET", "POST"])

# Create a logger instance for the app
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()  # Send logs to stdout
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# OAuth Setup for Google
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params={
        'prompt': 'consent',
        'access_type': 'offline',
        'scope': 'openid email profile'
    },
    client_kwargs={'scope': 'openid email profile'}
)

JWT_SECRET = os.getenv('JWT_SECRET', 'change_this_secret')
JWT_ALGORITHM = 'HS256'
JWT_EXP_DELTA_SECONDS = 3600  # 1 hour token expiry

USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://localhost:8889/')
PRODUCT_SERVICE_URL = os.getenv('PRODUCT_SERVICE_URL', 'http://localhost:8888/')
ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://localhost:8890/')

# Store the URLs in a list for easy iteration
urls = [
    {"ms": "users", "rel": "search_user_by_id", "href": USER_SERVICE_URL},
    {"ms": "products","rel": "search_products_by_user_id", "href": PRODUCT_SERVICE_URL},
    {"ms": "orders","rel": "search_orders_by_id", "href": ORDER_SERVICE_URL},
]

def generate_jwt_token(user_info, grants):
    payload = {
        "sub": user_info["email"],
        "name": user_info.get("name"),
        "grants": grants,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    # Here you could store user info in your user service if needed.
    # For now, we just issue a token with basic grants
    jwt_token = generate_jwt_token(user_info=user_info, grants=["basic_user"])
    # Return JWT token to the client (could be a cookie or JSON)
    return jsonify({"jwt": jwt_token})

@app.before_request
def before_request_auth_and_logging():
    """Measure execution time and log request details. Also authenticate JWT."""
    g.start_time = time.time()
    logger.info(f"BEFORE_REQUEST")
    logger.info(f"Incoming {request.method} request to {request.path}")
    logger.info(f"Query parameters: {request.args}\n")

    # Public endpoints that don't need authentication
    public_paths = ['/login', '/authorize', '/openapi.yaml', '/docs', '/swagger.json']

    # Skip auth if endpoint is public
    if request.path in public_paths or request.method == 'OPTIONS':
        return

    # Check for JWT
    auth_header = request.headers.get('Authorization', None)
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid token"}), 401

    token = auth_header.split(" ")[1]
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        g.current_user = decoded
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

@app.after_request
def after_request_logging(response):
    """Log response details after processing."""
    execution_time = time.time() - g.start_time
    logger.info(f"AFTER_REQUEST")
    logger.info(f"Response status: {response.status_code} | Time taken: {execution_time:.4f} seconds\n")
    return response

async def send_post_request(url, orders):
    async with aiohttp.ClientSession() as session:
        try:
            # Forward the JWT token downstream
            headers = {}
            if hasattr(g, 'current_user'):
                token = request.headers.get('Authorization')
                if token:
                    headers['Authorization'] = token

            async with session.post(url, json=orders, headers=headers) as response:
                if response.status == 201:
                    result = await response.json()
                    logger.info(f"POST request successful: {result}")
                else:
                    logger.error(f"Failed POST request with status {response.status}")
        except Exception as e:
            logger.error(f"Error occurred: {e}")

async def process_requests_in_backround(data_list):
    if type(data_list) != list:
        data_list = [data_list]
    tasks = [send_post_request(f'{ORDER_SERVICE_URL}post_order', data) for data in data_list]
    await asyncio.gather(*tasks)

def call_get(url):
    """Helper function to call a GET request to an atomic service."""
    try:
        logger.info(f"Calling GET {url}")
        # Forward the JWT token downstream
        headers = {}
        if hasattr(g, 'current_user'):
            token = request.headers.get('Authorization')
            if token:
                headers['Authorization'] = token

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err}")
        return None
    except Exception as err:
        logger.error(f"An error occurred: {err}")
        return None

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

@app.route('/composite/<microservice>', methods=['GET', 'POST'])
async def composite(microservice):
    """Handle composite requests for users, products, or orders."""
    # Example of checking grants:
    # if 'admin' not in g.current_user.get('grants', []):
    #     return jsonify({"error": "Not authorized"}), 403

    try:
        if request.method == 'GET':
            response = handle_get_request(microservice)
        elif request.method == 'POST' and microservice == 'post_product':
            response = forward_post_to_products()
        elif request.method == 'POST' and microservice == 'post_order':
            data_list = request.get_json()
            await process_requests_in_backround(data_list)
            return jsonify({"message": "Request accepted and processing"}), 202
        else:
            return jsonify({"error": "Invalid request"}), 400
        return response
    except Exception as e:
        logger.error(f"Error handling composite request: {e}")
        return jsonify({"error": "An error occurred while processing the request"}), 500

def handle_get_request(microservice):
    """Handles GET requests."""
    param = None
    if microservice == 'orders':
        param = request.args.get('order_id')
        url = urls[2]['href'] + (f'search_order?order_id={param}' if param else '')
        return requests.get(url, headers=_forward_auth_header()).json()
    elif microservice == 'products':
        param = request.args.get('product_name')
        url = urls[1]['href'] + (f'search_product?product_name={param}' if param else '')
        return requests.get(url, headers=_forward_auth_header()).json()
    elif microservice == 'users':
        param = request.args.get('user_id')
        url = urls[0]['href'] + (f'search_user?username={param}' if param else '')
        return requests.get(url, headers=_forward_auth_header()).json()
    elif microservice == 'all':
        param = request.args.get('user_id')
        return call_get_urls(urls, param)
    return {"error": "Unknown microservice"}

def forward_post_to_products():
    """Forwards the POST request to the products microservice."""
    data = request.json
    product_url = urls[1]['href'] + "/post_product"
    logger.info(f"Forwarding POST request to: {product_url}")

    try:
        response = requests.post(product_url, json=data, headers=_forward_auth_header())
        if response.status_code == 201:
            logger.info("Product posted successfully.")
            return jsonify({"message": "Product posted successfully"}), 201
        else:
            # Safely parse the JSON response
            try:
                response_data = response.json()
            except ValueError:
                response_data = {"error": response.text}

            logger.error(f"Error from product microservice: {response.status_code} - {response_data}")
            return jsonify(response_data), response.status_code
    except requests.exceptions.RequestException as e:
        logger.exception("Exception occurred while forwarding request to product microservice.")
        return jsonify({"error": "Failed to connect to product microservice.", "details": str(e)}), 500

def _forward_auth_header():
    """Helper to forward Authorization header downstream."""
    headers = {}
    token = request.headers.get('Authorization')
    if token:
        headers['Authorization'] = token
    return headers

if __name__ == '__main__':
    # Make sure you run behind HTTPS for real Google OAuth flow in production.
    app.run(host='0.0.0.0', port=8891, debug=True)
