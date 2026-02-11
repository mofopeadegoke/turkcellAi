from mcp.server.fastmcp import FastMCP
import httpx
from typing import Optional

# Create an MCP server
mcp = FastMCP("Turkcell AI MCP Server")

# Constants for API configuration
TURKCELL_API_BASE = "https://turkcellaiapi.onrender.com"
TURKCELL_HEADERS = {
    "X-API-KEY": "turkcell_key_12345*",
    "Content-Type": "application/json"
}

@mcp.tool()
async def lookup_customer(
    phone: Optional[str] = None, 
    passport: Optional[str] = None
) -> dict:
    """
    Identify a customer using their WhatsApp/phone number or passport number.
    Required for identifying tourists and accessing their specific records.
    """
    if not phone and not passport:
        return {"error": "Provide either a phone number or a passport number."}

    url = f"{TURKCELL_API_BASE}/api/v1/customers/lookup"
    params = {k: v for k, v in {"phone": phone, "passport": passport}.items() if v}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # We pass the TURKCELL_HEADERS here
            response = await client.get(
                url, 
                params=params, 
                headers=TURKCELL_HEADERS
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            return {"error": f"Lookup failed: {e.response.status_code}", "details": e.response.text}
        except httpx.RequestError as e:
            return {"error": "Network error", "details": str(e)}

@mcp.tool()
async def get_balance_summary(balance_id: str) -> dict:
    """
    Get a detailed summary of a specific balance ID.
    Returns remaining data (GB), minutes, and SMS counts.
    """
    # Note: Using the balance_id specifically as required by the teammate's endpoint
    url = f"{TURKCELL_API_BASE}/api/v1/balances/{balance_id}/summary"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                url, 
                headers=TURKCELL_HEADERS
            )
            response.raise_for_status()
            
            # This will return fields like {"data_remaining": 5.2, "unit": "GB", ...}
            return response.json()
            
        except httpx.HTTPStatusError as e:
            return {"error": f"Balance retrieval failed: {e.response.status_code}"}
        except httpx.RequestError as e:
            return {"error": "Connection to balance service failed"}

if __name__ == "__main__":
    mcp.run()