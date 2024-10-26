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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URLs of atomic services
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://localhost:8889/search_user')
PRODUCT_SERVICE_URL = os.getenv('PRODUCT_SERVICE_URL', 'http://localhost:8888/search_product')
ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://localhost:8890/search_order')

# Store the URLs in a list for easy iteration
urls = [
    {"rel": "users", "href": USER_SERVICE_URL},
    {"rel": "products", "href": PRODUCT_SERVICE_URL},
    {"rel": "orders", "href": ORDER_SERVICE_URL},
]

# Middleware function to log requests and responses
@app.before_request
def log_request():
    """Log incoming request details before processing."""
    logging.info(f"Incoming {request.method} request to {request.path}")
    logging.info(f"Query parameters: {request.args}")

@app.after_request
def log_response(response):
    """Log response details after processing."""
    execution_time = time.time() - g.start_time
    logging.info(f"Response status: {response.status_code} | Time taken: {execution_time:.4f} seconds")
    return response

@app.before_request
def start_timer():
    """Start the timer to measure request execution time."""
    g.start_time = time.time()

# Helper function to call a GET request to an atomic service
def call_get(url):
    try:
        logging.info(f"Calling GET {url}")
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for failed requests
        return response.json()  # Return the JSON response
    except requests.exceptions.HTTPError as err:
        logging.error(f"HTTP error occurred: {err}")
        return None
    except Exception as err:
        logging.error(f"An error occurred: {err}")
        return None

# Helper function to call multiple atomic services and aggregate their responses
def call_get_urls(urls, username=None):
    """Calls multiple atomic services and returns aggregated results."""
    result = defaultdict(list)

    for u in urls:
        r = call_get(u["href"])
        if r is not None:
            t = r.get(u["rel"])
            result[u["rel"]].append(t)
        else:
            logging.warning(f"No response from {u['href']}")

    return result

# Route to handle composite requests
@app.route('/composite/<microservice>', methods=['GET'])
def composite(microservice):
    """Handle composite requests for users, products, or orders."""
    param = request.args.get('param')
    response = None

    try:
        if microservice == 'orders':
            response = requests.get(urls[2]['href'] + (f'?order_id={param}' if param else '')).json()
        elif microservice == 'products':
            response = requests.get(urls[1]['href'] + (f'?product_name={param}' if param else '')).json()
        elif microservice == 'users':
            response = requests.get(urls[0]['href'] + (f'?username={param}' if param else '')).json()
        elif microservice == 'all':
            response = call_get_urls(urls)

        # logging.info(f"Composite response for {microservice}: {response}")
        return jsonify(response)
    except Exception as e:
        logging.error(f"Error handling composite request: {e}")
        return jsonify({"error": "An error occurred while processing the request"}), 500

# Main entry point for the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8891, debug=True)
