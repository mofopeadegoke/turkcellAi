import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# API Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'https://turkcellaiapi.onrender.com')
API_KEY = os.getenv('API_KEY')

def _make_request(method, endpoint, data=None, params=None):
    """Helper function to make API requests with X-API-Key authentication"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {
        'Content-Type': 'application/json'
    }
    
    if API_KEY:
        headers['X-API-Key'] = API_KEY
    
    # Increase timeout for slow API (Render free tier can be slow)
    TIMEOUT = 3
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=TIMEOUT)
        elif method.upper() == 'PATCH':
            response = requests.patch(url, json=data, headers=headers, timeout=TIMEOUT)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=TIMEOUT)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        print(f"   Response status: {response.status_code} ({response.elapsed.total_seconds():.2f}s)")
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        print(f"⚠️  API timeout: {endpoint} (>{TIMEOUT}s)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ API error ({endpoint}): {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text[:300]}")
        return None


# ==================== CUSTOMERS ====================

def get_customer_by_phone(phone_number):
    """
    Lookup customer by phone number
    
    Endpoint: GET /api/v1/customers/lookup?phone={phone}
    """
    phone = phone_number.replace('whatsapp:', '').replace(' ', '').strip()
    
    print(f"🔍 API: Looking up customer by phone: {phone}")
    
    result = _make_request('GET', '/api/v1/customers/lookup', params={'phone': phone})
    
    if result:
        print(f"✅ API: Customer found")
        return result
    
    print(f"⚠️  API: Customer not found")
    return None


def get_customer_by_id(customer_id):
    """
    Get customer by ID
    
    Endpoint: GET /api/v1/customers/{customer_id}
    """
    print(f"🔍 API: Looking up customer by ID: {customer_id}")
    
    result = _make_request('GET', f'/api/v1/customers/{customer_id}')
    return result


def create_customer(customer_data):
    """
    Create a new customer
    
    Endpoint: POST /api/v1/customers
    """
    print(f"📝 API: Creating customer - {customer_data.get('full_name')}")
    
    result = _make_request('POST', '/api/v1/customers', data=customer_data)
    
    if result:
        print(f"✅ API: Customer created")
    return result


def update_customer(customer_id, update_data):
    """
    Update customer information
    
    Endpoint: PATCH /api/v1/customers/{customer_id}
    """
    print(f"📝 API: Updating customer: {customer_id}")
    
    result = _make_request('PATCH', f'/api/v1/customers/{customer_id}', data=update_data)
    return result


def delete_customer(customer_id):
    """
    Delete customer
    
    Endpoint: DELETE /api/v1/customers/{customer_id}
    """
    print(f"🗑️  API: Deleting customer: {customer_id}")
    
    result = _make_request('DELETE', f'/api/v1/customers/{customer_id}')
    return result


def get_customer_subscriptions(customer_id):
    """
    Get all subscriptions for a customer
    
    Endpoint: GET /api/v1/customers/{customer_id}/subscriptions
    """
    print(f"📱 API: Getting subscriptions for customer: {customer_id}")
    
    result = _make_request('GET', f'/api/v1/customers/{customer_id}/subscriptions')
    return result


# ==================== PACKAGES ====================

def get_packages(package_type=None):
    """
    List all packages or filter by type
    
    Endpoint: GET /api/v1/packages
    Endpoint: GET /api/v1/packages/type/{package_type}
    """
    if package_type:
        print(f"📦 API: Getting packages of type: {package_type}")
        result = _make_request('GET', f'/api/v1/packages/type/{package_type}')
    else:
        print(f"📦 API: Getting all packages")
        result = _make_request('GET', '/api/v1/packages')
    
    return result if result else []


def get_package_by_id(package_id):
    """
    Get package details
    
    Endpoint: GET /api/v1/packages/{package_id}
    """
    result = _make_request('GET', f'/api/v1/packages/{package_id}')
    return result


def recommend_package(usage_data):
    """
    Get package recommendation based on usage
    
    Endpoint: GET /api/v1/packages/search/recommend
    """
    print(f"💡 API: Getting package recommendation")
    
    result = _make_request('GET', '/api/v1/packages/search/recommend', params=usage_data)
    return result


def compare_packages(package_ids):
    """
    Compare multiple packages
    
    Endpoint: GET /api/v1/packages/compare/packages
    """
    print(f"📊 API: Comparing packages")
    
    params = {'package_ids': ','.join(package_ids) if isinstance(package_ids, list) else package_ids}
    result = _make_request('GET', '/api/v1/packages/compare/packages', params=params)
    return result


# ==================== BALANCES ====================

def get_balance_by_subscription(subscription_id):
    """
    Get balance for a subscription
    
    Endpoint: GET /api/v1/balances/subscription/{subscription_id}
    """
    print(f"💰 API: Getting balance for subscription: {subscription_id}")
    
    result = _make_request('GET', f'/api/v1/balances/subscription/{subscription_id}')
    return result


def get_balance_by_phone(phone_number):
    """
    Get balance by phone number (MSISDN)
    
    Endpoint: GET /api/v1/balances/phone/{msisdn}
    """
    phone = phone_number.replace('whatsapp:', '').replace(' ', '').replace('+', '').strip()
    
    print(f"💰 API: Getting balance for phone: {phone}")
    
    result = _make_request('GET', f'/api/v1/balances/phone/{phone}')
    return result


def update_balance(balance_id, balance_data):
    """
    Update balance
    
    Endpoint: PATCH /api/v1/balances/{balance_id}
    """
    print(f"📊 API: Updating balance: {balance_id}")
    
    result = _make_request('PATCH', f'/api/v1/balances/{balance_id}', data=balance_data)
    return result


def recharge_balance(balance_id, recharge_data):
    """
    Recharge balance
    
    Endpoint: POST /api/v1/balances/{balance_id}/recharge
    """
    print(f"💳 API: Recharging balance: {balance_id}")
    
    result = _make_request('POST', f'/api/v1/balances/{balance_id}/recharge', data=recharge_data)
    return result


def get_usage_history(subscription_id, days=30):
    """
    Get usage history
    
    Endpoint: GET /api/v1/balances/subscription/{subscription_id}/usage-history
    """
    print(f"📈 API: Getting usage history for subscription: {subscription_id}")
    
    params = {'days': days}
    result = _make_request('GET', f'/api/v1/balances/subscription/{subscription_id}/usage-history', params=params)
    return result


def get_balance_summary(balance_id):
    """
    Get balance summary
    
    Endpoint: GET /api/v1/balances/{balance_id}/summary
    """
    result = _make_request('GET', f'/api/v1/balances/{balance_id}/summary')
    return result


# ==================== TROUBLESHOOTING ====================

def get_device_context(subscription_id):
    """
    Get device context for troubleshooting
    
    Endpoint: GET /api/v1/troubleshooting/device/{subscription_id}
    """
    print(f"📱 API: Getting device context: {subscription_id}")
    
    result = _make_request('GET', f'/api/v1/troubleshooting/device/{subscription_id}')
    return result


def update_device_context(subscription_id, device_data):
    """
    Update device context
    
    Endpoint: POST /api/v1/troubleshooting/device/{subscription_id}
    """
    print(f"📱 API: Updating device context: {subscription_id}")
    
    result = _make_request('POST', f'/api/v1/troubleshooting/device/{subscription_id}', data=device_data)
    return result


def get_network_status():
    """
    Get current network status
    
    Endpoint: GET /api/v1/troubleshooting/network-status
    
    Returns: dict with 'issues' key containing list of network issues
    """
    print(f"🌐 API: Getting network status")
    
    result = _make_request('GET', '/api/v1/troubleshooting/network-status')
    
    # API returns {"issues": [...]} not a list directly
    if result and isinstance(result, dict):
        return result.get('issues', [])
    
    return []


def get_network_status_by_region(region):
    """
    Get network status for specific region
    
    Endpoint: GET /api/v1/troubleshooting/network-status/region/{region}
    """
    print(f"🌐 API: Getting network status for region: {region}")
    
    result = _make_request('GET', f'/api/v1/troubleshooting/network-status/region/{region}')
    
    # API might return {"issues": [...]} or just a dict
    if result and isinstance(result, dict):
        return result.get('issues', [result] if result else [])
    
    return []


def search_knowledge_base(query, language='EN', limit=3):
    """
    Search knowledge base
    
    Endpoint: POST /api/v1/troubleshooting/knowledge-base/search?query={query}&language={language}&limit={limit}
    
    NOTE: Query parameters go in URL, but it's still a POST request
    """
    print(f"📚 API: Searching knowledge base - '{query}' (Language: {language})")
    
    # Build URL with query parameters
    url = f"{API_BASE_URL}/api/v1/troubleshooting/knowledge-base/search"
    headers = {
        'Content-Type': 'application/json'
    }
    
    if API_KEY:
        headers['X-API-Key'] = API_KEY
    
    params = {
        'query': query,
        'language': language,
        'limit': limit
    }
    
    try:
        # POST request with query parameters in URL
        response = requests.post(url, params=params, headers=headers, timeout=10)
        print(f"   Response status: {response.status_code}")
        
        response.raise_for_status()
        result = response.json()
        
        if result:
            # API might return {"results": [...]} or a list directly
            if isinstance(result, dict):
                results = result.get('results', result.get('data', result.get('knowledge_base', [])))
            else:
                results = result if isinstance(result, list) else []
            
            if results:
                print(f"✅ API: Found {len(results)} knowledge base results")
                return results
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API error: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text[:300]}")
    
    print(f"⚠️  API: No knowledge base results found")
    return []


def smart_diagnose(subscription_id):
    """
    Smart diagnosis of issues
    
    Endpoint: GET /api/v1/troubleshooting/diagnose/{subscription_id}
    """
    print(f"🔍 API: Running smart diagnosis: {subscription_id}")
    
    result = _make_request('GET', f'/api/v1/troubleshooting/diagnose/{subscription_id}')
    return result


def find_nearby_stores(latitude, longitude, radius_km=5):
    """
    Find nearby stores
    
    Endpoint: GET /api/v1/troubleshooting/stores/nearby
    """
    print(f"🏪 API: Finding stores near ({latitude}, {longitude})")
    
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'radius_km': radius_km
    }
    
    result = _make_request('GET', '/api/v1/troubleshooting/stores/nearby', params=params)
    
    # API might return {"stores": [...]}
    if result and isinstance(result, dict):
        return result.get('stores', [])
    
    return result if result else []


# ==================== INTERACTIONS ====================

def log_interaction(customer_id, channel, user_message, ai_response, intent=None, session_id=None):
    """
    Log AI interaction (if endpoint exists)
    
    Note: This endpoint may not exist in your API
    """
    if not customer_id:
        print("⚠️  API: No customer_id, skipping interaction log")
        return None
    
    interaction_data = {
        "customer_id": customer_id,
        "channel": channel,
        "user_message": user_message,
        "ai_response": ai_response,
        "intent_detected": intent,
        "session_id": session_id
    }
    
    print(f"💾 API: Attempting to log {channel} interaction")
    
    result = _make_request('POST', '/api/v1/interactions', data=interaction_data)
    
    if result:
        print(f"✅ API: Interaction logged")
        return result
    else:
        print(f"ℹ️  API: Interaction logging not available (skipping)")
        return None


# ==================== CONVENIENCE FUNCTIONS ====================

def get_full_customer_profile(phone_number):
    """
    Get complete customer profile with all related data
    """
    print(f"👤 API: Building full customer profile for: {phone_number}")
    
    # Get customer
    customer = get_customer_by_phone(phone_number)
    if not customer:
        return None
    
    # Get subscriptions
    subscriptions = None
    if customer.get('customer_id'):
        subscriptions = get_customer_subscriptions(customer['customer_id'])
    
    # Get balance by phone
    balance = get_balance_by_phone(phone_number)
    
    # Combine into single profile
    profile = {
        **customer,
        'subscriptions': subscriptions,
        'balance': balance
    }
    
    print(f"✅ API: Full profile built for {customer.get('full_name', 'Unknown')}")
    return profile


def check_network_issues(region=None):
    """
    Check network issues (with optional region filter)
    """
    if region:
        return get_network_status_by_region(region)
    else:
        return get_network_status()
    
# ==================== SUPPORT TICKETS ====================

def create_support_ticket(ticket_data):
    """
    Create a support ticket
    
    Endpoint: POST /api/v1/support-tickets (if it exists)
    
    Args:
        ticket_data (dict): {
            "customer_id": "uuid",
            "subscription_id": "uuid",
            "issue_type": "ESCALATION_REQUESTED",
            "priority": "HIGH",
            "description": "Customer requested human agent",
            "ai_attempted_resolution": "Previous conversation..."
        }
    """
    print(f"🎫 API: Creating support ticket - {ticket_data.get('issue_type')}")
    
    # Try to create ticket - if endpoint doesn't exist, fail gracefully
    result = _make_request('POST', '/api/v1/support-tickets', data=ticket_data)
    
    if result:
        ticket_id = (result.get('data') or result).get('ticket_id')
        print(f"✅ API: Ticket created with ID: {ticket_id}")
        return result.get('data') or result
    
    print(f"ℹ️  API: Support ticket endpoint not available (skipping)")
    return None