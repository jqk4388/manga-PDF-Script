import os
import json
import time
import hashlib
import requests
import pandas as pd
import threading
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import tiktoken
    import tiktoken_ext
    from tiktoken_ext import openai_public
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

try:
    from debug_logger import get_debug_logger
    _debug = get_debug_logger()
except ImportError:
    class SimpleDebug:
        def is_enabled(self): return False
        def log_translation_start(self, *args): pass
        def log_translation_chunk(self, *args): pass
        def log_translation_result(self, *args): pass
        def log_translation_progress(self, *args): pass
        def log_translation_complete(self, *args): pass
        def log_error(self, *args): pass
        def log_api_request(self, *args): pass
        def log_api_response(self, *args): pass
        def log_api_error(self, *args): pass
        def log_info(self, *args): pass
        def log_warning(self, *args): pass
    _debug = SimpleDebug()

from config import (
    API_PROVIDERS,
    TRANSLATION_CONFIG,
    DEFAULT_PROVIDER_ORDER,
)

from prompt_template import (
    TRANSLATION_PROMPT,
    TRANSLATION_PROMPT_WITH_GLOSSARY,
    TRANSLATION_PROMPT_NO_GLOSSARY,
    CONTEXT_WITH_BOTH,
    CONTEXT_PREV_ONLY,
    CONTEXT_NEXT_ONLY,
    CONTEXT_NONE,
)

from response_checker import ResponseChecker


class RequestLimiter:
    def __init__(self, max_requests_per_second=5):
        self.max_requests_per_second = max_requests_per_second
        self.request_times = []
        self.lock = threading.Lock()
    
    def wait(self):
        """等待直到可以发送下一个请求"""
        with self.lock:
            current_time = time.time()
            # 移除1秒前的请求记录
            self.request_times = [t for t in self.request_times if current_time - t < 1]
            
            # 如果请求数超过限制，等待
            if len(self.request_times) >= self.max_requests_per_second:
                wait_time = 1 - (current_time - self.request_times[0])
                if wait_time > 0:
                    time.sleep(wait_time)
            
            # 添加当前请求时间
            self.request_times.append(time.time())

class TranslationCache:
    def __init__(self, cache_dir="translation_cache"):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "translation_cache.json")
        self.lock = threading.Lock()
        os.makedirs(cache_dir, exist_ok=True)
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _get_cache_key(self, text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get(self, text):
        key = self._get_cache_key(text)
        with self.lock:
            return self.cache.get(key)

    def set(self, text, translation):
        key = self._get_cache_key(text)
        with self.lock:
            self.cache[key] = {
                "original": text,
                "translation": translation,
                "timestamp": time.time()
            }
            self._save_cache()

    def clear(self):
        with self.lock:
            self.cache = {}
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)

    def get_stats(self):
        return {
            "total_entries": len(self.cache),
            "cache_file": self.cache_file
        }


class CheckpointManager:
    def __init__(self, checkpoint_dir="checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

    def _get_checkpoint_path(self, task_id):
        return os.path.join(self.checkpoint_dir, f"checkpoint_{task_id}.json")

    def save_checkpoint(self, task_id, state):
        checkpoint_path = self._get_checkpoint_path(task_id)
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_checkpoint(self, task_id):
        checkpoint_path = self._get_checkpoint_path(task_id)
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def checkpoint_exists(self, task_id):
        return os.path.exists(self._get_checkpoint_path(task_id))

    def delete_checkpoint(self, task_id):
        checkpoint_path = self._get_checkpoint_path(task_id)
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)

    def list_checkpoints(self):
        checkpoints = []
        for filename in os.listdir(self.checkpoint_dir):
            if filename.startswith("checkpoint_") and filename.endswith(".json"):
                task_id = filename[11:-5]
                checkpoints.append(task_id)
        return checkpoints


class GlossaryManager:
    def __init__(self, glossary_file):
        self.glossary_file = glossary_file
        self.glossary = {}
        self.load_glossary()

    def load_glossary(self):
        if not os.path.exists(self.glossary_file):
            print(f"词汇表文件不存在: {self.glossary_file}")
            return
        try:
            df = pd.read_excel(self.glossary_file)
            columns = df.columns.tolist()
            
            jp_col = None
            cn_col = None
            info_col = None
            for col in columns:
                col_lower = col.lower().strip()
                if '原文' in col or 'jp' in col_lower or 'japanese' in col_lower:
                    jp_col = col
                if '中文' in col or 'cn' in col_lower or 'chinese' in col_lower or '翻译' in col:
                    cn_col = col
                if '备注' in col or 'info' in col_lower:
                    info_col = col
            
            if jp_col is None:
                jp_col = columns[0]
            if cn_col is None and len(columns) > 1:
                cn_col = columns[1]
            
            for _, row in df.iterrows():
                jp_term = str(row[jp_col]).strip() if jp_col and pd.notna(row[jp_col]) else ""
                cn_term = str(row[cn_col]).strip() if cn_col and pd.notna(row[cn_col]) else ""
                info = str(row[info_col]).strip() if info_col and pd.notna(row[info_col]) else ""
                if jp_term and cn_term and jp_term != "nan":
                    self.glossary[jp_term] = {"translation": cn_term, "info": info}
        except Exception as e:
            print(f"加载词汇表时发生错误: {str(e)}")

    def get_glossary_text(self):
        lines = []
        for jp, data in self.glossary.items():
            lines.append(f"{jp} = {data['translation']}")
        return "\n".join(lines)

    def get_filtered_glossary_text(self, text):
        if not text or not self.glossary:
            return ""
        matched = []
        seen = set()
        
        for jp, data in self.glossary.items():
            if jp in text and jp not in seen:
                info = data['info'] if data['info'] else " "
                matched.append(f"{jp}|{data['translation']}|{info}")
                seen.add(jp)
        
        if matched:
            result = "\n###术语表\n原文|译文|备注\n"
            result += "\n".join(matched)
            return result
        return ""

    def apply_glossary(self, text):
        # 按长度排序，优先替换长术语
        sorted_terms = sorted(self.glossary.items(), key=lambda x: len(x[0]), reverse=True)
        for jp, data in sorted_terms:
            text = text.replace(jp, data['translation'])
        return text

    def get_glossary_for_prompt(self, text, target_language="chinese_simplified"):
        """构建用于提示词的术语表，参考AiNiee的格式"""
        if not text or not self.glossary:
            return ""
        
        matched = []
        seen = set()
        
        for jp, data in self.glossary.items():
            if jp in text and jp not in seen:
                matched.append({"src": jp, "dst": data['translation'], "info": data['info']})
                seen.add(jp)
        
        if not matched:
            return ""
        
        if target_language in ("chinese_simplified", "chinese_traditional"):
            glossary_prompt = "\n###术语表\n原文|译文|备注\n"
        else:
            glossary_prompt = "\n###Glossary\nOriginal Text|Translation|Remarks\n"
        
        for item in matched:
            info = item["info"] if item["info"] else " "
            glossary_prompt += f"{item['src']}|{item['dst']}|{info}\n"
        
        return glossary_prompt


class TranslationAPI:
    def __init__(self, provider_config):
        self.provider_config = provider_config
        self.provider_name = provider_config.get("name", provider_config.get("provider_name", "Unknown"))
        self.provider_type = provider_config.get("provider_type", "local")
        self.api_base_url = provider_config.get("api_base_url", "")
        self.api_key = provider_config.get("api_key", "")
        self.model = provider_config.get("model", "gpt-3.5-turbo")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)

    def estimate_tokens(self, text):
        """计算文本的token数，参考AiNiee的实现"""
        # 空文本返回 0
        if not text:
            return 0

        try:
            # 尝试使用 tiktoken 精确计算
            if TIKTOKEN_AVAILABLE:
                encoding = tiktoken.get_encoding("o200k_base")
                return len(encoding.encode(text))

        except Exception:
            pass

        # tiktoken 不可用，使用降级估算方法
        ascii_count = sum(1 for c in text if ord(c) < 128)
        non_ascii_count = len(text) - ascii_count

        # 英文约 4 字符/token，中文约 1.5 字符/token
        estimated_tokens = int(ascii_count / 4 + non_ascii_count / 1.5)

        # 至少返回 1（如果文本非空）
        return max(1, estimated_tokens)

    def translate(self, prompt):
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        if self.provider_type == "local" or "ollama" in self.provider_name.lower():
            return self._translate_ollama(prompt)
        elif "anthropic" in self.provider_name.lower() or "claude" in self.provider_name.lower():
            return self._translate_anthropic(prompt)
        else:
            return self._translate_openai_compatible(prompt)

    def _translate_ollama(self, prompt):
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
        }
        url = f"{self.api_base_url}/api/chat"
        _debug.log_api_request(self.provider_name, self.model, url, prompt, headers)
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=300
            )          
            response.raise_for_status()
            result = response.json()            
            _debug.log_api_response(self.provider_name, response.status_code, json.dumps(result, ensure_ascii=False))            
            message = result.get('message', {})
            content = message.get('content', '')
            reasoning = message.get('reasoning', '')                        
            if content:
                return content
            elif reasoning:
                return reasoning
            return content
        except requests.exceptions.RequestException as e:
            _debug.log_api_error(self.provider_name, str(e), url)
            raise Exception(f"Ollama API调用失败: {str(e)}")

    def _translate_anthropic(self, prompt):
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        url = f"{self.api_base_url}/messages"
        
        _debug.log_api_request(self.provider_name, self.model, url, prompt, headers)
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            
            _debug.log_api_response(self.provider_name, response.status_code, json.dumps(result, ensure_ascii=False))
            
            return result['content'][0]['text']
        except requests.exceptions.RequestException as e:
            _debug.log_api_error(self.provider_name, str(e), url)
            raise Exception(f"Anthropic API调用失败: {str(e)}")

    def _translate_openai_compatible(self, prompt):
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        url = f"{self.api_base_url}/chat/completions"
        
        _debug.log_api_request(self.provider_name, self.model, url, prompt, headers)
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()
            
            _debug.log_api_response(self.provider_name, response.status_code, json.dumps(result, ensure_ascii=False))
            
            return result['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            _debug.log_api_error(self.provider_name, str(e), url)
            raise Exception(f"API调用失败: {str(e)}")


def extract_translation_from_tag(response_text):
    if not response_text:
        return None
    
    pattern = r'<translate_input[^>]*>(.*?)</translate_input>'
    match = re.search(pattern, response_text, re.DOTALL)
    
    if match:
        extracted = match.group(1).strip()
        # 尝试从提取出的内容中进一步提取列表格式的译文
        list_extracted = extract_translation_from_list_format(extracted)
        if list_extracted:
            return list_extracted
        return extracted
    
    return None


def extract_translation_from_list_format(response_text):
    """从列表格式的响应中提取译文，参考AiNiee的实现"""
    if not response_text:
        return None
    
    lines = response_text.strip().split('\n')
    translation_lines = []
    original_lines = []
    
    # 先提取原文行，用于后续比较序号
    for line in lines:
        line = line.strip()
        # 匹配以"-原文X："开头的行
        match = re.match(r'^-原文\d+：(.*)$', line)
        if match:
            original = match.group(1).strip()
            original_lines.append(original)
    
    # 提取译文行并处理序号
    for i, line in enumerate(lines):
        line = line.strip()
        # 匹配以"-译文X："开头的行
        match = re.match(r'^-译文\d+：(.*)$', line)
        if match:
            translation = match.group(1).strip()
            
            # 检查译文中是否包含与原文相同的序号
            if i < len(original_lines):
                original = original_lines[i]
                # 提取原文中的序号
                original_match = re.match(r'^(\d+\.)', original)
                if original_match:
                    original_number = original_match.group(1)
                    # 检查译文是否以相同的序号开头
                    if translation.startswith(original_number):
                        # 移除译文中的序号
                        translation = translation[len(original_number):].strip()
            
            translation_lines.append(translation)
    
    if translation_lines:
        return '\n'.join(translation_lines)
    
    return None


HIRAGANA_PATTERN = re.compile(r'[\u3040-\u309F]')
KATAKANA_PATTERN = re.compile(r'[\u30A0-\u30FF]')
KANJI_PATTERN = re.compile(r'[\u4e00-\u9fff]')
PUNCTUATION_PATTERN = re.compile(r'[^\w\s\u3040-\u309F\u30A0-\u30FF\u4e00-\u9fff]')


def contains_hiragana(text):
    return bool(HIRAGANA_PATTERN.search(text))


def contains_katakana(text):
    return bool(KATAKANA_PATTERN.search(text))


def contains_kana(text):
    return contains_hiragana(text) or contains_katakana(text)


def contains_kanji(text):
    return bool(KANJI_PATTERN.search(text))


def count_kana(text):
    hiragana_count = len(HIRAGANA_PATTERN.findall(text))
    katakana_count = len(KATAKANA_PATTERN.findall(text))
    return hiragana_count + katakana_count


def count_kanji(text):
    return len(KANJI_PATTERN.findall(text))


def calculate_kana_ratio(text):
    if not text:
        return 0.0
    kana_count = count_kana(text)
    return kana_count / len(text)


def is_japanese_text(text):
    if not text or not text.strip():
        return False
    
    text_clean = text.strip()
    text_len = len(text_clean)
    
    if text_len == 0:
        return False
    
    kana_count = count_kana(text)
    kanji_count = count_kanji(text)
    
    if kana_count == 0 and kanji_count == 0:
        return False
    
    kana_ratio = kana_count / text_len
    kanji_ratio = kanji_count / text_len
    
    has_significant_kana = kana_ratio >= 0.05
    has_significant_kanji = kanji_ratio >= 0.03
    
    return has_significant_kana or has_significant_kanji


def is_pure_english(text):
    if not text or not text.strip():
        return False
    
    return all((char.isalpha() and char.isascii()) or char.isspace() for char in text)

def is_only_punctuation(text):
    if not text or not text.strip():
        return False
    
    text_clean = text.strip()
    return all(not char.isalnum() and not char.isspace() for char in text_clean)

def needs_translation(text):
    if not text or not text.strip():
        return False, "empty"
    
    text_clean = text.strip()
    
    if is_pure_english(text_clean) or is_only_punctuation(text_clean):
        return False, "english_or_punctuation_only"
    
    has_kana = contains_kana(text_clean)
    has_kanji = contains_kanji(text_clean)
    
    if has_kana and has_kanji:
        return True, "japanese_kana_kanji"
    
    if has_kana and not has_kanji:
        return True, "japanese_kana_only"
    
    if has_kanji and not has_kana:
        return True, "japanese_kanji_only"
    
    english_count = sum(1 for c in text_clean if c.isascii() and c.isalpha())
    punctuation_count = len(PUNCTUATION_PATTERN.findall(text_clean))
    
    if english_count > 0 and punctuation_count > 0:
        return False, "english_punctuation_only"
    
    if english_count > 0:
        return True, "english"
    
    return False, "other"


def detect_language(text):
    if not text or not text.strip():
        return "unknown"
    
    text_clean = text.strip()
    text_len = len(text_clean)
    
    kana_count = count_kana(text_clean)
    kanji_count = count_kanji(text_clean)
    english_count = sum(1 for c in text_clean if c.isascii() and c.isalpha())
    chinese_char_count = count_kanji(text_clean)
    
    if kana_count > 0 or (chinese_char_count > 0 and kana_count > 0):
        return "japanese"
    
    if kana_count == 0 and chinese_char_count > 0 and english_count == 0:
        return "chinese"
    
    if english_count > text_len * 0.5:
        return "english"
    
    return "unknown"


def should_translate_block(text, target_language="japanese"):
    if not text or not text.strip():
        return False, "empty"
    
    needs, reason = needs_translation(text)
    
    if not needs:
        return False, reason
    
    if target_language == "japanese":
        has_kana = contains_kana(text)
        has_kanji = contains_kanji(text)
        
        if not has_kana and not has_kanji:
            return False, "no_japanese_chars"
        
        if has_kanji and not has_kana:
            return True, "japanese_kanji"
        
        if has_kana:
            return True, "japanese_kana"
    
    return True, reason


def extract_japanese_segments(text):
    if not text:
        return []
    
    japanese_pattern = re.compile(
        r'[\u3040-\u309F\u30A0-\u30FF\u4e00-\u9fff]+'
    )
    return japanese_pattern.findall(text)


class ProgressTracker:
    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.chunk_status = {}

    def update(self, chunk_id, success=True):
        with self.lock:
            self.chunk_status[chunk_id] = "completed" if success else "failed"
            if success:
                self.completed += 1
            else:
                self.failed += 1

    def get_progress(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            if self.completed > 0:
                avg_time = elapsed / (self.completed + self.failed)
                remaining = (self.total - self.completed - self.failed) * avg_time
            else:
                remaining = 0
            
            return {
                "total": self.total,
                "completed": self.completed,
                "failed": self.failed,
                "progress": (self.completed + self.failed) / self.total * 100 if self.total > 0 else 0,
                "elapsed": elapsed,
                "remaining": remaining
            }

    def print_progress(self, chunk_id=None):
        progress = self.get_progress()
        bar_width = 30
        filled = int(bar_width * progress["progress"] / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        elapsed_str = self._format_time(progress["elapsed"])
        remaining_str = self._format_time(progress["remaining"])
        
        print(f"\r[{bar}] {progress['progress']:.1f}% | "
              f"完成: {progress['completed']}/{progress['total']} | "
              f"失败: {progress['failed']} | "
              f"已用时: {elapsed_str} | 剩余: {remaining_str}", end="")

    def _format_time(self, seconds):
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            return f"{seconds/60:.1f}分钟"
        else:
            return f"{seconds/3600:.1f}小时"

    def finish(self):
        with self.lock:
            elapsed = time.time() - self.start_time
        print(f"\n翻译完成! 总用时: {self._format_time(elapsed)}")
        print(f"成功: {self.completed}, 失败: {self.failed}")


class MangaTranslator:
    def __init__(self, api_config_list, translation_config, glossary_file, 
                 max_concurrent=None, use_cache=True, checkpoint_enabled=True):
        self.providers = []
        for config in api_config_list:
            self.providers.append(TranslationAPI(config))
        
        self.glossary_manager = GlossaryManager(glossary_file)
        self.context_lines_before = translation_config.get("context_lines_before", 1)
        self.context_lines_after = translation_config.get("context_lines_after", 1)
        self.batch_size = translation_config.get("batch_size", 25)
        self.max_retries = translation_config.get("max_retries", 5)
        self.retry_delay = translation_config.get("retry_delay", 2)
        self.prompt_template = translation_config.get("manga_prompt_template", "")
        self.local_chunk_lines = translation_config.get("local_chunk_lines", 20)
        self.api_chunk_tokens = translation_config.get("api_chunk_tokens", 1024)
        
        # 从配置中读取并发设置
        config_max_concurrent = translation_config.get("max_concurrent", 3)
        self.max_concurrent = max_concurrent if max_concurrent is not None else config_max_concurrent
        max_requests_per_second = translation_config.get("max_requests_per_second", 3)
        
        self.use_cache = use_cache
        self.checkpoint_enabled = checkpoint_enabled
        
        self.cache = TranslationCache() if use_cache else None
        self.checkpoint_manager = CheckpointManager()
        self.response_checker = ResponseChecker()
        self.request_limiter = RequestLimiter(max_requests_per_second=max_requests_per_second)
        
        self.task_id = None
        self.progress_tracker = None

    def _is_local_provider(self):
        if not self.providers:
            return False
        provider_type = self.providers[0].provider_config.get("provider_type", "local")
        return provider_type == "local"

    def _set_task_id(self, task_id):
        self.task_id = task_id

    def _translate_with_provider(self, provider, prompt):
        return provider.translate(prompt)

    def _translate_with_retry(self, prompt, use_fallback=True):
        last_error = None
        for provider in self.providers:
            for retry in range(self.max_retries):
                try:
                    # 使用请求限速器
                    self.request_limiter.wait()
                    _debug.log_api_request(provider.provider_name, provider.model, provider.api_base_url, prompt, {})
                    result = self._translate_with_provider(provider, prompt)
                    _debug.log_api_response(provider.provider_name, 200, result)
                    return result, provider.provider_name
                except requests.exceptions.Timeout as e:
                    last_error = f"API请求超时: {str(e)}"
                    _debug.log_api_error(provider.provider_name, last_error, provider.api_base_url)
                    if retry < self.max_retries - 1:
                        # 指数退避策略，超时错误使用更长的延迟
                        delay = self.retry_delay * (2 ** (retry + 1))
                        _debug.log_info(f"超时错误，重试延迟: {delay}秒")
                        time.sleep(delay)
                except requests.exceptions.RequestException as e:
                    last_error = f"网络错误: {str(e)}"
                    _debug.log_api_error(provider.provider_name, last_error, provider.api_base_url)
                    if retry < self.max_retries - 1:
                        # 指数退避策略
                        delay = self.retry_delay * (2 ** retry)
                        _debug.log_info(f"重试延迟: {delay}秒")
                        time.sleep(delay)
                except Exception as e:
                    last_error = f"其他错误: {str(e)}"
                    _debug.log_api_error(provider.provider_name, last_error, provider.api_base_url)
                    if retry < self.max_retries - 1:
                        time.sleep(self.retry_delay)
        
        if use_fallback:
            _debug.log_warning("所有翻译提供商都失败，使用回退方案")
            return None, None
        raise Exception(f"所有提供商都失败: {last_error}")

    def _split_text_by_lines(self, lines, max_lines=20):
        chunks = []
        for i in range(0, len(lines), max_lines):
            chunks.append(lines[i:i + max_lines])
        return chunks
    
    def _split_text_by_tokens(self, lines, max_tokens=1024):
        """根据token数分割文本，参考AiNiee的实现"""
        chunks = []
        current_chunk = []
        current_length = 0
        
        for line in lines:
            # 计算当前行的token数
            line_tokens = self.providers[0].estimate_tokens(line)
            
            # 当一个新chunk开始时
            if not current_chunk:
                pass
            
            # 如果当前chunk满了，提交它
            if current_chunk and (current_length + line_tokens > max_tokens):
                chunks.append(current_chunk)
                # 重置，为下一个chunk做准备
                current_chunk, current_length = [], 0
            
            # 添加当前行到chunk
            current_chunk.append(line)
            current_length += line_tokens
        
        # 处理循环结束后剩余的最后一个chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    def _translate_chunk(self, chunk_lines, chunk_id, prev_context="", next_context=""):
        try:
            # 逐行检查是否需要翻译
            lines_to_translate = []
            lines_to_keep = []
            
            for i, line in enumerate(chunk_lines):
                try:
                    should_translate, skip_reason = needs_translation(line)
                    if should_translate:
                        lines_to_translate.append(line)
                    else:
                        lines_to_keep.append((i, line))
                except Exception as e:
                    _debug.log_error(f"翻译块 #{chunk_id} 行 {i} 检查失败", str(e))
                    # 出错时默认需要翻译
                    lines_to_translate.append(line)
            
            # 如果所有行都不需要翻译，直接返回原文
            if not lines_to_translate:
                _debug.log_info(f"翻译块 #{chunk_id} 所有行都不需要翻译，保持原文")
                return "\n".join(chunk_lines), "skipped", chunk_id
            
            # 构建需要翻译的文本
            current_text = "\n".join(lines_to_translate)
            
            provider_name = "unknown"
            
            if self.cache:
                try:
                    cached = self.cache.get(current_text)
                    if cached and isinstance(cached, dict) and cached.get("translation"):
                        translated_text = cached["translation"]
                    elif cached and isinstance(cached, str) and cached:
                        translated_text = cached
                    else:
                        # 缓存未命中，进行翻译
                        filtered_glossary = self.glossary_manager.get_filtered_glossary_text(current_text)
                        source_lang = detect_language(current_text)
                        
                        prompt = self._build_prompt(current_text, filtered_glossary, prev_context, next_context, source_lang)
                        
                        _debug.log_info(f"=== 翻译块 #{chunk_id} 完整提示词 ===\n{prompt}\n=== 提示词结束 ===")
                        
                        result, provider_name = self._translate_with_retry(prompt)
                        
                        if result is None:
                            _debug.log_warning(f"翻译块 #{chunk_id} 所有翻译提供商都失败，回退到原文")
                            return "\n".join(chunk_lines), "fallback", chunk_id
                        
                        extracted_result = extract_translation_from_tag(result)
                        if extracted_result:
                            translated_text = extracted_result
                            _debug.log_info(f"翻译块 #{chunk_id} 已从 <translate_input> 标签中提取翻译内容")
                        else:
                            # 尝试从列表格式中提取译文
                            list_extracted = extract_translation_from_list_format(result)
                            if list_extracted:
                                translated_text = list_extracted
                                _debug.log_info(f"翻译块 #{chunk_id} 已从列表格式中提取翻译内容")
                            else:
                                translated_text = result
                        
                        # 构建源文本字典和响应字典用于检查
                        source_lines = current_text.strip().split("\n")
                        source_text_dict = {str(i): line for i, line in enumerate(source_lines)}
                        
                        translated_lines = translated_text.strip().split("\n")
                        response_dict = {str(i): line for i, line in enumerate(translated_lines)}
                        
                        # 使用响应检查器检查翻译结果
                        check_passed, check_message = self.response_checker.check_response_content(
                            result, response_dict, source_text_dict, source_lang
                        )
                        
                        if not check_passed:
                            _debug.log_warning(f"翻译块 #{chunk_id} 响应检查失败: {check_message}")
                            # 尝试重试
                            for retry in range(3):
                                retry_result, _ = self._retry_translate(current_text, translated_text, [], filtered_glossary, retry + 1, prev_context, next_context, source_lang)
                                if retry_result:
                                    # 重新检查重试结果
                                    retry_lines = retry_result.strip().split("\n")
                                    retry_dict = {str(i): line for i, line in enumerate(retry_lines)}
                                    retry_passed, _ = self.response_checker.check_response_content(
                                        retry_result, retry_dict, source_text_dict, source_lang
                                    )
                                    if retry_passed:
                                        _debug.log_info(f"翻译块 #{chunk_id} 重试成功")
                                        translated_text = retry_result
                                        break
                        
                        # 验证翻译结果
                        validated_result, error_lines = self._validate_translation(current_text, translated_text, chunk_id)
                        
                        if error_lines:
                            _debug.log_warning(f"翻译块 #{chunk_id}", f"需要重试 {len(error_lines)} 行")
                            
                            for retry in range(3):
                                retry_result, _ = self._retry_translate(current_text, validated_result, error_lines, filtered_glossary, retry + 1, prev_context, next_context, source_lang)
                                
                                if retry_result:
                                    validated_result, retry_error_lines = self._validate_translation(current_text, retry_result, chunk_id)
                                    if not retry_error_lines:
                                        _debug.log_info(f"翻译块 #{chunk_id} 重试成功")
                                        translated_text = retry_result
                                        error_lines = []
                                        break
                                    else:
                                        error_lines = retry_error_lines
                            
                        if error_lines:
                            _debug.log_error(f"翻译块 #{chunk_id}", f"重试3次后仍有 {len(error_lines)} 行未通过验证，回退到原文")
                        
                        translated_text = validated_result
                        
                        # 输出原文→译文的匹配效果预览
                        source_lines = current_text.strip().split("\n")
                        translated_lines = translated_text.strip().split("\n")
                        _debug.log_translation_mapping(chunk_id, source_lines, translated_lines)
                        
                        if self.cache:
                            self.cache.set(current_text, translated_text)
                except Exception as e:
                    _debug.log_error(f"翻译块 #{chunk_id} 缓存处理失败", str(e))
                    # 缓存处理失败时，使用不缓存的方式继续翻译
                    provider_name = "unknown"
                    filtered_glossary = self.glossary_manager.get_filtered_glossary_text(current_text)
                    source_lang = detect_language(current_text)
                    
                    prompt = self._build_prompt(current_text, filtered_glossary, prev_context, next_context, source_lang)
                    
                    _debug.log_info(f"=== 翻译块 #{chunk_id} 完整提示词 ===\n{prompt}\n=== 提示词结束 ===")
                    
                    result, provider_name = self._translate_with_retry(prompt)
                    
                    if result is None:
                        _debug.log_warning(f"翻译块 #{chunk_id} 所有翻译提供商都失败，回退到原文")
                        return "\n".join(chunk_lines), "fallback", chunk_id
                    
                    extracted_result = extract_translation_from_tag(result)
                    if extracted_result:
                        translated_text = extracted_result
                        _debug.log_info(f"翻译块 #{chunk_id} 已从 <translate_input> 标签中提取翻译内容")
                    else:
                        # 尝试从列表格式中提取译文
                        list_extracted = extract_translation_from_list_format(result)
                        if list_extracted:
                            translated_text = list_extracted
                            _debug.log_info(f"翻译块 #{chunk_id} 已从列表格式中提取翻译内容")
                        else:
                            translated_text = result
                    
                    # 验证翻译结果
                    validated_result, error_lines = self._validate_translation(current_text, translated_text, chunk_id)
                    translated_text = validated_result
                    
                    # 输出原文→译文的匹配效果预览
                    source_lines = current_text.strip().split("\n")
                    translated_lines = translated_text.strip().split("\n")
                    _debug.log_translation_mapping(chunk_id, source_lines, translated_lines)
            else:
                # 不使用缓存，直接翻译
                try:
                    filtered_glossary = self.glossary_manager.get_filtered_glossary_text(current_text)
                    source_lang = detect_language(current_text)
                    
                    prompt = self._build_prompt(current_text, filtered_glossary, prev_context, next_context, source_lang)
                    
                    _debug.log_info(f"=== 翻译块 #{chunk_id} 完整提示词 ===\n{prompt}\n=== 提示词结束 ===")
                    
                    result, provider_name = self._translate_with_retry(prompt)
                    
                    if result is None:
                        _debug.log_warning(f"翻译块 #{chunk_id} 所有翻译提供商都失败，回退到原文")
                        return "\n".join(chunk_lines), "fallback", chunk_id
                    
                    extracted_result = extract_translation_from_tag(result)
                    if extracted_result:
                        translated_text = extracted_result
                        _debug.log_info(f"翻译块 #{chunk_id} 已从 <translate_input> 标签中提取翻译内容")
                    else:
                        translated_text = result
                    
                    # 构建源文本字典和响应字典用于检查
                    source_lines = current_text.strip().split("\n")
                    source_text_dict = {str(i): line for i, line in enumerate(source_lines)}
                    
                    translated_lines = translated_text.strip().split("\n")
                    response_dict = {str(i): line for i, line in enumerate(translated_lines)}
                    
                    # 使用响应检查器检查翻译结果
                    check_passed, check_message = self.response_checker.check_response_content(
                        result, response_dict, source_text_dict, source_lang
                    )
                    
                    if not check_passed:
                        _debug.log_warning(f"翻译块 #{chunk_id} 响应检查失败: {check_message}")
                        # 尝试重试
                        for retry in range(3):
                            retry_result, _ = self._retry_translate(current_text, translated_text, [], filtered_glossary, retry + 1, prev_context, next_context, source_lang)
                            if retry_result:
                                # 重新检查重试结果
                                retry_lines = retry_result.strip().split("\n")
                                retry_dict = {str(i): line for i, line in enumerate(retry_lines)}
                                retry_passed, _ = self.response_checker.check_response_content(
                                    retry_result, retry_dict, source_text_dict, source_lang
                                )
                                if retry_passed:
                                    _debug.log_info(f"翻译块 #{chunk_id} 重试成功")
                                    translated_text = retry_result
                                    break
                    
                    # 验证翻译结果
                    validated_result, error_lines = self._validate_translation(current_text, translated_text, chunk_id)
                    
                    if error_lines:
                        _debug.log_warning(f"翻译块 #{chunk_id}", f"需要重试 {len(error_lines)} 行")
                        
                        for retry in range(3):
                            retry_result, _ = self._retry_translate(current_text, validated_result, error_lines, filtered_glossary, retry + 1, prev_context, next_context, source_lang)
                            
                            if retry_result:
                                validated_result, retry_error_lines = self._validate_translation(current_text, retry_result, chunk_id)
                                if not retry_error_lines:
                                    _debug.log_info(f"翻译块 #{chunk_id} 重试成功")
                                    translated_text = retry_result
                                    error_lines = []
                                    break
                                else:
                                    error_lines = retry_error_lines
                        
                        if error_lines:
                            _debug.log_error(f"翻译块 #{chunk_id}", f"重试3次后仍有 {len(error_lines)} 行未通过验证，回退到原文")
                    
                    translated_text = validated_result
                    
                    # 输出原文→译文的匹配效果预览
                    source_lines = current_text.strip().split("\n")
                    translated_lines = translated_text.strip().split("\n")
                    _debug.log_translation_mapping(chunk_id, source_lines, translated_lines)
                except Exception as e:
                    _debug.log_error(f"翻译块 #{chunk_id} 翻译失败", str(e))
                    return "\n".join(chunk_lines), "error", chunk_id
            
            # 重建翻译结果，将不需要翻译的行保持原文
            try:
                translated_lines = translated_text.strip().split("\n")
                final_result = []
                translate_idx = 0
                
                for i in range(len(chunk_lines)):
                    # 检查当前行是否在需要保持原文的列表中
                    keep_line = next((line for idx, line in lines_to_keep if idx == i), None)
                    if keep_line:
                        final_result.append(keep_line)
                    else:
                        if translate_idx < len(translated_lines):
                            final_result.append(translated_lines[translate_idx].strip())
                            translate_idx += 1
                        else:
                            # 翻译结果行数不足，使用原文
                            final_result.append(chunk_lines[i])
                
                final_text = "\n".join(final_result)
                
                return final_text, provider_name, chunk_id
            except Exception as e:
                _debug.log_error(f"翻译块 #{chunk_id} 结果处理失败", str(e))
                return "\n".join(chunk_lines), "error", chunk_id
        except Exception as e:
            _debug.log_error(f"翻译块 #{chunk_id} 处理失败", str(e))
            return "\n".join(chunk_lines), "error", chunk_id

    def _build_source_text(self, source_text):
        """构建带有序号的原文文本，参考AiNiee的实现"""
        lines = source_text.strip().split("\n")
        numbered_lines = []
        
        for index, line in enumerate(lines):
            # 检查是否为多行文本
            if "\n" in line:
                sub_lines = line.split("\n")
                numbered_text = f"{index + 1}.[\n"
                total_lines = len(sub_lines)
                for sub_index, sub_line in enumerate(sub_lines):
                    # 仅当只有一个尾随空格时才去除
                    sub_line = sub_line[:-1] if re.match(r'.*[^ ] $', sub_line) else sub_line
                    numbered_text += f'"{index + 1}.{total_lines - sub_index}.,{sub_line}",\n'
                numbered_text = numbered_text.rstrip('\n')
                numbered_text = numbered_text.rstrip(',')
                numbered_text += f"\n]"
                numbered_lines.append(numbered_text)
            else:
                # 单行文本直接添加序号
                numbered_lines.append(f"{index + 1}.{line}")
        
        return "\n".join(numbered_lines)

    def _build_translation_sample(self, current_text, source_lang="japanese"):
        """构建动态翻译示例，参考AiNiee的实现"""
        lines = current_text.strip().split("\n")
        source_list, translated_list = [], []
        
        # 定义不同语言的示例文本
        text_examples = {
            "japanese": "例示テキスト",
            "chinese_simplified": "示例文本",
            "chinese_traditional": "翻譯示例文本",
            "english": "Sample Text"
        }
        
        # 生成动态示例
        counter = 1
        for line in lines[:2]:  # 最多生成2个示例
            if line.strip():
                # 简单替换生成示例
                source_example = line.replace(line.strip(), f"{text_examples.get(source_lang, '示例文本')}{counter}")
                translated_example = line.replace(line.strip(), f"示例译文{counter}")
                source_list.append(source_example)
                translated_list.append(translated_example)
                counter += 1
        
        # 如果没有足够的示例，使用默认示例
        if not source_list:
            source_list = ["こんにちは", "ありがとう", "さようなら"]
            translated_list = ["你好", "谢谢", "再见"]
        
        # 构建示例文本
        sample_text = "\n###翻译示例\n"
        for i, (original, translated) in enumerate(zip(source_list, translated_list), 1):
            sample_text += f"  -原文{i}：{original}\n  -译文{i}：{translated}\n"
        
        return sample_text

    def _build_prompt(self, current_text, filtered_glossary, prev_context, next_context, source_lang="japanese"):
        from prompt_template import SYSTEM_PROMPT
        
        has_glossary = bool(filtered_glossary.strip())
        has_prev = bool(prev_context.strip())
        has_next = bool(next_context.strip())
        
        # 构建带有序号的文本
        current_text = self._build_source_text(current_text)
        
        # 构建带有序号的上下文
        if prev_context:
            prev_context = self._build_source_text(prev_context)
        if next_context:
            next_context = self._build_source_text(next_context)
        
        # 构建上下文部分
        if has_prev and has_next:
            context_section = f"###上文内容\n<previous>\n{prev_context}\n</previous>\n\n###待翻译文本\n<textarea>\n{current_text}\n</textarea>\n\n###后文内容\n<next>\n{next_context}\n</next>"
        elif has_prev:
            context_section = f"###上文内容\n<previous>\n{prev_context}\n</previous>\n\n###待翻译文本\n<textarea>\n{current_text}\n</textarea>"
        elif has_next:
            context_section = f"###待翻译文本\n<textarea>\n{current_text}\n</textarea>\n\n###后文内容\n<next>\n{next_context}\n</next>"
        else:
            context_section = f"###待翻译文本\n<textarea>\n{current_text}\n</textarea>"
        
        # 构建动态翻译示例
        translation_sample = self._build_translation_sample(current_text, source_lang)
        
        # 构建完整的提示词
        prompt = f"{SYSTEM_PROMPT}"
        
        # 添加术语表
        if has_glossary:
            prompt += f"\n{filtered_glossary}"
        
        # 添加上下文
        prompt += f"\n{context_section}"
        
        # 添加翻译示例
        prompt += f"{translation_sample}"
        
        # 添加输出要求
        prompt += "\n###输出要求（非常重要 - 必须严格遵守）\n"
        prompt += "1. 标签格式：翻译内容必须放在 <translate_input> 和 </translate_input> 之间\n"
        prompt += "2. 保持原文的换行格式，每行对应一行\n"
        prompt += "3. 禁止在标签外添加任何内容，包括解释、注释或装饰符号\n"
        prompt += "4. 确保每行都有正确的序号前缀\n"
        
        # 添加预输入回复前缀
        prompt += "\n我完全理解了翻译的要求与原则，我将遵循您的指示进行翻译，以下是对原文的翻译："
        
        return prompt

    def _retry_translate(self, original_text, translated_text, error_lines, filtered_glossary, retry_count, prev_context="", next_context="", source_lang="japanese"):
        original_lines = original_text.strip().split("\n")
        
        retry_prompt = self._build_prompt(original_text, filtered_glossary, prev_context, next_context, source_lang)
        
        retry_prompt = retry_prompt.replace("上次翻译行数不匹配", f"上次翻译行数不匹配，这是第{retry_count}次重试")
        
        _debug.log_info(f"=== 翻译块重试 #{retry_count}（重新翻译整个块)===\n{retry_prompt}\n=== 重试提示词结束 ===")
        
        result, provider_name = self._translate_with_retry(retry_prompt)
        
        if result is None:
            return None, None
        
        extracted_result = extract_translation_from_tag(result)
        if extracted_result:
            result = extracted_result
        else:
            # 尝试从列表格式中提取译文
            list_extracted = extract_translation_from_list_format(result)
            if list_extracted:
                result = list_extracted
        
        return result, provider_name

    def _validate_translation(self, original_text, translated_text, chunk_id):
        original_lines = original_text.strip().split("\n")
        translated_lines = translated_text.strip().split("\n")
        original_line_count = len(original_lines)
        translated_line_count = len(translated_lines)
        
        error_lines = []
        
        # 检查行数是否一致
        if original_line_count != translated_line_count:
            _debug.log_warning(f"翻译块 #{chunk_id}", 
                f"行数不匹配: 原文 {original_line_count} 行, 翻译 {translated_line_count} 行")
            
            if translated_line_count < original_line_count:
                for i in range(translated_line_count, original_line_count):
                    error_lines.append(i)
            else:
                error_lines = list(range(original_line_count))
        else:
            for i, (orig, trans) in enumerate(zip(original_lines, translated_lines)):
                # 检查是否返回了原文
                if orig.strip() == trans.strip():
                    _debug.log_warning(f"翻译块 #{chunk_id} 第 {i} 行", "译文与原文完全相同")
                    error_lines.append(i)
                    continue
                
                # 检查特殊符号是否匹配
                import re
                orig_special = set(re.findall(r'[【】《》「」『』（）\[\]{}<>""\'\']', orig))
                trans_special = set(re.findall(r'[【】《》「」『』（）\[\]{}<>""\'\']', trans))
                if trans_special != orig_special:
                    _debug.log_warning(f"翻译块 #{chunk_id} 第 {i} 行", "特殊符号不匹配")
                    error_lines.append(i)
                    continue
                
                # 检查是否包含残留的原文
                orig_clean = re.sub(r'[【】《》「」『』（）\[\]{}<>""\'\'\s]', '', orig)
                trans_clean = re.sub(r'[【】《》「」『』（）\[\]{}<>""\'\'\s]', '', trans)
                if orig_clean and orig_clean in trans_clean:
                    _debug.log_warning(f"翻译块 #{chunk_id} 第 {i} 行", "译文中残留原文")
                    error_lines.append(i)
        
        if error_lines:
            _debug.log_warning(f"翻译块 #{chunk_id}", f"错误行号: {error_lines}")
        
        return translated_text, error_lines

    def translate_text(self, extracted_blocks, resume=False):
        if not extracted_blocks:
            return []

        if not self.task_id:
            self.task_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        
        if resume and self.checkpoint_manager.checkpoint_exists(self.task_id):
            print(f"发现断点文件，正在恢复翻译任务: {self.task_id}")
            checkpoint = self.checkpoint_manager.load_checkpoint(self.task_id)
            if checkpoint:
                translated_blocks = checkpoint.get("translated_blocks", [])
                start_index = checkpoint.get("completed_chunks", 0) * self.batch_size
                extracted_blocks = extracted_blocks[start_index:]
                print(f"已恢复 {len(translated_blocks)} 条翻译记录")
            else:
                translated_blocks = []
        else:
            if self.checkpoint_enabled:
                self.checkpoint_manager.delete_checkpoint(self.task_id)
            translated_blocks = []
        
        lines = [block["text"] for block in extracted_blocks]
        
        # 根据模型类型选择分割方式
        if self._is_local_provider():
            chunks = self._split_text_by_lines(lines, max_lines=self.local_chunk_lines)
            print(f"开始翻译，共 {len(chunks)} 个翻译单元（每单元 {self.local_chunk_lines} 行）")
        else:
            chunks = self._split_text_by_tokens(lines, max_tokens=self.api_chunk_tokens)
            print(f"开始翻译，共 {len(chunks)} 个翻译单元（每单元最大 {self.api_chunk_tokens} tokens）")
        
        self.progress_tracker = ProgressTracker(len(chunks))
        
        _debug.log_translation_start(len(extracted_blocks))
        print(f"并行任务数: {self.max_concurrent}")
        print("-" * 60)
        
        def process_chunk(args):
            chunk_lines, chunk_id, prev_lines, next_lines = args
            prev_context = "\n".join(prev_lines) if prev_lines else ""
            next_context = "\n".join(next_lines) if next_lines else ""
            
            try:
                _debug.log_translation_chunk(chunk_id, "\n".join(chunk_lines))
                translated_text, source, cid = self._translate_chunk(
                    chunk_lines, chunk_id, prev_context, next_context
                )
                _debug.log_translation_result(chunk_id, source, source != "fallback")
                self.progress_tracker.update(chunk_id, success=(source not in ["fallback", "error"]))
                return chunk_lines, translated_text, source
            except Exception as e:
                _debug.log_error(f"翻译块 #{chunk_id}", str(e))
                self.progress_tracker.update(chunk_id, success=False)
                return chunk_lines, "\n".join(chunk_lines), "error"
        
        chunk_args = []
        for i, chunk in enumerate(chunks):
            prev_lines = chunks[i-1][-self.context_lines_before:] if i > 0 else []
            next_lines = chunks[i+1][:self.context_lines_after] if i < len(chunks) - 1 else []
            chunk_args.append((chunk, i, prev_lines, next_lines))
        
        # 存储每个chunk的结果，包括原始索引
        chunk_results = []
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 为每个chunk保存原始索引
            futures = {executor.submit(process_chunk, arg): (i, arg) for i, arg in enumerate(chunk_args)}
            
            for future in as_completed(futures):
                chunk_idx, arg = futures[future]
                chunk_lines, translated_text, source = future.result()
                chunk_results.append((chunk_idx, chunk_lines, translated_text, source))
                self.progress_tracker.print_progress()
        
        # 按照原始顺序处理结果
        chunk_results.sort(key=lambda x: x[0])
        
        for chunk_idx, chunk_lines, translated_text, source in chunk_results:
            if isinstance(translated_text, dict):
                translated_text = str(translated_text)
            
            if not translated_text or not translated_text.strip():
                translated_text = "\n".join(chunk_lines)
            
            translated_lines = translated_text.strip().split("\n") if translated_text else chunk_lines
            
            # 计算当前chunk在原始extracted_blocks中的起始索引
            original_start = 0
            for i in range(chunk_idx):
                original_start += len(chunk_args[i][0])
            
            for j, line in enumerate(chunk_lines):
                if j < len(translated_lines) and original_start + j < len(extracted_blocks):
                    block_idx = extracted_blocks[original_start + j]
                    translated_block = block_idx.copy()
                    translated_block["translation"] = translated_lines[j].strip()
                    translated_blocks.append(translated_block)
            
            if self.checkpoint_enabled and len(translated_blocks) % (self.batch_size * 2) == 0:
                checkpoint_state = {
                    "task_id": self.task_id,
                    "translated_blocks": translated_blocks,
                    "completed_chunks": len(translated_blocks) // self.batch_size,
                    "timestamp": time.time()
                }
                self.checkpoint_manager.save_checkpoint(self.task_id, checkpoint_state)
        
        self.progress_tracker.finish()
        
        if self.checkpoint_enabled:
            self.checkpoint_manager.delete_checkpoint(self.task_id)
        
        return translated_blocks

    def translate_simple(self, text_lines):
        if not text_lines:
            return []

        # 根据模型类型选择分割方式
        if self._is_local_provider():
            chunks = self._split_text_by_lines(text_lines, max_lines=self.local_chunk_lines)
            print(f"开始翻译，共 {len(chunks)} 个翻译单元（每单元 {self.local_chunk_lines} 行）")
        else:
            chunks = self._split_text_by_tokens(text_lines, max_tokens=self.api_chunk_tokens)
            print(f"开始翻译，共 {len(chunks)} 个翻译单元（每单元最大 {self.api_chunk_tokens} tokens）")
        
        self.progress_tracker = ProgressTracker(len(chunks))
        
        translated_chunks = []
        
        def process_chunk(args):
            chunk_lines, chunk_id, prev_lines, next_lines = args
            prev_context = "\n".join(prev_lines) if prev_lines else ""
            next_context = "\n".join(next_lines) if next_lines else ""
            
            try:
                result, source, cid = self._translate_chunk(
                    chunk_lines, chunk_id, prev_context, next_context
                )
                self.progress_tracker.update(chunk_id, success=(source not in ["fallback", "error"]))
                return result.split("\n") if result else chunk_lines
            except Exception:
                self.progress_tracker.update(chunk_id, success=False)
                return chunk_lines
        
        chunk_args = []
        for i, chunk in enumerate(chunks):
            prev_lines = chunks[i-1][-self.context_lines_before:] if i > 0 else []
            next_lines = chunks[i+1][:self.context_lines_after] if i < len(chunks) - 1 else []
            chunk_args.append((chunk, i, prev_lines, next_lines))
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {executor.submit(process_chunk, arg): arg for arg in chunk_args}
            
            for future in as_completed(futures):
                result_lines = future.result()
                translated_chunks.extend(result_lines)
                self.progress_tracker.print_progress()
        
        self.progress_tracker.finish()
        
        return translated_chunks

    def get_cache_stats(self):
        if self.cache:
            return self.cache.get_stats()
        return {"total_entries": 0, "cache_file": None}

    def clear_cache(self):
        if self.cache:
            self.cache.clear()
            print("翻译缓存已清除")

    def list_resumable_tasks(self):
        return self.checkpoint_manager.list_checkpoints()
