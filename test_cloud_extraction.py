"""
Test cloud extraction functionality
"""

from cloud_extractor import extract_tax_cloud

# Test data from actual properties
test_properties = [
    {
        "id": "test1",
        "property_name": "Montgomery Test Property",
        "jurisdiction": "Montgomery",
        "tax_bill_link": "https://actweb.acttax.com/act_webdev/montgomery/showdetail2.jsp?account=R105121",
        "account_number": "R105121"
    },
    {
        "id": "test2", 
        "property_name": "Fort Bend Test",
        "jurisdiction": "Fort Bend",
        "tax_bill_link": "https://tax.fortbendcountytx.gov/",
        "account_number": None
    }
]

print("Testing Cloud Extraction")
print("=" * 60)

for prop in test_properties:
    print(f"\nTesting: {prop['property_name']}")
    print(f"Jurisdiction: {prop['jurisdiction']}")
    
    result = extract_tax_cloud(prop)
    
    if result.get("success"):
        print("✅ Extraction successful!")
        print(f"   Tax Amount: ${result.get('tax_amount', 0):.2f}" if result.get('tax_amount') else "   Tax Amount: Not found")
        print(f"   Address: {result.get('property_address')}" if result.get('property_address') else "   Address: Not found")
        print(f"   Method: {result.get('extraction_method')}")
    else:
        print(f"❌ Extraction failed: {result.get('error')}")

print("\n" + "=" * 60)
print("\nSupported Jurisdictions:")
from cloud_extractor import cloud_extractor
for key, info in cloud_extractor.get_supported_jurisdictions().items():
    print(f"  • {key}: {info['confidence']} confidence")