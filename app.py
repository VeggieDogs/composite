from flask import Flask, request, jsonify
from collections import defaultdict
import json
from flask_cors import CORS
import requests
import time  # Import time to measure execution duration

app = Flask(__name__)
CORS(app, origins="http://localhost:3000", methods=["GET", "POST"])

urls = [
    {"rel": "users", "href": "http://192.168.1.153:8889/search_user"},
    {"rel": "products", "href": "http://192.168.1.153:8888/search_product"},
    {"rel": "orders", "href": "http://192.168.1.153:8890/search_order"}
]


def call_get(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        return response.json()  # Return the JSON response
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
        return None
    except Exception as err:
        print(f"An error occurred: {err}")
        return None


def call_get_urls(urls):
    # implement searching using username

    result = defaultdict(list)

    for u in urls:
        r = call_get(u["href"])
        print(u['href'])
        print('r', r)
        t = r.get(u["rel"])
        result[u["rel"]].append(t)

    return result

@app.route('/composite/<microservice>', methods=['GET'])
def composite(microservice):
    param = request.args.get('param')
    
    if microservice == 'orders':
        if param:
            response = requests.get(urls[2]['href']+f'?order_id={param}').json()
            print(response)
        else:
            response = requests.get(urls[2]['href']).json()
        return response
    elif microservice == 'products':
        if param:
            response = requests.get(urls[1]['href']+f'?product_name={param}').json()
        else:
            response = requests.get(urls[1]['href']).json()
        return response
    elif microservice == 'users':
        if param:
            response = requests.get(urls[0]['href']+f'?username={param}').json()
        else:
            response = requests.get(urls[0]['href']).json()
        return response
    else:
        full_result = call_get_urls(
            urls
        )
        return jsonify(full_result)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8891, debug=True)
