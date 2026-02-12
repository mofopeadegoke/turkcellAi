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

@mcp.tool()
async def get_network_status_per_region(region: str) -> dict:
    """
    Get the network status for a specific region.
    """
    url = f"{TURKCELL_API_BASE}/api/v1/troubleshooting/network-status/region/{region}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                url,
                headers=TURKCELL_HEADERS
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            return {"error": f"Network status retrieval failed: {e.response.status_code}"}
        except httpx.RequestError as e:
            return {"error": "Connection to network status service failed"}


@mcp.tool()
async def recommend_package(
    budget_try: Optional[float] = None,
    min_data_gb: Optional[int] = None,
    duration_days: Optional[int] = None,
    package_type: str = "TOURIST"
) -> dict:
    """
    Recommend the best mobile package based on the customer's specific needs.
    Useful when a user asks 'Which plan is best for me?' or mentions a budget.
    
    Args:
        budget_try: Maximum amount the user wants to spend in TRY.
        min_data_gb: Minimum amount of data (in GB) required.
        duration_days: Length of stay in Turkey (e.g., 7, 30).
        package_type: "TOURIST" (default), "PREPAID", or "POSTPAID".
    """
    url = f"{TURKCELL_API_BASE}/api/v1/packages/search/recommend"
    
    # Dynamically build the query parameters
    # This ensures we don't send "None" values to the API
    params = {
        "package_type": package_type
    }
    if budget_try is not None:
        params["budget_try"] = budget_try
    if min_data_gb is not None:
        params["min_data_gb"] = min_data_gb
    if duration_days is not None:
        params["duration_days"] = duration_days

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                url, 
                params=params, 
                headers=TURKCELL_HEADERS
            )
            response.raise_for_status()
            
            # Returns a list of recommended packages with reasoning
            return response.json()
            
        except httpx.HTTPStatusError as e:
            return {"error": f"Recommendation failed: {e.response.status_code}", "details": e.response.text}
        except httpx.RequestError as e:
            return {"error": "Connection failed", "details": str(e)}


@mcp.tool()
async def search_knowledge_base(query: str) -> str:
    """
    Search the Turkcell internal knowledge base for technical guides, 
    troubleshooting steps, and official procedures.
    Use this when the user has a technical issue like 'no internet' or 'APN settings'.
    """
    url = f"{TURKCELL_API_BASE}/api/v1/troubleshooting/knowledge-base/search"
    
    # POST body containing the search query
    payload = {"query": query}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # We use client.post for this endpoint
            response = await client.post(
                url,
                json=payload,
                headers=TURKCELL_HEADERS
            )
            response.raise_for_status()
            
            # Returns the raw search results as a string for the AI to process
            return response.text
            
        except httpx.HTTPStatusError as e:
            return f"Search failed (Error {e.response.status_code}): {e.response.text}"
        except httpx.RequestError as e:
            return f"Knowledge base is currently unreachable: {str(e)}"

if __name__ == "__main__":
    mcp.run()