import logging
import sys
from datetime import datetime

class DebugLogger:
    _instance = None
    _debug_mode = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance
    
    def _setup_logger(self):
        self.logger = logging.getLogger('MangaTranslator')
        
        if self._debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.WARNING)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
            handler.setFormatter(formatter)
            try:
                handler.stream.reconfigure(encoding='utf-8')
            except:
                pass
            self.logger.addHandler(handler)
    
    def enable(self):
        self._debug_mode = True
        self.logger.setLevel(logging.DEBUG)
    
    def disable(self):
        self._debug_mode = False
        self.logger.setLevel(logging.WARNING)
    
    def is_enabled(self):
        return self._debug_mode
    
    def log_extraction_start(self, pdf_path):
        self.logger.info(f"开始提取文本: {pdf_path}")
    
    def log_extraction_page(self, page_num, char_count):
        self.logger.debug(f"  页面 {page_num}: {char_count} 个字符")
    
    def log_block_extracted(self, block_num, page_num, text_preview, font, size):
        self.logger.debug(f"  文本块 #{block_num} [页{page_num}] {font} {size:.1f}pt: {text_preview[:30]}...")
    
    def log_block_filtered(self, block_num, reason):
        self.logger.debug(f"  过滤文本块 #{block_num}: {reason}")
    
    def log_extraction_complete(self, total_blocks):
        self.logger.info(f"提取完成: 共 {total_blocks} 个文本块")
    
    def log_translation_start(self, total_blocks):
        self.logger.info(f"开始翻译: 共 {total_blocks} 个文本块")
    
    def log_translation_chunk(self, chunk_id, text_preview):
        self.logger.debug(f"  翻译块 #{chunk_id}: {text_preview[:50]}...")
    
    def log_translation_result(self, chunk_id, source, success):
        status = "成功" if success else "失败"
        self.logger.debug(f"  翻译块 #{chunk_id} 结果: {source} - {status}")
    
    def log_api_request(self, provider_name, model, url, prompt_preview, headers=None):
        prompt_display = prompt_preview[:200] + "..." if len(prompt_preview) > 200 else prompt_preview
        self.logger.info(f"=== API 请求 [{provider_name}] ===")
        self.logger.info(f"  Model: {model}")
        self.logger.info(f"  URL: {url}")
        self.logger.info(f"  Prompt: {prompt_display}")
        if headers:
            safe_headers = {k: v for k, v in headers.items() if k.lower() not in ['authorization', 'x-api-key']}
            self.logger.info(f"  Headers: {safe_headers}")
    
    def log_api_response(self, provider_name, status_code, response_text, success=True):
        status_str = "成功" if success else "失败"
        if self._debug_mode:
            # 在debug模式下显示完整的API返回内容
            self.logger.info(f"=== API 响应 [{provider_name}] {status_str} (HTTP {status_code}) ===")
            self.logger.info(f"  Response: {response_text}")
        else:
            # 在非debug模式下显示预览
            text_preview = response_text[:300] + "..." if len(response_text) > 300 else response_text
            self.logger.info(f"=== API 响应 [{provider_name}] {status_str} (HTTP {status_code}) ===")
            self.logger.info(f"  Response: {text_preview}")
    
    def log_translation_mapping(self, chunk_id, source_lines, translated_lines):
        """输出原文→译文的匹配效果预览"""
        if self._debug_mode:
            self.logger.info(f"=== 翻译映射 #{chunk_id} ===")
            for i, (source, translated) in enumerate(zip(source_lines, translated_lines)):
                self.logger.info(f"  原文{i+1}: {source}")
                self.logger.info(f"  译文{i+1}: {translated}")
                self.logger.info(f"  {'-' * 50}")
    
    def log_api_error(self, provider_name, error_msg, url=None):
        self.logger.error(f"=== API 错误 [{provider_name}] ===")
        if url:
            self.logger.error(f"  URL: {url}")
        self.logger.error(f"  Error: {error_msg}")
    
    def log_translation_progress(self, completed, total):
        self.logger.debug(f"  进度: {completed}/{total}")
    
    def log_translation_complete(self, total_translated):
        self.logger.info(f"翻译完成: 共 {total_translated} 个文本块")
    
    def log_annotation_start(self, total_blocks):
        self.logger.info(f"开始生成注释: 共 {total_blocks} 个文本块")
    
    def log_annotation_page(self, page_num, block_count):
        self.logger.debug(f"  页面 {page_num}: {block_count} 个注释")
    
    def log_annotation_added(self, block_num, text_preview, x, y):
        self.logger.debug(f"  添加注释 #{block_num} 位置({x:.2f},{y:.2f}): {text_preview[:30]}...")
    
    def log_annotation_skipped(self, block_num, reason):
        self.logger.debug(f"  跳过注释 #{block_num}: {reason}")
    
    def log_annotation_complete(self, total_annotations):
        self.logger.info(f"注释生成完成: 共 {total_annotations} 个注释")
    
    def log_error(self, stage, error_msg):
        self.logger.error(f"错误 [{stage}]: {error_msg}")
    
    def log_warning(self, stage, warning_msg):
        self.logger.warning(f"警告 [{stage}]: {warning_msg}")
    
    def log_info(self, message):
        self.logger.info(message)


def get_debug_logger():
    return DebugLogger()
