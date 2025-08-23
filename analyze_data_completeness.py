"""
Analyze Supabase data completeness for properties table
"""

import os
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import json

# Get Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_KEY:
    # Try to load from .env file
    try:
        with open('.env', 'r') as f:
            for line in f:
                if 'SUPABASE_KEY=' in line and 'SERVICE_ROLE' not in line:
                    SUPABASE_KEY = line.split('=', 1)[1].strip().strip('"').strip("'")
                    break
    except:
        pass

if not SUPABASE_KEY:
    print("❌ Error: SUPABASE_KEY not found in environment variables or .env file")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🔍 Analyzing Supabase Data Completeness")
print("=" * 60)

try:
    # Fetch all properties
    response = supabase.table('properties').select("*").execute()
    properties = response.data
    
    if not properties:
        print("❌ No properties found in database")
        exit(1)
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(properties)
    
    print(f"\n📊 Total Properties: {len(df)}")
    print(f"📋 Total Columns: {len(df.columns)}")
    print("\n" + "=" * 60)
    
    # Analyze each field
    print("\n📈 FIELD COMPLETENESS ANALYSIS:")
    print("-" * 60)
    
    field_stats = []
    
    for column in df.columns:
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
        
        # Show sample values for partially filled fields
        if 0 < completeness_pct < 100 and column not in ['id', 'created_at', 'updated_at']:
            sample_values = df[df[column].notna() & (df[column] != '')][column].dropna().head(3).tolist()
            if sample_values:
                print(f"   Sample values: {sample_values[:3]}")
    
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
        'acct_number'
    ]
    
    for field in critical_fields:
        if field in df.columns:
            non_empty = df[field].notna().sum() if field != 'amount_due' else df[field].notna().sum()
            if df[field].dtype == 'object' and field != 'amount_due':
                non_empty = df[field].fillna('').str.strip().str.len().gt(0).sum()
            
            pct = (non_empty / len(df) * 100)
            status = "✅" if pct == 100 else "⚠️" if pct >= 75 else "❌"
            print(f"{status} {field:25} | {non_empty:3}/{len(df):3} ({pct:5.1f}%)")
        else:
            print(f"❌ {field:25} | Field does not exist!")
    
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
        missing_jurisdiction = df['jurisdiction'].isna() | (df['jurisdiction'] == '')
        if missing_jurisdiction.sum() > 0:
            print(f"⚠️ Properties without jurisdiction: {missing_jurisdiction.sum()}")
    
    print("\n" + "=" * 60)
    
    # Entity relationship analysis
    print("\n👥 ENTITY RELATIONSHIPS:")
    print("-" * 60)
    
    if 'parent_entity_name' in df.columns:
        entity_counts = df['parent_entity_name'].value_counts()
        print(f"Total Entities: {len(entity_counts)}")
        print(f"Properties with Entity: {df['parent_entity_name'].notna().sum()}/{len(df)}")
        
        missing_entity = df['parent_entity_name'].isna() | (df['parent_entity_name'] == '')
        if missing_entity.sum() > 0:
            print(f"\n⚠️ Properties without entity assignment: {missing_entity.sum()}")
            # Show some properties without entities
            missing_props = df[missing_entity][['property_name', 'property_address', 'state']].head(5)
            print("\nSample properties without entities:")
            for _, row in missing_props.iterrows():
                print(f"  • {row['property_name']} - {row['property_address']} ({row['state']})")
    
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
            print(f"Total amount due: ${df[positive_amount]['amount_due'].sum():,.2f}")
    
    if 'previous_year_taxes' in df.columns:
        has_prev = df['previous_year_taxes'].notna() & (df['previous_year_taxes'] > 0)
        print(f"\nProperties with previous year taxes: {has_prev.sum()}/{len(df)}")
        if has_prev.sum() > 0:
            print(f"Total previous year taxes: ${df[has_prev]['previous_year_taxes'].sum():,.2f}")
    
    print("\n" + "=" * 60)
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    print("-" * 60)
    
    recommendations = []
    
    # Check for missing critical fields
    for field in critical_fields:
        if field in df.columns:
            if df[field].dtype == 'object':
                missing = (df[field].isna() | (df[field] == '')).sum()
            else:
                missing = df[field].isna().sum()
            
            if missing > 0 and field != 'amount_due':  # amount_due can be 0
                recommendations.append(f"Update {missing} properties missing '{field}'")
    
    # Check for geographic gaps
    if 'state' in df.columns:
        missing_state = (df['state'].isna() | (df['state'] == '')).sum()
        if missing_state > 0:
            recommendations.append(f"Add state information for {missing_state} properties")
    
    if 'jurisdiction' in df.columns:
        missing_jurisdiction = (df['jurisdiction'].isna() | (df['jurisdiction'] == '')).sum()
        if missing_jurisdiction > 0:
            recommendations.append(f"Add jurisdiction for {missing_jurisdiction} properties")
    
    # Check entity assignments
    if 'parent_entity_name' in df.columns:
        missing_entity = (df['parent_entity_name'].isna() | (df['parent_entity_name'] == '')).sum()
        if missing_entity > 0:
            recommendations.append(f"Assign entities to {missing_entity} properties")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("✅ All critical fields are fully populated!")
    
    # Save detailed report
    print("\n" + "=" * 60)
    print("\n📄 Generating detailed report...")
    
    # Create detailed report DataFrame
    report_df = pd.DataFrame(field_stats)
    report_df = report_df.sort_values('Completeness %', ascending=False)
    
    # Save to CSV
    report_filename = f"data_completeness_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    report_df.to_csv(report_filename, index=False)
    print(f"✅ Report saved to: {report_filename}")
    
    # Also save properties with missing critical fields
    if any([(df[field].isna() | (df[field] == '')).sum() > 0 for field in critical_fields if field in df.columns]):
        missing_critical_df = df[df[critical_fields].isna().any(axis=1) | (df[critical_fields] == '').any(axis=1)]
        missing_filename = f"properties_missing_fields_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        missing_critical_df.to_csv(missing_filename, index=False)
        print(f"✅ Properties with missing fields saved to: {missing_filename}")

except Exception as e:
    print(f"\n❌ Error analyzing data: {e}")
    import traceback
    traceback.print_exc()