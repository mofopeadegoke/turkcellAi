from app.database import *
import os

print("🧪 Testing Live API Integration\n")
print(f"API Base URL: {os.getenv('API_BASE_URL')}")
print(f"API Key configured: {'Yes' if os.getenv('API_KEY') else 'No'}")
print("\n" + "="*60 + "\n")

# Test 1: Get customer by phone
print("Test 1: Get customer by phone")
customer = get_customer_by_phone("+905321000008")
if customer:
    print(f"✅ Customer found: {customer.get('full_name', 'N/A')}")
    print(f"   Customer ID: {customer.get('customer_id', 'N/A')}")
    print(f"   Language: {customer.get('preferred_language', 'N/A')}")
else:
    print("❌ Customer not found or API error")

print("\n" + "="*60 + "\n")

# Test 2: Search knowledge base (with query params)
print("Test 2: Search knowledge base")
results = search_knowledge_base("internet not working", "EN", limit=2)
if results and len(results) > 0:
    print(f"✅ Found {len(results)} knowledge base entries")
    for r in results:
        print(f"   - {r.get('title', 'No title')}")
else:
    print("⚠️  No results found")

print("\n" + "="*60 + "\n")

# Test 3: Check network status (returns list now)
print("Test 3: Check network issues")
issues = get_network_status()
if issues and len(issues) > 0:
    print(f"⚠️  Found {len(issues)} network issues")
    for issue in issues[:2]:  # Show first 2
        print(f"   - Region: {issue.get('region', 'N/A')}")
        print(f"     Type: {issue.get('issue_type', 'N/A')}")
        print(f"     Severity: {issue.get('severity', 'N/A')}")
else:
    print("✅ No network issues")

print("\n" + "="*60 + "\n")

# Test 4: Get packages by type
print("Test 4: Get tourist packages")
packages = get_packages(package_type="TOURIST")
if packages and len(packages) > 0:
    print(f"✅ Found {len(packages)} tourist packages")
    for p in packages[:3]:  # Show first 3
        print(f"   - {p.get('package_name', 'N/A')}: {p.get('price_try', 'N/A')} TRY")
else:
    print("⚠️  No packages found")

print("\n" + "="*60 + "\n")

# Test 5: Get balance by phone
print("Test 5: Get balance by phone")
balance = get_balance_by_phone("+905321000008")
if balance:
    print(f"✅ Balance found")
    print(f"   Data remaining: {balance.get('data_remaining_mb', 0) // 1024}GB")
    print(f"   Voice remaining: {balance.get('voice_remaining_min', 0)} min")
else:
    print("⚠️  No balance found")

print("\n" + "="*60 + "\n")

# Test 6: Get full customer profile
print("Test 6: Get full customer profile")
profile = get_full_customer_profile("+905321000008")
if profile:
    print(f"✅ Profile built for: {profile.get('full_name', 'N/A')}")
    print(f"   Has balance: {'Yes' if profile.get('balance') else 'No'}")
    print(f"   Has subscriptions: {'Yes' if profile.get('subscriptions') else 'No'}")
else:
    print("⚠️  Profile not found")

print("\n" + "="*60 + "\n")
print("✅ API integration tests complete!")