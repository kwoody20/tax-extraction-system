#!/usr/bin/env python3
"""
Bulk upload tax documents from a directory
"""
import os
import sys
import re
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class DocumentUploader:
    def __init__(self):
        self.supabase = supabase
        self.properties_cache = None
        self.entities_cache = None
        self.upload_results = []
    
    def load_cache(self):
        """Load properties and entities into cache"""
        if not self.properties_cache:
            result = self.supabase.table("properties").select("*").execute()
            self.properties_cache = result.data
            print(f"Loaded {len(self.properties_cache)} properties")
        
        if not self.entities_cache:
            result = self.supabase.table("entities").select("*").execute()
            self.entities_cache = result.data
            print(f"Loaded {len(self.entities_cache)} entities")
    
    def find_property_by_info(self, file_name):
        """Try to match property based on filename information"""
        # Extract relevant info from filename
        address_patterns = [
            r'(\d+\s+[A-Z\s]+(?:ST|RD|HWY|AVE|DR|LN|BLVD))',  # Street address
            r'(\d+\s+SH\s+\d+)',  # State Highway
            r'(\d+\s+INTERSTATE\s+\d+)',  # Interstate
        ]
        
        # Extract board order numbers
        bo_match = re.search(r'Board Order\s+(\d+)', file_name)
        invoice_match = re.search(r'Invoice[_-]\s*(.+?)\.pdf', file_name, re.IGNORECASE)
        
        # Try to find by address
        for pattern in address_patterns:
            match = re.search(pattern, file_name.upper())
            if match:
                address = match.group(1)
                for prop in self.properties_cache:
                    prop_address = (prop.get('property_address') or '').upper()
                    prop_name = (prop.get('property_name') or '').upper()
                    if address in prop_address or address in prop_name:
                        return prop.get('id'), prop.get('parent_entity_id'), prop.get('property_name'), address
        
        # Try to find by account number if board order
        if bo_match:
            account_num = bo_match.group(1)
            for prop in self.properties_cache:
                if prop.get('account_number') == account_num:
                    return prop.get('id'), prop.get('parent_entity_id'), prop.get('property_name'), f"Account #{account_num}"
        
        # Try invoice address extraction
        if invoice_match:
            address_part = invoice_match.group(1).strip()
            if address_part and address_part not in ['', ' ']:
                # Clean up address
                address_part = address_part.replace('[', '').replace(']', '').strip()
                for prop in self.properties_cache:
                    prop_address = (prop.get('property_address') or '').upper()
                    prop_name = (prop.get('property_name') or '').upper()
                    if address_part.upper() in prop_address or address_part.upper() in prop_name:
                        return prop.get('id'), prop.get('parent_entity_id'), prop.get('property_name'), address_part
        
        return None, None, None, None
    
    def determine_document_type(self, file_name):
        """Determine document type from filename"""
        file_lower = file_name.lower()
        if 'board order' in file_lower:
            return 'tax_bill', 'Board Order'  # Use tax_bill as the enum value
        elif 'invoice' in file_lower:
            return 'invoice', 'Invoice'
        elif 'tax' in file_lower:
            return 'tax_bill', 'Tax Bill'
        else:
            return 'tax_bill', 'Document'  # Default to tax_bill
    
    def upload_document(self, file_path):
        """Upload a single document"""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        print(f"\nProcessing: {file_name}")
        print("-" * 40)
        
        # Find matching property
        property_id, entity_id, property_name, match_info = self.find_property_by_info(file_name)
        
        # Determine document type
        doc_type, doc_type_display = self.determine_document_type(file_name)
        
        # Extract any numbers from filename for reference
        numbers = re.findall(r'\d+', file_name)
        doc_number = numbers[0] if numbers else None
        
        # Build document data
        document_data = {
            "property_id": property_id if property_id else str(uuid4()),
            "jurisdiction": "Harris County",  # Default, could be enhanced
            "document_type": doc_type,
            "document_name": f"{doc_type_display} - {match_info if match_info else file_name}",
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": "application/pdf",
            "notes": f"Bulk uploaded from tax-uploads directory",
            "status": "pending",
            "uploaded_by": "bulk_upload"
        }
        
        if doc_number:
            document_data["notes"] += f" | Document #: {doc_number}"
        
        # Add entity_id if available and valid
        if entity_id:
            # Verify entity exists in cache
            entity_exists = any(e.get('id') == entity_id for e in self.entities_cache)
            if entity_exists:
                try:
                    document_data["entity_id"] = entity_id
                except:
                    pass
        
        try:
            # Insert into database
            result = self.supabase.table("tax_documents").insert(document_data).execute()
            
            if result.data:
                status = "✅ SUCCESS"
                doc_id = result.data[0]['id']
                self.upload_results.append({
                    'file': file_name,
                    'status': 'success',
                    'doc_id': doc_id,
                    'property': property_name or 'Unmatched',
                    'match_info': match_info
                })
                print(f"  Status: {status}")
                print(f"  Document ID: {doc_id}")
                if property_name:
                    print(f"  Matched Property: {property_name}")
                    print(f"  Match Info: {match_info}")
                else:
                    print(f"  ⚠️ No property match found")
            else:
                raise Exception("No data returned from insert")
                
        except Exception as e:
            status = "❌ FAILED"
            self.upload_results.append({
                'file': file_name,
                'status': 'failed',
                'error': str(e),
                'property': property_name or 'Unmatched'
            })
            print(f"  Status: {status}")
            print(f"  Error: {e}")
        
        return status == "✅ SUCCESS"
    
    def process_directory(self, directory_path):
        """Process all PDF files in a directory"""
        pdf_files = [f for f in os.listdir(directory_path) if f.endswith('.pdf')]
        
        print("=" * 60)
        print("BULK DOCUMENT UPLOAD")
        print("=" * 60)
        print(f"Directory: {directory_path}")
        print(f"Found {len(pdf_files)} PDF files")
        print("=" * 60)
        
        # Load cache
        print("\nLoading database cache...")
        self.load_cache()
        print("-" * 60)
        
        # Process each file
        success_count = 0
        for pdf_file in pdf_files:
            file_path = os.path.join(directory_path, pdf_file)
            if self.upload_document(file_path):
                success_count += 1
        
        # Print summary
        print("\n" + "=" * 60)
        print("UPLOAD SUMMARY")
        print("=" * 60)
        print(f"Total Files: {len(pdf_files)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {len(pdf_files) - success_count}")
        print("-" * 60)
        
        # Show detailed results
        print("\nDetailed Results:")
        for result in self.upload_results:
            if result['status'] == 'success':
                print(f"✅ {result['file']}")
                print(f"   → Property: {result['property']}")
                if result.get('match_info'):
                    print(f"   → Matched by: {result['match_info']}")
                print(f"   → Doc ID: {result['doc_id'][:8]}...")
            else:
                print(f"❌ {result['file']}")
                print(f"   → Error: {result.get('error', 'Unknown error')}")
        
        print("=" * 60)
        
        return success_count, len(pdf_files) - success_count

def main():
    # Directory to process
    upload_dir = "/Users/kwoody/Downloads/tax-uploads"
    
    # Check if directory exists
    if not os.path.exists(upload_dir):
        print(f"❌ Error: Directory not found: {upload_dir}")
        sys.exit(1)
    
    # Create uploader and process
    uploader = DocumentUploader()
    success, failed = uploader.process_directory(upload_dir)
    
    # Exit with appropriate code
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()