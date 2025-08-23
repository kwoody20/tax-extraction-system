"""
Analyze data completeness from JSON file
"""

import json
import pandas as pd
from datetime import datetime

print("🔍 Analyzing Data Completeness from JSON")
print("=" * 60)

try:
    # Load JSON data
    with open('properties_data.json', 'r') as f:
        data = json.load(f)
    
    properties = data.get('properties', [])
    
    if not properties:
        print("❌ No properties found")
        exit(1)
    
    # Convert to DataFrame
    df = pd.DataFrame(properties)
    
    print(f"\n📊 Total Properties: {len(df)}")
    print(f"📋 Total Columns: {len(df.columns)}")
    print("\n" + "=" * 60)
    
    # Analyze each field
    print("\n📈 FIELD COMPLETENESS ANALYSIS:")
    print("-" * 60)
    
    field_stats = []
    
    for column in sorted(df.columns):
        total_count = len(df)
        
        # Count non-null values
        non_null_count = df[column].notna().sum()
        
        # Count non-empty strings (for string fields)
        if df[column].dtype == 'object':
            non_empty_count = df[column].fillna('').str.strip().str.len().gt(0).sum()
        else:
            non_empty_count = non_null_count
        
        # Special handling for amount_due (0.00 is valid)
        if column == 'amount_due':
            valid_count = df[column].notna().sum()
            non_empty_count = valid_count
        
        # Calculate percentages
        completeness_pct = (non_empty_count / total_count * 100) if total_count > 0 else 0
        
        field_stats.append({
            'Field': column,
            'Populated': non_empty_count,
            'Missing': total_count - non_empty_count,
            'Completeness %': completeness_pct
        })
        
        # Print detailed info
        status_icon = "✅" if completeness_pct == 100 else "⚠️" if completeness_pct >= 50 else "❌"
        print(f"{status_icon} {column:30} | {non_empty_count:3}/{total_count:3} ({completeness_pct:5.1f}%)")
    
    print("\n" + "=" * 60)
    
    # Critical fields analysis
    print("\n🎯 CRITICAL FIELDS STATUS:")
    print("-" * 60)
    
    critical_fields = [
        'property_name',
        'property_address', 
        'jurisdiction',
        'state',
        'parent_entity_id',
        'parent_entity_name',
        'amount_due',
        'previous_year_taxes',
        'tax_bill_link',
        'account_number',
        'acct_number'
    ]
    
    for field in critical_fields:
        if field in df.columns:
            non_empty = df[field].notna().sum()
            if df[field].dtype == 'object':
                non_empty = df[field].fillna('').str.strip().str.len().gt(0).sum()
            
            pct = (non_empty / len(df) * 100)
            status = "✅" if pct == 100 else "⚠️" if pct >= 75 else "❌"
            print(f"{status} {field:25} | {non_empty:3}/{len(df):3} ({pct:5.1f}%)")
        else:
            print(f"⚠️ {field:25} | Field does not exist in data")
    
    print("\n" + "=" * 60)
    
    # Geographic coverage analysis
    print("\n🗺️ GEOGRAPHIC COVERAGE:")
    print("-" * 60)
    
    if 'state' in df.columns:
        state_counts = df['state'].value_counts()
        print(f"Total States: {len(state_counts)}")
        print("\nProperties by State:")
        for state, count in state_counts.items():
            if pd.notna(state) and state != '':
                print(f"  • {state}: {count} properties")
        
        missing_state = df['state'].isna() | (df['state'] == '')
        if missing_state.sum() > 0:
            print(f"\n⚠️ Properties without state: {missing_state.sum()}")
    
    if 'jurisdiction' in df.columns:
        print(f"\nTotal Jurisdictions: {df['jurisdiction'].nunique()}")
        jurisdiction_counts = df['jurisdiction'].value_counts()
        print("\nTop 10 Jurisdictions:")
        for jurisdiction, count in jurisdiction_counts.head(10).items():
            if pd.notna(jurisdiction) and jurisdiction != '':
                print(f"  • {jurisdiction}: {count} properties")
        
        missing_jurisdiction = df['jurisdiction'].isna() | (df['jurisdiction'] == '')
        if missing_jurisdiction.sum() > 0:
            print(f"\n⚠️ Properties without jurisdiction: {missing_jurisdiction.sum()}")
    
    print("\n" + "=" * 60)
    
    # Entity relationship analysis
    print("\n👥 ENTITY RELATIONSHIPS:")
    print("-" * 60)
    
    if 'parent_entity_name' in df.columns:
        entity_counts = df['parent_entity_name'].value_counts()
        print(f"Total Entities: {len(entity_counts)}")
        print(f"Properties with Entity: {df['parent_entity_name'].notna().sum()}/{len(df)}")
        
        print("\nTop 10 Entities by Property Count:")
        for entity, count in entity_counts.head(10).items():
            print(f"  • {entity}: {count} properties")
        
        missing_entity = df['parent_entity_name'].isna() | (df['parent_entity_name'] == '')
        if missing_entity.sum() > 0:
            print(f"\n⚠️ Properties without entity assignment: {missing_entity.sum()}")
    
    print("\n" + "=" * 60)
    
    # Tax data completeness
    print("\n💰 TAX DATA STATUS:")
    print("-" * 60)
    
    if 'amount_due' in df.columns:
        has_amount = df['amount_due'].notna()
        zero_amount = (df['amount_due'] == 0) | (df['amount_due'] == 0.0)
        positive_amount = df['amount_due'] > 0
        
        print(f"Properties with amount_due populated: {has_amount.sum()}/{len(df)}")
        print(f"Properties with $0.00 due (valid): {zero_amount.sum()}")
        print(f"Properties with positive amount due: {positive_amount.sum()}")
        
        if positive_amount.sum() > 0:
            total_due = df[positive_amount]['amount_due'].sum()
            print(f"Total amount due: ${total_due:,.2f}")
    
    if 'previous_year_taxes' in df.columns:
        has_prev = df['previous_year_taxes'].notna() & (df['previous_year_taxes'] > 0)
        print(f"\nProperties with previous year taxes: {has_prev.sum()}/{len(df)}")
        if has_prev.sum() > 0:
            total_prev = df[has_prev]['previous_year_taxes'].sum()
            print(f"Total previous year taxes: ${total_prev:,.2f}")
    
    print("\n" + "=" * 60)
    
    # Additional fields analysis
    print("\n🔍 ADDITIONAL FIELD ANALYSIS:")
    print("-" * 60)
    
    optional_fields = ['property_address', 'tax_bill_link', 'account_number', 'acct_number', 
                      'extraction_steps', 'close_date', 'property_type', 'sub_entity']
    
    for field in optional_fields:
        if field in df.columns:
            non_empty = df[field].notna().sum()
            if df[field].dtype == 'object':
                non_empty = df[field].fillna('').str.strip().str.len().gt(0).sum()
            pct = (non_empty / len(df) * 100)
            print(f"  {field:25} | {non_empty:3}/{len(df):3} ({pct:5.1f}%)")
    
    print("\n" + "=" * 60)
    
    # Summary and Recommendations
    print("\n📊 SUMMARY & RECOMMENDATIONS:")
    print("-" * 60)
    
    issues = []
    
    # Check critical fields
    if 'property_address' not in df.columns or df['property_address'].fillna('').str.strip().str.len().gt(0).sum() == 0:
        issues.append("🔴 CRITICAL: No property addresses found - needed for geographic visualization")
    elif 'property_address' in df.columns:
        missing_addr = (df['property_address'].isna() | (df['property_address'] == '')).sum()
        if missing_addr > 0:
            issues.append(f"🟠 HIGH: {missing_addr} properties missing addresses")
    
    if 'tax_bill_link' in df.columns:
        missing_link = (df['tax_bill_link'].isna() | (df['tax_bill_link'] == '')).sum()
        if missing_link > 0:
            issues.append(f"🟡 MEDIUM: {missing_link} properties missing tax bill links")
    
    if 'account_number' in df.columns or 'acct_number' in df.columns:
        acct_field = 'account_number' if 'account_number' in df.columns else 'acct_number'
        missing_acct = (df[acct_field].isna() | (df[acct_field] == '')).sum()
        if missing_acct > 0:
            issues.append(f"🟡 MEDIUM: {missing_acct} properties missing account numbers")
    
    if issues:
        print("\n⚠️ Issues Found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ All fields are adequately populated!")
    
    print("\n💡 Key Insights:")
    print(f"  • Data contains {len(df)} properties across {df['state'].nunique() if 'state' in df.columns else 0} states")
    print(f"  • {df['parent_entity_name'].notna().sum() if 'parent_entity_name' in df.columns else 0} properties are assigned to entities")
    print(f"  • Tax data is {df['amount_due'].notna().sum()/len(df)*100:.1f}% complete")
    
    # Save report
    report_df = pd.DataFrame(field_stats).sort_values('Completeness %', ascending=False)
    report_filename = f"field_completeness_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    report_df.to_csv(report_filename, index=False)
    print(f"\n✅ Detailed report saved to: {report_filename}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()