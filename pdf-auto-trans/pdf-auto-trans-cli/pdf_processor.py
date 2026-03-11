import os
import pdfplumber
import pymupdf
import base64
import json
import requests
from typing import List, Dict, Tuple, Optional

class PDFProcessor:
    def __init__(self):
        self.supported_ocr_providers = ["ollama", "api"]
    
    def merge_pdfs(self, input_folder: str, output_path: str) -> str:
        pdf_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')])
        
        if not pdf_files:
            raise ValueError(f"在 {input_folder} 中未找到PDF文件")
        
        merged_doc = pymupdf.open()
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_folder, pdf_file)
            src_doc = pymupdf.open(pdf_path)
            merged_doc.insert_pdf(src_doc)
            src_doc.close()
        
        merged_doc.save(output_path)
        merged_doc.close()
        
        return output_path
    
    def detect_pdf_type(self, pdf_path: str) -> Dict:
        result = {
            "is_scanned": False,
            "has_text": False,
            "page_count": 0,
            "text_pages": 0,
            "empty_pages": 0,
            "confidence": 0.0
        }
        
        try:
            with pdfplumber.open(pdf_path) as plumber_pdf:
                result["page_count"] = len(plumber_pdf.pages)
                
                for page in plumber_pdf.pages:
                    text = page.extract_text()
                    chars = page.chars
                    
                    if text and text.strip():
                        result["has_text"] = True
                        result["text_pages"] += 1
                    elif not chars or len(chars) == 0:
                        result["empty_pages"] += 1
                
                if result["text_pages"] == 0 and result["page_count"] > 0:
                    result["is_scanned"] = True
                    result["confidence"] = 1.0
                elif result["text_pages"] < result["page_count"]:
                    result["is_scanned"] = result["text_pages"] == 0
                    result["confidence"] = result["text_pages"] / result["page_count"] if result["page_count"] > 0 else 0
                else:
                    result["confidence"] = 1.0
                    
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def merge_and_detect_type(self, input_folder: str, temp_merged_path: str) -> Tuple[str, Dict]:
        merged_path = self.merge_pdfs(input_folder, temp_merged_path)
        pdf_type = self.detect_pdf_type(merged_path)
        return merged_path, pdf_type
    
    def compress_pdf(self, input_path: str, output_path: str = None, 
                     max_size_mb: int = 50) -> Tuple[str, float]:
        if output_path is None:
            base_name = os.path.splitext(input_path)[0]
            output_path = f"{base_name}_compressed.pdf"
        
        input_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        
        if input_size_mb <= max_size_mb:
            return input_path, input_size_mb
        
        print(f"PDF大小 {input_size_mb:.2f}MB 超过限制 {max_size_mb}MB，正在压缩...")
        
        try:
            doc = pymupdf.open(input_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page.get_pixmap(alpha=False)
            
            doc.save(
                output_path,
                garbage=4,
                deflate=True,
                clean=True,
                deflate_images=True
            )
            doc.close()
            
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            compression_ratio = (1 - output_size_mb / input_size_mb) * 100
            
            print(f"PDF压缩完成: {input_size_mb:.2f}MB -> {output_size_mb:.2f}MB (减少 {compression_ratio:.1f}%)")
            
            return output_path, output_size_mb
            
        except Exception as e:
            print(f"PDF压缩失败: {str(e)}")
            return input_path, input_size_mb
    
    def get_pdf_size_mb(self, pdf_path: str) -> float:
        return os.path.getsize(pdf_path) / (1024 * 1024)


class OCRProcessor:
    def __init__(self, ocr_provider: str = "ollama", ocr_config: Optional[Dict] = None):
        self.ocr_provider = ocr_provider
        self.ocr_config = ocr_config or {}
        self._setup_provider()
    
    def _setup_provider(self):
        if self.ocr_provider == "ollama":
            self.ollama_base_url = self.ocr_config.get("api_base_url", "http://localhost:11434")
            self.ollama_model = self.ocr_config.get("model", "glm-ocr")
        elif self.ocr_provider == "api":
            self.api_url = self.ocr_config.get("api_url", "")
            self.api_key = self.ocr_config.get("api_key", "")
    
    def extract_page_image(self, pdf_path: str, page_num: int) -> str:
        doc = pymupdf.open(pdf_path)
        page = doc[page_num]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
        img_data = pix.tobytes("png")
        doc.close()
        return base64.b64encode(img_data).decode('utf-8')
    
    def ocr_with_ollama(self, image_base64: str, page_num: int) -> List[Dict]:
        prompt = """请识别图片中的所有文字。对于每个文字块，请提供以下JSON格式的信息：
        {
            "text": "识别出的文字",
            "x": 文字的X坐标(相对位置,0-1),
            "y": 文字的Y坐标(相对位置,0-1),
            "width": 文字的宽度(相对位置,0-1),
            "height": 文字的高度(相对位置,0-1)
        }
        
        请以JSON数组格式输出，格式如下：
        [{"text": "...", "x": 0.1, "y": 0.2, "width": 0.05, "height": 0.02}, ...]"""
        
        payload = {
            "model": self.ollama_model,
            "images": [image_base64],
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            
            response_text = result.get("response", "")
            return self._parse_ocr_response(response_text)
        except Exception as e:
            print(f"Ollama OCR失败 (页 {page_num + 1}): {str(e)}")
            return []
    
    def ocr_with_api(self, image_base64: str, page_num: int) -> List[Dict]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "image": image_base64,
            "return_coordinates": True
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            return self._parse_api_response(result)
        except Exception as e:
            print(f"API OCR失败 (页 {page_num + 1}): {str(e)}")
            return []
    
    def _parse_ocr_response(self, response_text: str) -> List[Dict]:
        try:
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return []
    
    def _parse_api_response(self, result: Dict) -> List[Dict]:
        if "data" in result:
            return result["data"]
        elif "texts" in result:
            return result["texts"]
        return []
    
    def ocr_pdf(self, pdf_path: str, page_start: int = 0, page_end: Optional[int] = None) -> List[Dict]:
        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)
        
        if page_end is None:
            page_end = total_pages
        
        all_results = []
        
        for page_num in range(page_start, min(page_end, total_pages)):
            print(f"  OCR处理页 {page_num + 1}/{total_pages}...")
            
            image_base64 = self.extract_page_image(pdf_path, page_num)
            
            if self.ocr_provider == "ollama":
                page_results = self.ocr_with_ollama(image_base64, page_num)
            else:
                page_results = self.ocr_with_api(image_base64, page_num)
            
            for item in page_results:
                item["page"] = page_num + 1
            
            all_results.extend(page_results)
        
        doc.close()
        return all_results
    
    def ocr_results_to_blocks(self, ocr_results: List[Dict]) -> List[Dict]:
        blocks = []
        
        for item in ocr_results:
            text = item.get("text", "").strip()
            if not text:
                continue
            
            x = item.get("x", 0)
            y = item.get("y", 0)
            width = item.get("width", 0.01)
            height = item.get("height", 0.01)
            
            blocks.append({
                "page": item.get("page", 1),
                "text": text,
                "font": "OCR",
                "size": height * 100,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "is_ocr": True
            })
        
        return blocks


def merge_pdfs(input_folder: str, output_path: str) -> str:
    processor = PDFProcessor()
    return processor.merge_pdfs(input_folder, output_path)

def detect_pdf_type(pdf_path: str) -> Dict:
    processor = PDFProcessor()
    return processor.detect_pdf_type(pdf_path)

def process_pdf_with_ocr(pdf_path: str, ocr_provider: str = "ollama", ocr_config: Optional[Dict] = None) -> List[Dict]:
    ocr = OCRProcessor(ocr_provider, ocr_config)
    results = ocr.ocr_pdf(pdf_path)
    return ocr.ocr_results_to_blocks(results)
