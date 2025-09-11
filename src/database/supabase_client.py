"""
Supabase client for property tax extraction system.
Handles database operations for entities, properties, and tax extractions.
"""

import os
import asyncio
import pandas as pd
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID
import json
from dotenv import load_dotenv
from supabase import create_client, Client
from supabase.client import AsyncClient, create_async_client

load_dotenv()


class SupabasePropertyTaxClient:
    """Synchronous Supabase client for property tax database operations."""
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """Initialize Supabase client."""
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Supabase URL and Key must be provided or set in environment variables")
        
        self.client: Client = create_client(self.url, self.key)
    
    # Entity Operations
    def get_entities(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all entities with pagination."""
        response = self.client.table("entities").select("*").range(offset, offset + limit - 1).execute()
        return response.data
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get a single entity by ID."""
        response = self.client.table("entities").select("*").eq("entity_id", entity_id).single().execute()
        return response.data
    
    def create_entity(self, entity_data: Dict) -> Dict:
        """Create a new entity."""
        response = self.client.table("entities").insert(entity_data).execute()
        return response.data[0] if response.data else None
    
    def update_entity(self, entity_id: str, updates: Dict) -> Dict:
        """Update an existing entity."""
        response = self.client.table("entities").update(updates).eq("entity_id", entity_id).execute()
        return response.data[0] if response.data else None
    
    def upsert_entity(self, entity_data: Dict) -> Dict:
        """Insert or update an entity."""
        response = self.client.table("entities").upsert(entity_data).execute()
        return response.data[0] if response.data else None
    
    # Property Operations
    def get_properties(self, limit: int = 100, offset: int = 0, filters: Optional[Dict] = None) -> List[Dict]:
        """Get properties with optional filters."""
        query = self.client.table("properties").select("*")
        
        if filters:
            if "state" in filters:
                query = query.eq("state", filters["state"])
            if "jurisdiction" in filters:
                query = query.eq("jurisdiction", filters["jurisdiction"])
            if "parent_entity_id" in filters:
                query = query.eq("parent_entity_id", filters["parent_entity_id"])
        
        response = query.range(offset, offset + limit - 1).execute()
        return response.data
    
    def get_property(self, property_id: str) -> Optional[Dict]:
        """Get a single property by ID."""
        response = self.client.table("properties").select("*").eq("property_id", property_id).single().execute()
        return response.data
    
    def create_property(self, property_data: Dict) -> Dict:
        """Create a new property."""
        response = self.client.table("properties").insert(property_data).execute()
        return response.data[0] if response.data else None
    
    def update_property(self, property_id: str, updates: Dict) -> Dict:
        """Update an existing property."""
        response = self.client.table("properties").update(updates).eq("property_id", property_id).execute()
        return response.data[0] if response.data else None
    
    def upsert_property(self, property_data: Dict) -> Dict:
        """Insert or update a property using the database function."""
        response = self.client.rpc("upsert_property", property_data).execute()
        return response.data
    
    # Tax Extraction Operations
    def record_extraction(self, extraction_data: Dict) -> Dict:
        """Record a tax extraction result."""
        response = self.client.rpc("record_extraction_result", extraction_data).execute()
        return response.data
    
    def get_recent_extractions(self, limit: int = 100) -> List[Dict]:
        """Get recent tax extractions."""
        response = self.client.table("recent_extractions").select("*").limit(limit).execute()
        return response.data
    
    def get_extraction_metrics(self, days: int = 30) -> List[Dict]:
        """Get extraction metrics for the specified number of days."""
        response = self.client.table("extraction_metrics").select("*").limit(days).execute()
        return response.data
    
    def find_properties_needing_extraction(self, days_since_last: int = 30) -> List[Dict]:
        """Find properties that need extraction."""
        response = self.client.rpc("find_properties_needing_extraction", {"p_days_since_last": days_since_last}).execute()
        return response.data
    
    # Jurisdiction Operations
    def get_jurisdictions(self, state: Optional[str] = None) -> List[Dict]:
        """Get all jurisdictions, optionally filtered by state."""
        query = self.client.table("jurisdictions").select("*")
        if state:
            query = query.eq("state", state)
        response = query.execute()
        return response.data
    
    def get_jurisdiction(self, jurisdiction_name: str) -> Optional[Dict]:
        """Get a single jurisdiction by name."""
        response = self.client.table("jurisdictions").select("*").eq("jurisdiction_name", jurisdiction_name).single().execute()
        return response.data
    
    def update_jurisdiction_config(self, jurisdiction_name: str, config: Dict) -> Dict:
        """Update jurisdiction extraction configuration."""
        response = self.client.table("jurisdictions").update({"extraction_config": config}).eq("jurisdiction_name", jurisdiction_name).execute()
        return response.data[0] if response.data else None
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics (stub for compatibility)."""
        # Regular client doesn't use pooling, return dummy stats
        return {
            "active": 0,
            "idle": 1,
            "total_requests": 0,
            "created": 1,
            "failed": 0,
            "avg_wait_time_ms": 0,
            "peak_connections": 1,
            "pool_size": 1,
            "overflow_count": 0,
            "uptime_seconds": 0
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics (stub for compatibility)."""
        return {
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "size": 0
        }
    
    def clear_cache(self):
        """Clear cache (stub for compatibility)."""
        pass
    
    def close(self):
        """Close client (stub for compatibility)."""
        pass
    
    # Bulk Operations
    def bulk_import_properties_from_csv(self, csv_path: str) -> Dict[str, Any]:
        """Import properties from CSV file."""
        df = pd.read_csv(csv_path, encoding='latin-1')
        results = {"success": 0, "failed": 0, "errors": []}
        
        for _, row in df.iterrows():
            try:
                property_data = {
                    "property_id": row.get("Property ID"),
                    "property_name": row.get("Property Name"),
                    "sub_entity": row.get("Sub-Entity") if pd.notna(row.get("Sub-Entity")) else None,
                    "parent_entity_name": row.get("Parent Entity") if pd.notna(row.get("Parent Entity")) else None,
                    "jurisdiction": row.get("Jurisdiction"),
                    "state": row.get("State"),
                    "property_type": row.get("Property Type", "property"),
                    "close_date": pd.to_datetime(row.get("Close Date")).date().isoformat() if pd.notna(row.get("Close Date")) else None,
                    "amount_due": float(str(row.get("Amount Due", "0")).replace("$", "").replace(",", "") or "0"),
                    "previous_year_taxes": float(str(row.get("Previous Year Taxes", "0")).replace("$", "").replace(",", "") or "0"),
                    "extraction_steps": row.get("Extraction Steps"),
                    "account_number": str(row.get("Acct Number")) if pd.notna(row.get("Acct Number")) else None,
                    "property_address": row.get("Property Address"),
                    "tax_bill_link": row.get("Tax Bill Link"),
                    "tax_due_date": pd.to_datetime(row.get("Tax Due Date")).date().isoformat() if pd.notna(row.get("Tax Due Date")) else None,
                    "paid_by": row.get("Paid By") if pd.notna(row.get("Paid By")) else None
                }
                
                self.upsert_property(property_data)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "row": row.get("Property ID"),
                    "error": str(e)
                })
        
        return results
    
    def bulk_import_entities_from_csv(self, csv_path: str) -> Dict[str, Any]:
        """Import entities from CSV file."""
        df = pd.read_csv(csv_path, encoding='latin-1')
        results = {"success": 0, "failed": 0, "errors": []}
        
        # Get column names from first row
        columns = df.columns.tolist()
        
        for _, row in df.iterrows():
            try:
                # First column is entity_id, second is entity_name
                entity_data = {
                    "entity_id": row[columns[0]],
                    "entity_name": row[columns[1]],
                    "jurisdiction": row[columns[4]] if len(columns) > 4 and pd.notna(row[columns[4]]) else None,
                    "state": row[columns[5]] if len(columns) > 5 and pd.notna(row[columns[5]]) else None,
                    "entity_type": row[columns[6]] if len(columns) > 6 and pd.notna(row[columns[6]]) else "parent entity",
                    "close_date": pd.to_datetime(row[columns[7]]).date().isoformat() if len(columns) > 7 and pd.notna(row[columns[7]]) else None
                }
                
                # Handle amount_due and previous_year_taxes if they exist
                if len(columns) > 8 and pd.notna(row[columns[8]]):
                    try:
                        entity_data["amount_due"] = float(str(row[columns[8]]).replace("$", "").replace(",", ""))
                    except:
                        pass
                
                if len(columns) > 9 and pd.notna(row[columns[9]]):
                    try:
                        entity_data["previous_year_taxes"] = float(str(row[columns[9]]).replace("$", "").replace(",", ""))
                    except:
                        pass
                
                # Additional fields
                if len(columns) > 10:
                    entity_data["extraction_steps"] = row[columns[10]] if pd.notna(row[columns[10]]) else None
                if len(columns) > 11:
                    entity_data["account_number"] = str(row[columns[11]]) if pd.notna(row[columns[11]]) else None
                if len(columns) > 12:
                    entity_data["property_address"] = row[columns[12]] if pd.notna(row[columns[12]]) else None
                if len(columns) > 13:
                    entity_data["tax_bill_link"] = row[columns[13]] if pd.notna(row[columns[13]]) else None
                
                self.upsert_entity(entity_data)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "row": row[columns[0]] if len(columns) > 0 else "Unknown",
                    "error": str(e)
                })
        
        return results
    
    # Analytics Operations
    def get_entity_portfolio_summary(self) -> List[Dict]:
        """Get portfolio summary for all entities."""
        response = self.client.table("entity_portfolio_summary").select("*").execute()
        return response.data
    
    def get_tax_payment_overview(self, state: Optional[str] = None) -> List[Dict]:
        """Get tax payment overview by state and jurisdiction."""
        query = self.client.table("tax_payment_overview").select("*")
        if state:
            query = query.eq("state", state)
        response = query.execute()
        return response.data
    
    def get_property_details(self, property_id: str) -> Optional[Dict]:
        """Get detailed property information including entity and jurisdiction."""
        response = self.client.table("property_details").select("*").eq("property_id", property_id).single().execute()
        return response.data
    
    def calculate_tax_statistics(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict:
        """Calculate tax statistics for a date range."""
        params = {}
        if start_date:
            params["p_start_date"] = start_date.isoformat()
        if end_date:
            params["p_end_date"] = end_date.isoformat()
        
        response = self.client.rpc("calculate_tax_statistics", params).execute()
        return response.data[0] if response.data else {}


class AsyncSupabasePropertyTaxClient:
    """Asynchronous Supabase client for property tax database operations."""
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """Initialize async Supabase client."""
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Supabase URL and Key must be provided or set in environment variables")
        
        self.client: Optional[AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = await create_async_client(self.url, self.key)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.close()
    
    async def get_entities(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all entities with pagination."""
        response = await self.client.table("entities").select("*").range(offset, offset + limit - 1).execute()
        return response.data
    
    async def get_properties_needing_extraction(self, days_since_last: int = 30) -> List[Dict]:
        """Find properties that need extraction."""
        response = await self.client.rpc("find_properties_needing_extraction", {"p_days_since_last": days_since_last}).execute()
        return response.data
    
    async def record_extraction(self, extraction_data: Dict) -> Dict:
        """Record a tax extraction result."""
        response = await self.client.rpc("record_extraction_result", extraction_data).execute()
        return response.data
    
    async def bulk_record_extractions(self, extractions: List[Dict]) -> Dict[str, Any]:
        """Record multiple extraction results."""
        results = {"success": 0, "failed": 0, "errors": []}
        
        for extraction in extractions:
            try:
                await self.record_extraction(extraction)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "property_id": extraction.get("p_property_id"),
                    "error": str(e)
                })
        
        return results


# Example usage
if __name__ == "__main__":
    # Synchronous example
    client = SupabasePropertyTaxClient()
    
    # Import data from CSV files
    print("Importing entities...")
    entity_results = client.bulk_import_entities_from_csv("entities-proptax-8202025.csv")
    print(f"Entities imported: {entity_results['success']} success, {entity_results['failed']} failed")
    
    print("\nImporting properties...")
    property_results = client.bulk_import_properties_from_csv("OFFICIAL-proptax-assets.csv")
    print(f"Properties imported: {property_results['success']} success, {property_results['failed']} failed")
    
    # Get statistics
    stats = client.calculate_tax_statistics()
    print(f"\nTax Statistics:")
    print(f"Total Properties: {stats.get('total_properties')}")
    print(f"Total Amount Due: ${stats.get('total_amount_due', 0):,.2f}")
    print(f"Properties with Balance: {stats.get('properties_with_balance')}")
    
    # Find properties needing extraction
    properties_to_extract = client.find_properties_needing_extraction(days_since_last=30)
    print(f"\nProperties needing extraction: {len(properties_to_extract)}")
    
    # Async example
    async def async_example():
        async with AsyncSupabasePropertyTaxClient() as async_client:
            properties = await async_client.get_properties_needing_extraction(30)
            print(f"Properties to extract (async): {len(properties)}")
    
    # Run async example
    # asyncio.run(async_example())