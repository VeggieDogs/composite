from flask import Flask, request, jsonify, g
from collections import defaultdict
import json
from flask_cors import CORS
import requests
import time  # To measure execution time
import logging  # For logging
import os
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins="http://localhost:3000", methods=["GET", "POST"])

# Create a logger instance for the app
logger = logging.getLogger(__name__)

# Configure the logger instance
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()  # Send logs to stdout
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# URLs of atomic services
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://localhost:8889/')
PRODUCT_SERVICE_URL = os.getenv('PRODUCT_SERVICE_URL', 'http://localhost:8888/')
ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://localhost:8890/')

# Store the URLs in a list for easy iteration
urls = [
    {"rel": "users", "href": USER_SERVICE_URL},
    {"rel": "products", "href": PRODUCT_SERVICE_URL},
    {"rel": "orders", "href": ORDER_SERVICE_URL},
]

@app.before_request
def log_request():
    """Start the timer to measure request execution time and log request details."""
    g.start_time = time.time()
    logger.info(f"Incoming {request.method} request to {request.path}")
    logger.info(f"Query parameters: {request.args}")

@app.after_request
def log_response(response):
    """Log response details after processing."""
    execution_time = time.time() - g.start_time
    logger.info(f"Response status: {response.status_code} | Time taken: {execution_time:.4f} seconds")
    return response

def call_get(url):
    """Helper function to call a GET request to an atomic service."""
    try:
        logger.info(f"Calling GET {url}")
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err}")
        return None
    except Exception as err:
        logger.error(f"An error occurred: {err}")
        return None

def call_get_urls(urls, username=None):
    """Calls multiple atomic services and returns aggregated results."""
    result = defaultdict(list)
    for u in urls:
        r = call_get(u["href"])
        if r is not None:
            t = r.get(u["rel"])
            result[u["rel"]].append(t)
        else:
            logger.warning(f"No response from {u['href']}")
    return result

@app.route('/composite/<microservice>', methods=['GET', 'POST'])
def composite(microservice):
    """Handle composite requests for users, products, or orders."""
    try:
        if request.method == 'GET':
            response = handle_get_request(microservice)
        elif request.method == 'POST' and microservice == 'post_product':
            response = forward_post_to_products()
        else:
            return jsonify({"error": "Invalid request"}), 400
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling composite request: {e}")
        return jsonify({"error": "An error occurred while processing the request"}), 500

def handle_get_request(microservice):
    """Handles GET requests."""
    if microservice == 'orders':
        param = request.args.get('order_id')
        return requests.get(urls[2]['href'] + (f'search_order?order_id={param}' if param else '')).json()
    elif microservice == 'products':
        param = request.args.get('product_id')
        return requests.get(urls[1]['href'] + (f'search_product?product_name={param}' if param else '')).json()
    elif microservice == 'users':
        param = request.args.get('user_id')
        return requests.get(urls[0]['href'] + (f'search_user?username={param}' if param else '')).json()
    elif microservice == 'all':
        return call_get_urls(urls)
    return {"error": "Unknown microservice"}

def forward_post_to_products():
    """Forwards the POST request to the products microservice."""
    data = request.json
    product_url = urls[1]['href']  # URL for the products microservice
    logger.info(f"Forwarding POST request to: {product_url}/post_product")
    response = requests.post(f"{product_url}/post_product", json=data)
    if response.status_code == 201:
        return {"message": "Product posted successfully"}
    else:
        return response.json()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8891, debug=True)
