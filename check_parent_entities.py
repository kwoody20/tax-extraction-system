#!/usr/bin/env python3
"""
Check all properties in Supabase to ensure they have parent entity IDs.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json
from datetime import datetime

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in environment or .env file")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_parent_entities():
    """Check all properties for parent entity IDs"""
    
    print("=" * 80)
    print("PARENT ENTITY ID CHECK")
    print("=" * 80)
    
    # Get all properties
    try:
        properties_response = supabase.table('properties').select('*').execute()
        properties = properties_response.data
        
        print(f"\nTotal properties in database: {len(properties)}")
        print("-" * 80)
        
        # Categorize properties
        with_parent = []
        without_parent = []
        
        for prop in properties:
            if prop.get('parent_entity_id'):
                with_parent.append(prop)
            else:
                without_parent.append(prop)
        
        # Summary statistics
        print(f"\n📊 SUMMARY:")
        print(f"  ✅ Properties WITH parent entity ID: {len(with_parent)} ({len(with_parent)/len(properties)*100:.1f}%)")
        print(f"  ❌ Properties WITHOUT parent entity ID: {len(without_parent)} ({len(without_parent)/len(properties)*100:.1f}%)")
        
        # Show properties without parent entity ID
        if without_parent:
            print(f"\n🚨 PROPERTIES MISSING PARENT ENTITY ID ({len(without_parent)}):")
            print("-" * 80)
            for prop in without_parent:
                print(f"\nProperty ID: {prop['id']}")
                print(f"  Name: {prop.get('property_name', 'N/A')}")
                print(f"  Jurisdiction: {prop.get('jurisdiction', 'N/A')}")
                print(f"  State: {prop.get('state', 'N/A')}")
                print(f"  Amount Due: ${prop.get('amount_due', 0):,.2f}")
                print(f"  Previous Year: ${prop.get('previous_year_taxes', 0):,.2f}")
        
        # Get all entities for reference
        entities_response = supabase.table('entities').select('*').execute()
        entities = entities_response.data
        entity_dict = {e['id']: e['entity_name'] for e in entities}
        
        # Show parent entity distribution
        if with_parent:
            print(f"\n📈 PARENT ENTITY DISTRIBUTION:")
            print("-" * 80)
            
            entity_counts = {}
            for prop in with_parent:
                parent_id = prop['parent_entity_id']
                parent_name = entity_dict.get(parent_id, f"Unknown ({parent_id})")
                entity_counts[parent_name] = entity_counts.get(parent_name, 0) + 1
            
            # Sort by count
            sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
            
            for entity_name, count in sorted_entities[:10]:  # Top 10 entities
                print(f"  {entity_name}: {count} properties")
            
            if len(sorted_entities) > 10:
                print(f"  ... and {len(sorted_entities) - 10} more entities")
        
        # Financial impact of missing parent entities
        if without_parent:
            total_missing_due = sum(p.get('amount_due', 0) for p in without_parent)
            total_missing_prev = sum(p.get('previous_year_taxes', 0) for p in without_parent)
            
            print(f"\n💰 FINANCIAL IMPACT OF MISSING PARENT ENTITIES:")
            print("-" * 80)
            print(f"  Total Amount Due (missing parents): ${total_missing_due:,.2f}")
            print(f"  Total Previous Year (missing parents): ${total_missing_prev:,.2f}")
        
        # Recommendations
        print(f"\n📋 RECOMMENDATIONS:")
        print("-" * 80)
        if without_parent:
            print(f"  ⚠️  {len(without_parent)} properties need parent entity assignment")
            print(f"  💡 Review the properties above and assign appropriate parent entities")
            print(f"  💡 Check if these properties should be linked to existing entities or new ones")
        else:
            print(f"  ✅ All properties have parent entity IDs assigned!")
        
        # Save detailed report
        report_filename = f"parent_entity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_properties": len(properties),
                "with_parent_entity": len(with_parent),
                "without_parent_entity": len(without_parent),
                "percentage_complete": len(with_parent) / len(properties) * 100
            },
            "properties_without_parent": [
                {
                    "id": p['id'],
                    "name": p.get('property_name'),
                    "jurisdiction": p.get('jurisdiction'),
                    "state": p.get('state'),
                    "amount_due": p.get('amount_due'),
                    "previous_year_taxes": p.get('previous_year_taxes')
                }
                for p in without_parent
            ],
            "parent_entity_distribution": dict(entity_counts) if with_parent else {}
        }
        
        with open(report_filename, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_filename}")
        
        return len(without_parent) == 0  # Return True if all have parent entities
        
    except Exception as e:
        print(f"\n❌ Error querying database: {str(e)}")
        return False

if __name__ == "__main__":
    all_have_parents = check_parent_entities()
    
    if all_have_parents:
        print("\n✅ SUCCESS: All properties have parent entity IDs!")
        exit(0)
    else:
        print("\n⚠️  WARNING: Some properties are missing parent entity IDs")
        exit(1)