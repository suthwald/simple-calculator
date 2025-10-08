import requests
import uuid
import json
import sys

SERVER_URL = "http://localhost:8000/mcp"


def call_mcp_method(method: str, params: dict):
    """Send a JSON-RPC 2.0 request to the server and return the result or error."""
    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
    }

    try:
        resp = requests.post(SERVER_URL, json=body, timeout=5)
        resp.raise_for_status()
        response = resp.json()
        return response
    except requests.exceptions.RequestException as e:
        return {"error": {"message": f"Request failed: {str(e)}"}}
    except json.JSONDecodeError:
        return {"error": {"message": "Invalid JSON response from server"}}


def print_response(response):
    """Pretty print JSON-RPC response."""
    if "error" in response:
        print("\n❌ Error:")
        print(json.dumps(response["error"], indent=2))
    else:
        print("\n✅ Result:")
        print(json.dumps(response, indent=2))


def interactive_mode():
    """Interactive CLI to call the math server."""
    print("🧮 JSON-RPC Math Client (connected to http://localhost:8000/mcp)")
    print("Available methods: add, multiply, subtract")
    print("Type 'exit' to quit.\n")

    while True:
        method = input("Method> ").strip()
        if method.lower() in {"exit", "quit"}:
            print("Goodbye 👋")
            break
        if method not in {"add", "multiply", "subtract"}:
            print("Invalid method. Try again.")
            continue
        try:
            a = float(input("a = "))
            b = float(input("b = "))
        except ValueError:
            print("⚠️ Please enter valid numbers.\n")
            continue

        response = call_mcp_method(method, {"a": a, "b": b})
        print_response(response)
        print()


if __name__ == "__main__":
    # --- CLI argument mode ---
    if len(sys.argv) > 2:
        method = sys.argv[1]
        try:
            params = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            print(
                'Invalid JSON for params. Example: python math_client.py add \'{"a":1,"b":2}\''
            )
            sys.exit(1)
        print_response(call_mcp_method(method, params))
    else:
        # --- Interactive mode ---
        interactive_mode()
