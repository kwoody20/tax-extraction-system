#!/usr/bin/env python3
"""
Document Management Service for Tax Documents
Handles storage, retrieval, OCR, and extraction of tax documents
"""

import asyncio
import base64
import hashlib
import io
import json
import logging
import mimetypes
import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4

import aiohttp
import requests
from PIL import Image
import PyPDF2
import pytesseract
from pdf2image import convert_from_path, convert_from_bytes
from supabase import create_client, Client
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import pandas as pd
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_KEY else None

# ================================================================================
# DATA MODELS
# ================================================================================

class DocumentUpload(BaseModel):
    """Model for document upload request"""
    property_id: str
    entity_id: Optional[str] = None
    jurisdiction: str
    document_type: str = "tax_bill"
    tax_year: Optional[int] = None
    tax_period: Optional[str] = None
    amount_due: Optional[float] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = []

class DocumentSearch(BaseModel):
    """Model for document search request"""
    property_id: Optional[str] = None
    entity_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    document_type: Optional[str] = None
    tax_year: Optional[int] = None
    status: Optional[str] = None
    search_text: Optional[str] = None
    tags: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0

class DocumentExtraction(BaseModel):
    """Model for document extraction request"""
    property_id: str
    url: str
    jurisdiction: str
    extraction_type: str = "tax_bill"
    priority: int = 5

class PaymentRecord(BaseModel):
    """Model for payment recording"""
    document_id: str
    property_id: str
    payment_amount: float
    payment_date: str
    payment_method: Optional[str] = None
    confirmation_number: Optional[str] = None
    paid_by: Optional[str] = None
    notes: Optional[str] = None

# ================================================================================
# DOCUMENT STORAGE SERVICE
# ================================================================================

class DocumentStorageService:
    """Service for managing document storage in Supabase"""
    
    def __init__(self):
        self.supabase = supabase
        self.bucket_name = "tax-documents"
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """Ensure storage bucket exists"""
        try:
            buckets = self.supabase.storage.list_buckets()
            if not any(b['name'] == self.bucket_name for b in buckets):
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    options={"public": False}
                )
                logger.info(f"Created storage bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Error ensuring bucket: {e}")
    
    async def upload_document(
        self,
        file_content: bytes,
        file_name: str,
        property_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Upload document to Supabase storage"""
        try:
            # Generate unique storage path
            file_extension = Path(file_name).suffix
            storage_name = f"{property_id}/{datetime.now().year}/{uuid4()}{file_extension}"
            
            # Upload to Supabase storage
            response = self.supabase.storage.from_(self.bucket_name).upload(
                path=storage_name,
                file=file_content,
                file_options={"content-type": mimetypes.guess_type(file_name)[0]}
            )
            
            # Get public URL
            public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(storage_name)
            
            # Create database record
            document_data = {
                "property_id": property_id,
                "entity_id": metadata.get("entity_id"),
                "jurisdiction": metadata.get("jurisdiction"),
                "document_type": metadata.get("document_type", "tax_bill"),
                "document_name": metadata.get("document_name", file_name),
                "file_name": file_name,
                "file_size": len(file_content),
                "mime_type": mimetypes.guess_type(file_name)[0],
                "storage_path": storage_name,
                "storage_bucket": self.bucket_name,
                "public_url": public_url,
                "tax_year": metadata.get("tax_year"),
                "tax_period": metadata.get("tax_period"),
                "amount_due": metadata.get("amount_due"),
                "due_date": metadata.get("due_date"),
                "notes": metadata.get("notes"),
                "tags": metadata.get("tags", []),
                "status": "pending",
                "uploaded_by": metadata.get("uploaded_by", "system")
            }
            
            # Insert into database
            result = self.supabase.table("tax_documents").insert(document_data).execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def download_document(self, document_id: str) -> Tuple[bytes, str]:
        """Download document from storage"""
        try:
            # Get document metadata
            result = self.supabase.table("tax_documents").select("*").eq("id", document_id).execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Document not found")
            
            document = result.data[0]
            
            # Download from storage
            file_content = self.supabase.storage.from_(self.bucket_name).download(
                document["storage_path"]
            )
            
            return file_content, document["file_name"]
            
        except Exception as e:
            logger.error(f"Error downloading document: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document from storage and database"""
        try:
            # Get document metadata
            result = self.supabase.table("tax_documents").select("*").eq("id", document_id).execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Document not found")
            
            document = result.data[0]
            
            # Delete from storage
            self.supabase.storage.from_(self.bucket_name).remove([document["storage_path"]])
            
            # Delete from database
            self.supabase.table("tax_documents").delete().eq("id", document_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# ================================================================================
# OCR SERVICE
# ================================================================================

class OCRService:
    """Service for OCR processing of documents"""
    
    @staticmethod
    async def process_pdf(file_content: bytes) -> Dict[str, Any]:
        """Extract text and data from PDF"""
        try:
            # Try text extraction first
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text_content = ""
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"
            
            # If no text found, use OCR
            if len(text_content.strip()) < 100:
                text_content = await OCRService.ocr_pdf(file_content)
            
            # Extract structured data
            extracted_data = OCRService.extract_tax_data(text_content)
            
            return {
                "text": text_content,
                "extracted_data": extracted_data,
                "page_count": len(pdf_reader.pages),
                "method": "text_extraction" if len(text_content.strip()) >= 100 else "ocr"
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return {"error": str(e)}
    
    @staticmethod
    async def ocr_pdf(file_content: bytes) -> str:
        """OCR a PDF file"""
        try:
            # Convert PDF to images
            images = convert_from_bytes(file_content)
            
            text_content = ""
            for i, image in enumerate(images):
                # Perform OCR on each page
                page_text = pytesseract.image_to_string(image)
                text_content += f"\n--- Page {i+1} ---\n{page_text}"
            
            return text_content
            
        except Exception as e:
            logger.error(f"Error in OCR: {e}")
            return ""
    
    @staticmethod
    async def process_image(file_content: bytes) -> Dict[str, Any]:
        """Extract text from image using OCR"""
        try:
            image = Image.open(io.BytesIO(file_content))
            text_content = pytesseract.image_to_string(image)
            
            # Get OCR confidence
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Extract structured data
            extracted_data = OCRService.extract_tax_data(text_content)
            
            return {
                "text": text_content,
                "extracted_data": extracted_data,
                "confidence": avg_confidence,
                "method": "ocr"
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def extract_tax_data(text: str) -> Dict[str, Any]:
        """Extract structured tax data from text"""
        extracted = {}
        
        # Extract amounts
        amount_patterns = [
            r"(?:Total Due|Amount Due|Balance Due)[\s:]*\$?([\d,]+\.?\d*)",
            r"(?:Total|Amount)[\s:]*\$?([\d,]+\.?\d*)",
            r"\$?([\d,]+\.\d{2})(?:\s|$)"
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    extracted["amount_due"] = float(amount_str)
                    break
                except:
                    pass
        
        # Extract dates
        date_patterns = [
            r"(?:Due Date|Payment Due|Due By)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(?:Due|Payable).*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})"
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["due_date"] = match.group(1)
                break
        
        # Extract account/parcel numbers
        account_patterns = [
            r"(?:Account|Acct|Parcel)[\s#:]*([A-Z0-9\-]+)",
            r"(?:Property ID|Tax ID)[\s:]*([A-Z0-9\-]+)"
        ]
        
        for pattern in account_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["account_number"] = match.group(1)
                break
        
        # Extract tax year
        year_match = re.search(r"(?:Tax Year|Year)[\s:]*(\d{4})", text, re.IGNORECASE)
        if year_match:
            extracted["tax_year"] = int(year_match.group(1))
        
        # Extract property address
        address_match = re.search(
            r"(?:Property Address|Location|Situs)[\s:]*(.+?)(?:\n|$)",
            text,
            re.IGNORECASE
        )
        if address_match:
            extracted["property_address"] = address_match.group(1).strip()
        
        return extracted

# ================================================================================
# DOCUMENT EXTRACTION SERVICE
# ================================================================================

class DocumentExtractionService:
    """Service for extracting documents from tax websites"""
    
    def __init__(self):
        self.storage_service = DocumentStorageService()
        self.ocr_service = OCRService()
    
    async def extract_document_from_url(
        self,
        url: str,
        property_id: str,
        jurisdiction: str,
        extraction_type: str = "tax_bill"
    ) -> Optional[Dict[str, Any]]:
        """Extract and save document from URL"""
        try:
            # Download document
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download: {response.status}")
                    
                    file_content = await response.read()
                    content_type = response.headers.get('Content-Type', '')
                    
                    # Determine file extension
                    if 'pdf' in content_type:
                        file_extension = '.pdf'
                    elif 'image' in content_type:
                        file_extension = '.png'
                    else:
                        file_extension = '.html'
                    
                    file_name = f"{jurisdiction}_{extraction_type}_{datetime.now().strftime('%Y%m%d')}{file_extension}"
            
            # Process document based on type
            if file_extension == '.pdf':
                ocr_result = await self.ocr_service.process_pdf(file_content)
            elif file_extension in ['.png', '.jpg', '.jpeg']:
                ocr_result = await self.ocr_service.process_image(file_content)
            else:
                # Parse HTML
                ocr_result = await self._parse_html_document(file_content)
            
            # Prepare metadata
            metadata = {
                "property_id": property_id,
                "jurisdiction": jurisdiction,
                "document_type": extraction_type,
                "document_name": f"{jurisdiction} {extraction_type.replace('_', ' ').title()}",
                "extracted_from_url": url,
                "extraction_date": datetime.now().isoformat(),
                "extraction_method": "automated",
                "ocr_text": ocr_result.get("text", ""),
                "extracted_data": ocr_result.get("extracted_data", {}),
                "amount_due": ocr_result.get("extracted_data", {}).get("amount_due"),
                "due_date": ocr_result.get("extracted_data", {}).get("due_date"),
                "tax_year": ocr_result.get("extracted_data", {}).get("tax_year")
            }
            
            # Upload to storage
            document = await self.storage_service.upload_document(
                file_content,
                file_name,
                property_id,
                metadata
            )
            
            # Update OCR status
            if document and ocr_result.get("text"):
                self.supabase.table("tax_documents").update({
                    "ocr_processed": True,
                    "ocr_text": ocr_result.get("text", ""),
                    "ocr_confidence": ocr_result.get("confidence"),
                    "extracted_data": json.dumps(ocr_result.get("extracted_data", {})),
                    "status": "processed"
                }).eq("id", document["id"]).execute()
            
            return document
            
        except Exception as e:
            logger.error(f"Error extracting document from {url}: {e}")
            return None
    
    async def _parse_html_document(self, html_content: bytes) -> Dict[str, Any]:
        """Parse HTML content for tax data"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text()
            
            # Remove excessive whitespace
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            
            # Extract data
            extracted_data = self.ocr_service.extract_tax_data(text_content)
            
            return {
                "text": text_content,
                "extracted_data": extracted_data,
                "method": "html_parsing"
            }
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return {"error": str(e)}
    
    async def queue_extraction(
        self,
        property_id: str,
        url: str,
        jurisdiction: str,
        extraction_type: str = "tax_bill",
        priority: int = 5
    ) -> str:
        """Queue document for extraction"""
        try:
            queue_data = {
                "property_id": property_id,
                "url": url,
                "jurisdiction": jurisdiction,
                "extraction_type": extraction_type,
                "priority": priority,
                "status": "queued"
            }
            
            result = self.supabase.table("document_extraction_queue").insert(queue_data).execute()
            
            return result.data[0]["id"] if result.data else None
            
        except Exception as e:
            logger.error(f"Error queuing extraction: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def process_extraction_queue(self):
        """Process documents in extraction queue"""
        try:
            # Get queued items
            result = self.supabase.table("document_extraction_queue")\
                .select("*")\
                .eq("status", "queued")\
                .order("priority", desc=False)\
                .limit(10)\
                .execute()
            
            for item in result.data:
                try:
                    # Update status
                    self.supabase.table("document_extraction_queue").update({
                        "status": "processing",
                        "started_at": datetime.now().isoformat()
                    }).eq("id", item["id"]).execute()
                    
                    # Extract document
                    document = await self.extract_document_from_url(
                        item["url"],
                        item["property_id"],
                        item["jurisdiction"],
                        item["extraction_type"]
                    )
                    
                    # Update queue
                    if document:
                        self.supabase.table("document_extraction_queue").update({
                            "status": "completed",
                            "document_id": document["id"],
                            "completed_at": datetime.now().isoformat()
                        }).eq("id", item["id"]).execute()
                    else:
                        raise Exception("Document extraction failed")
                        
                except Exception as e:
                    # Update with error
                    self.supabase.table("document_extraction_queue").update({
                        "status": "failed",
                        "error_message": str(e),
                        "retry_count": item["retry_count"] + 1
                    }).eq("id", item["id"]).execute()
                    
        except Exception as e:
            logger.error(f"Error processing extraction queue: {e}")

# ================================================================================
# DOCUMENT SEARCH SERVICE
# ================================================================================

class DocumentSearchService:
    """Service for searching and filtering documents"""
    
    def __init__(self):
        self.supabase = supabase
    
    async def search_documents(self, search_params: DocumentSearch) -> List[Dict[str, Any]]:
        """Search documents with filters"""
        try:
            query = self.supabase.table("tax_documents").select("*")
            
            # Apply filters
            if search_params.property_id:
                query = query.eq("property_id", search_params.property_id)
            
            if search_params.entity_id:
                query = query.eq("entity_id", search_params.entity_id)
            
            if search_params.jurisdiction:
                query = query.eq("jurisdiction", search_params.jurisdiction)
            
            if search_params.document_type:
                query = query.eq("document_type", search_params.document_type)
            
            if search_params.tax_year:
                query = query.eq("tax_year", search_params.tax_year)
            
            if search_params.status:
                query = query.eq("status", search_params.status)
            
            if search_params.date_from:
                query = query.gte("created_at", search_params.date_from)
            
            if search_params.date_to:
                query = query.lte("created_at", search_params.date_to)
            
            if search_params.tags:
                query = query.contains("tags", search_params.tags)
            
            # Full-text search
            if search_params.search_text:
                query = query.text_search(
                    "search_vector",
                    search_params.search_text,
                    config="english"
                )
            
            # Apply pagination
            query = query.range(
                search_params.offset,
                search_params.offset + search_params.limit - 1
            )
            
            # Order by created_at desc
            query = query.order("created_at", desc=True)
            
            result = query.execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_document_summary(self, property_id: Optional[str] = None) -> Dict[str, Any]:
        """Get document summary statistics"""
        try:
            if property_id:
                result = self.supabase.rpc("get_property_document_summary", {
                    "prop_id": property_id
                }).execute()
            else:
                result = self.supabase.table("document_summary").select("*").execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting document summary: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_upcoming_payments(self) -> List[Dict[str, Any]]:
        """Get upcoming payment obligations"""
        try:
            result = self.supabase.table("upcoming_payments").select("*").execute()
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting upcoming payments: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# ================================================================================
# FASTAPI APPLICATION
# ================================================================================

app = FastAPI(
    title="Tax Document Management API",
    description="API for managing tax documents, invoices, and bills",
    version="1.0.0"
)

# Initialize services
storage_service = DocumentStorageService()
ocr_service = OCRService()
extraction_service = DocumentExtractionService()
search_service = DocumentSearchService()

@app.post("/api/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    property_id: str = Form(...),
    entity_id: Optional[str] = Form(None),
    jurisdiction: str = Form(...),
    document_type: str = Form("tax_bill"),
    tax_year: Optional[int] = Form(None),
    amount_due: Optional[float] = Form(None),
    due_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    tags: Optional[str] = Form(None)
):
    """Upload a tax document"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Parse tags
        tag_list = tags.split(",") if tags else []
        
        # Prepare metadata
        metadata = {
            "property_id": property_id,
            "entity_id": entity_id,
            "jurisdiction": jurisdiction,
            "document_type": document_type,
            "document_name": file.filename,
            "tax_year": tax_year,
            "amount_due": amount_due,
            "due_date": due_date,
            "notes": notes,
            "tags": tag_list
        }
        
        # Upload document
        document = await storage_service.upload_document(
            file_content,
            file.filename,
            property_id,
            metadata
        )
        
        # Queue OCR processing
        if document and file.content_type in ["application/pdf", "image/png", "image/jpeg"]:
            background_tasks.add_task(process_document_ocr, document["id"], file_content)
        
        return {"message": "Document uploaded successfully", "document": document}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/{document_id}/download")
async def download_document(document_id: str):
    """Download a document"""
    file_content, file_name = await storage_service.download_document(document_id)
    
    return StreamingResponse(
        io.BytesIO(file_content),
        media_type=mimetypes.guess_type(file_name)[0],
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    success = await storage_service.delete_document(document_id)
    return {"message": "Document deleted successfully" if success else "Failed to delete document"}

@app.post("/api/documents/search")
async def search_documents(search_params: DocumentSearch):
    """Search documents"""
    documents = await search_service.search_documents(search_params)
    return {"documents": documents, "count": len(documents)}

@app.post("/api/documents/extract")
async def extract_document(extraction_request: DocumentExtraction):
    """Queue document extraction from URL"""
    queue_id = await extraction_service.queue_extraction(
        extraction_request.property_id,
        extraction_request.url,
        extraction_request.jurisdiction,
        extraction_request.extraction_type,
        extraction_request.priority
    )
    return {"message": "Extraction queued", "queue_id": queue_id}

@app.post("/api/documents/process-queue")
async def process_queue(background_tasks: BackgroundTasks):
    """Process extraction queue"""
    background_tasks.add_task(extraction_service.process_extraction_queue)
    return {"message": "Queue processing started"}

@app.get("/api/documents/summary")
async def get_summary(property_id: Optional[str] = Query(None)):
    """Get document summary"""
    summary = await search_service.get_document_summary(property_id)
    return {"summary": summary}

@app.get("/api/documents/upcoming-payments")
async def get_upcoming_payments():
    """Get upcoming payment obligations"""
    payments = await search_service.get_upcoming_payments()
    return {"payments": payments}

@app.post("/api/documents/record-payment")
async def record_payment(payment: PaymentRecord):
    """Record a payment for a document"""
    try:
        payment_data = payment.dict()
        result = supabase.table("document_payments").insert(payment_data).execute()
        
        # Update document paid_date
        supabase.table("tax_documents").update({
            "paid_date": payment.payment_date
        }).eq("id", payment.document_id).execute()
        
        return {"message": "Payment recorded", "payment": result.data[0]}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Background task for OCR processing
async def process_document_ocr(document_id: str, file_content: bytes):
    """Process document with OCR in background"""
    try:
        # Determine file type and process
        result = await ocr_service.process_pdf(file_content)
        
        # Update document with OCR results
        if result and not result.get("error"):
            supabase.table("tax_documents").update({
                "ocr_processed": True,
                "ocr_text": result.get("text", ""),
                "ocr_confidence": result.get("confidence"),
                "extracted_data": json.dumps(result.get("extracted_data", {})),
                "amount_due": result.get("extracted_data", {}).get("amount_due"),
                "due_date": result.get("extracted_data", {}).get("due_date"),
                "status": "processed"
            }).eq("id", document_id).execute()
            
    except Exception as e:
        logger.error(f"Error in OCR processing: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)