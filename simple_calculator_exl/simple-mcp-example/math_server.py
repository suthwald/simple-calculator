from fastapi import FastAPI, Request
from fastmcp import FastMCP
import uvicorn
import json

# Initialize FastMCP
mcp = FastMCP(name="math-server", version="1.0.0")


# --- Math Tools ---
@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise ValueError("Inputs must be numeric")
    return float(a + b)


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise ValueError("Inputs must be numeric")
    return float(a * b)


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract two numbers."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise ValueError("Inputs must be numeric")
    return float(a - b)


# --- FastAPI Setup ---
app = FastAPI(title="Math JSON-RPC Server", version="1.0.0")


@app.post("/mcp")
async def handle_mcp(request: Request):
    """Handle JSON-RPC 2.0 requests manually."""
    json_data = None
    try:
        json_data = await request.json()

        # Basic validation
        if json_data.get("jsonrpc") != "2.0" or "method" not in json_data:
            return {
                "jsonrpc": "2.0",
                "id": json_data.get("id", None),
                "error": {"code": -32600, "message": "Invalid JSON-RPC request"},
            }

        method = json_data["method"]
        params = json_data.get("params", {})

        # Manual dispatch using underlying function references
        if method == "add":
            result = add.fn(**params)
        elif method == "multiply":
            result = multiply.fn(**params)
        elif method == "subtract":
            result = subtract.fn(**params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": json_data.get("id"),
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
            }

        # Success response
        return {"jsonrpc": "2.0", "id": json_data.get("id"), "result": result}

    except json.JSONDecodeError:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error: invalid JSON"},
        }

    except ValueError as e:
        return {
            "jsonrpc": "2.0",
            "id": json_data.get("id") if isinstance(json_data, dict) else None,
            "error": {"code": -32602, "message": f"Invalid params: {e}"},
        }

    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": json_data.get("id") if isinstance(json_data, dict) else None,
            "error": {"code": -32000, "message": f"Server error: {e}"},
        }


@app.get("/health")
async def health_check():
    """Simple health check."""
    return {"status": "ok", "version": mcp.version}


@app.get("/")
async def root():
    """Root endpoint for browser testing."""
    return {
        "message": "Welcome to Math MCP Server",
        "tools": ["add", "multiply", "subtract"],
    }


if __name__ == "__main__":
    uvicorn.run("math_server:app", host="localhost", port=8000, reload=True)
