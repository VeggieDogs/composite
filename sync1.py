import json
from collections import defaultdict

import requests
import time  # Import time to measure execution duration

urls = [
    {"rel": "users", "href": "http://192.168.1.153:8889/search_user?username=henry"},
    {"rel": "products", "href": "http://192.168.1.153:8888/search_product?product_name=apple"},
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

    result = defaultdict(list)

    for u in urls:
        r = call_get(u["href"])
            # print(element)
            # print(u['rel'])
        t = r.get(u["rel"])
        result[u["rel"]].append(t)

    return result

# Example usage:
def main():

    # Start measuring time
    start_time = time.time()

    # Call API three times synchronously
    full_result = call_get_urls(
        urls
    )

    # Calculate total execution time
    total_time = time.time() - start_time

    # Print all the responses
    print("The full response = \n",
          json.dumps(full_result, indent=2))

    # Print total execution time
    print(f"Total execution time: {total_time:.2f} seconds")


# To run the program
if __name__ == "__main__":
    main()
