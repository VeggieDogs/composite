import json

import aiohttp
import asyncio
import time  # Import time to measure execution duration

urls = [
    {"rel": "users", "href": "http://192.168.1.153:8889/search_user?username=henry"},
    {"rel": "products", "href": "http://192.168.1.153:8888/search_product?product_name=apple"},
    {"rel": "orders", "href": "http://192.168.1.153:8890/search_order"}
]


async def get_url(url):

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()  # Check if the request was successful
                result = await response.json()  # Return the JSON respons
                return result
        except aiohttp.ClientResponseError as err:
            print(f"HTTP error occurred: {err}")
            return None
        except Exception as err:
            print(f"An error occurred: {err}")
            return None


async def get_all_urls(urls):
    """Encapsulates the API call logic to call the API three times asynchronously."""
    tasks = []
    properties = []
    for u in urls:
        properties.append(u["rel"])
        tasks.append(get_url(u["href"]))
    all_results = await asyncio.gather(*tasks)  # Run tasks concurrently and gather results
    full_result = {}

    for i in range(0, len(properties)):
        p = properties[i]
        v = all_results[i]
        final_v = v.get(p, v)
        full_result[p] = final_v

    return full_result


# Example usage:
async def main():
    uni = 'dff9'

    # Start measuring time
    start_time = time.time()

    # Call API three times asynchronously
    result = await get_all_urls(urls)

    # Calculate total execution time
    total_time = time.time() - start_time

    # Print all the responses
    print("Full result = ", json.dumps(result, indent=2))

    # Print total execution time
    print(f"Total execution time: {total_time:.2f} seconds")


# To run the async function
if __name__ == "__main__":
    asyncio.run(main())
