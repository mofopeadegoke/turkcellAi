from mcp.server.fastmcp import FastMCP
import httpx
from typing import Optional
from typing import List, Dict, Any

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

#   Not the most optimal tool yet
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


@mcp.tool()
async def get_active_subscriptions(customer_id: str) -> list[dict[str, Any]]:
    """
    Fetches the list of active subscriptions for a customer.
    
    The API returns a wrapper object:
    { "success": true, "subscriptions": [...] }
    
    This tool extracts JUST the list inside 'subscriptions'.
    """
    # Construct the full URL using the new base variable
    endpoint = f"{TURKCELL_API_BASE}/api/v1/customers/{customer_id}/subscriptions"
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Make the request
            response = await client.get(endpoint, timeout=10.0)
            response.raise_for_status()
            
            # 2. Parse JSON
            data = response.json()
            
            # 3. Extract the list from the "subscriptions" key
            if "subscriptions" in data and isinstance(data["subscriptions"], list):
                return data["subscriptions"]
            
            return []

        except httpx.HTTPStatusError as e:
            print(f"⚠️ API Error ({e.response.status_code}): {e}")
            return []
        except Exception as e:
            print(f"⚠️ Unexpected Error: {e}")
            return []


@mcp.tool()
async def run_smart_diagnostic(
    subscription_id: str, 
    issue_type: str = "INTERNET_ISSUES"
) -> Dict[str, Any]:
    """
    Runs a comprehensive system check for a specific subscription.
    
    This tool automatically checks:
    - Network status (outages)
    - Device settings (roaming, data enabled)
    - Account balance/limits
    
    Args:
        subscription_id (str): The unique UUID of the subscription to check.
        issue_type (str, optional): The category of the problem. Defaults to "INTERNET_ISSUES".
                                    Only change this if the user specifically mentions "CALLS" or "SMS".

    Returns:
        dict: A diagnostic report containing 'recommended_solutions', 'device_status', 
              and 'network_status'.
    """
    endpoint = f"{TURKCELL_API_BASE}/api/v1/troubleshooting/diagnose/{subscription_id}"
    
    # We pass the default or overridden issue_type
    params = {"issue_type": issue_type}
    
    async with httpx.AsyncClient() as client:
        try:
            # 10 second timeout for deep diagnosis
            response = await client.get(endpoint, params=params, timeout=10.0)
            response.raise_for_status()
            
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"⚠️ Diagnostic API Error ({e.response.status_code}): {e}")
            return {
                "success": False,
                "error": f"Status {e.response.status_code}",
                "message": "Diagnostic failed. Please escalate to human agent."
            }
        except Exception as e:
            print(f"⚠️ Unexpected Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "An unexpected error occurred during diagnostics."
            }



@mcp.tool()
async def get_device_technical_context(subscription_id: str) -> Dict[str, Any]:
    """
    Retrieves real-time technical details about the user's device.
    
    Use this tool to:
    1. Tailor instructions to the specific OS (Android vs iOS).
    2. Check critical settings: 'roaming_enabled', 'data_enabled', 'airplane_mode'.
    3. Verify signal strength (e.g., -68 dBm is good, -110 dBm is poor).
    4. confirm the device model (e.g., 'OnePlus 11').

    Args:
        subscription_id (str): The unique UUID of the subscription.

    Returns:
        dict: A flat dictionary containing 'device_model', 'os_type', 'roaming_enabled', etc.
              Returns an error dict if the API call fails.
    """
    endpoint = f"{TURKCELL_API_BASE}/api/v1/troubleshooting/device/{subscription_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            # 10s timeout to ensure we get accurate real-time data
            response = await client.get(endpoint, timeout=10.0)
            response.raise_for_status()
            
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"⚠️ Device Context API Error ({e.response.status_code}): {e}")
            return {
                "error": f"Status {e.response.status_code}",
                "message": "Could not retrieve device details."
            }
        except Exception as e:
            print(f"⚠️ Unexpected Error: {e}")
            return {
                "error": str(e),
                "message": "An unexpected error occurred while fetching device context."
            }


if __name__ == "__main__":
    mcp.run()