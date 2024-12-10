from flask import Flask, request, jsonify, g 
import click
import sys
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

# URLs of atomic services
@click.command()
@click.option('--composite_port', default = 8888)
@click.option('--user_port', default = 8888)
@click.option('--product_port', default = 8888)
@click.option('--order_port', default = 8888)

def main(composite_port, user_port, product_port, order_port):

    USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', f'http://localhost:{user_port}/')
    PRODUCT_SERVICE_URL = os.getenv('PRODUCT_SERVICE_URL', f'http://localhost:{product_port}/')
    ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', f'http://localhost:{order_port}/')

    # Initialize Flask app
    app = Flask(__name__)
    CORS(app, origins="http://localhost:3001", methods=["GET", "POST"])

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

    @app.before_request
    def log_request():
        """Start the timer to measure request execution time and log request details."""
        g.start_time = time.time()
        logger.info(f"BEFORE_REQUEST")
        logger.info(f"Incoming {request.method} request to {request.path}")
        logger.info(f"Query parameters: {request.args}\n")

    @app.after_request
    def log_response(response):
        """Log response details after processing."""
        execution_time = time.time() - g.start_time
        logger.info(f"AFTER_REQUEST")
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

    async def process_requests_in_backround(data_list):
        if type(data_list) != list:
            data_list = [data_list]
        tasks = [send_post_request(f'{ORDER_SERVICE_URL}post_order', data) for data in data_list]
        await asyncio.gather(*tasks)

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
        if microservice == 'orders':
            param = request.args.get('order_id')
            return requests.get(urls[2]['href'] + (f'search_order?order_id={param}' if param else '')).json()
        elif microservice == 'products':
            param = request.args.get('product_name')
            return requests.get(urls[1]['href'] + (f'search_product?product_name={param}' if param else '')).json()
        elif microservice == 'users':
            param = request.args.get('username')
            return requests.get(urls[0]['href'] + (f'search_user?username={param}' if param else '')).json()
        elif microservice == 'all':
            param = request.args.get('user_id')
            return call_get_urls(urls, param)
        return {"error": "Unknown microservice"}

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
    
    app.run(host='0.0.0.0', port=composite_port, debug=True)

if __name__ == '__main__':
    main()
