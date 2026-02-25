# app/ocr_processor.py - FREE OCR using PaddleOCR/EasyOCR
import os
import re
import json
import logging
import numpy as np
from PIL import Image
import io
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import cv2
from pdf2image import convert_from_bytes

# OCR Libraries
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
    print("✅ PaddleOCR is available")
except ImportError:
    PADDLE_AVAILABLE = False
    print("⚠️ PaddleOCR not installed")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
    print("✅ EasyOCR is available")
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️ EasyOCR not installed")

from app.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRDocumentProcessor:
    """Extract data from Indian government documents using FREE OCR"""
    
    def __init__(self, engine: str = None):
        """
        Initialize OCR processor
        
        Args:
            engine: 'paddle' or 'easyocr' (default from settings)
        """
        self.engine = engine or settings.OCR_ENGINE
        self.languages = settings.OCR_LANGUAGES
        self.confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD
        self.use_gpu = settings.OCR_USE_GPU
        
        logger.info(f"🚀 Initializing OCR processor with engine: {self.engine}")
        logger.info(f"📚 Languages: {self.languages}")
        logger.info(f"🎮 Use GPU: {self.use_gpu}")
        
        # Initialize OCR engine
        self.reader = self._initialize_reader()
        
        # Document table map from settings
        self.doc_table_map = settings.DOCUMENT_TABLE_MAP
        
        if not self.reader:
            logger.error("❌ No OCR engine available!")
    
    def _initialize_reader(self):
        """Initialize the selected OCR engine"""
        
        # Try PaddleOCR first if selected
        if self.engine == "paddle" and PADDLE_AVAILABLE:
            try:
                logger.info("📡 Initializing PaddleOCR...")
                
                # Map languages for PaddleOCR
                # PaddleOCR uses different language codes, default to 'en' for now
                return PaddleOCR(
                    use_angle_cls=True,
                    lang='en',  # PaddleOCR handles multilingual automatically
                    show_log=False,
                    use_gpu=self.use_gpu,
                    ocr_version='PP-OCRv4'  # Latest version
                )
            except Exception as e:
                logger.error(f"❌ PaddleOCR initialization failed: {e}")
                logger.info("⚠️ Falling back to EasyOCR...")
                self.engine = "easyocr"
        
        # Try EasyOCR
        if (self.engine == "easyocr" or not PADDLE_AVAILABLE) and EASYOCR_AVAILABLE:
            try:
                logger.info("📡 Initializing EasyOCR...")
                
                # Map language codes for EasyOCR
                easyocr_langs = []
                for lang in self.languages:
                    if lang in settings.EASYOCR_LANG_MAP:
                        easyocr_langs.append(settings.EASYOCR_LANG_MAP[lang])
                
                if not easyocr_langs:
                    easyocr_langs = ['en']
                
                logger.info(f"📚 EasyOCR languages: {easyocr_langs}")
                
                return easyocr.Reader(
                    easyocr_langs,
                    gpu=self.use_gpu,
                    model_storage_directory='~/.easyocr/model',
                    download_enabled=True,
                    recog_network='standard'  # Use standard recognition network
                )
            except Exception as e:
                logger.error(f"❌ EasyOCR initialization failed: {e}")
        
        logger.error("❌ No OCR engine could be initialized!")
        return None
    
    async def process_document(self,
                               file_bytes: bytes,
                               file_name: str,
                               document_type: str,
                               farmer_id: str) -> Dict[str, Any]:
        """
        Extract structured data from document using OCR
        
        Args:
            file_bytes: Raw file bytes
            file_name: Original filename
            document_type: Type of document (aadhaar, pan, etc.)
            farmer_id: Farmer ID for linking
        
        Returns:
            Dictionary with extracted data
        """
        try:
            logger.info(f"🔍 Processing {document_type} document for farmer {farmer_id}")
            
            if not self.reader:
                return {
                    "success": False,
                    "error": "OCR engine not initialized. Please check your installation."
                }
            
            # Convert to image if PDF
            images = await self._convert_to_images(file_bytes, file_name)
            
            if not images:
                return {
                    "success": False,
                    "error": "Could not convert document to image"
                }
            
            # Process each page (usually first page is enough)
            all_text = []
            all_boxes = []
            
            for i, image in enumerate(images[:3]):  # Max 3 pages
                logger.info(f"📄 Processing page {i+1}/{min(len(images), 3)}")
                
                # Preprocess image for better OCR
                processed_image = self._preprocess_image(image)
                
                # Perform OCR based on engine
                if self.engine == "paddle":
                    result = self.reader.ocr(np.array(processed_image), cls=True)
                    page_text, page_boxes = self._parse_paddle_result(result)
                else:  # easyocr
                    result = self.reader.readtext(np.array(processed_image))
                    page_text, page_boxes = self._parse_easyocr_result(result)
                
                all_text.extend(page_text)
                all_boxes.extend(page
