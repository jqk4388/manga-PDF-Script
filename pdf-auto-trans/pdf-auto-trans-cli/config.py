import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from api_providers import API_PROVIDERS

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(BASE_DIR), "config.json")

# 默认配置
DEFAULT_CONFIG = {
    # 翻译配置
    "translation": {
        "context_lines_before": 2,
        "context_lines_after": 2,
        "batch_size": 25,
        "max_retries": 5,
        "retry_delay": 2,
        "manga_prompt_template": "翻译为中文：{current_text}",
        "local_chunk_lines": 5,
        "api_chunk_tokens": 200,
        "max_concurrent": 3,  # 最大并发数
        "max_requests_per_second": 3,  # 每秒最大请求数
        "response_check": {
            "enabled": True,
            "check_empty_response": True,
            "check_line_count": True,
            "check_dict_order": True,
            "check_multiline_text": True,
            "check_return_to_original": True,
            "check_residual_original": True,
            "check_reply_format": True,
            "check_placeholders": True
        }
    },
    
    # PDF配置
    "pdf": {
        "rubi_size": 6.5,
        "x_position_threshold": 1.92,
        "y_position_threshold": 2.35,
        "include_font_info": False,
        "font_scale": 1.0,
        "filter_color": False,
        "filter_adv": False,
        "generate_original_annot_pdf": True,
        "generate_translated_annot_pdf": True,
        "generate_annot_txt": True,
    },
    
    # 服务器配置
    "server": {
        "host": "0.0.0.0",
        "port": 8078,
    },
    
    # 文件夹配置
    "folders": {
        "input_pdf": os.path.join(os.path.dirname(BASE_DIR), "漫画"),
        "output": os.path.join(os.path.dirname(BASE_DIR), "output"),
        "glossary": os.path.join(os.path.dirname(BASE_DIR), "词汇表.xlsx")
    },
    
    # OCR配置
    "ocr": {
        "enabled": True,
        "provider": "ollama",
        "ollama": {
            "api_base_url": "http://localhost:11434",
            "model": "glm-ocr"
        },
        "api": {
            "api_url": "",
            "api_key": "",
            "model": ""
        }
    },
    
    # 提供商配置
    "providers": {
        "default_order": ["ollama", "deepseek", "openai", "doubao", "anthropic", "azure_openai"]
    }
}

# 加载用户配置
def load_config():
    """加载配置文件，如果不存在则使用默认配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # 合并默认配置和用户配置
                return merge_configs(DEFAULT_CONFIG, user_config)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

# 合并配置
def merge_configs(default, user):
    """递归合并配置字典"""
    if not isinstance(user, dict):
        return default
    
    result = default.copy()
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result

# 保存配置
def save_config(config):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {str(e)}")
        return False

# 加载配置
CONFIG = load_config()

# 导出配置变量
TRANSLATION_CONFIG = CONFIG["translation"]
PDF_CONFIG = CONFIG["pdf"]
SERVER_CONFIG = CONFIG["server"]
OCR_CONFIG = CONFIG["ocr"]

INPUT_PDF_FOLDER = CONFIG["folders"]["input_pdf"]
OUTPUT_FOLDER = CONFIG["folders"]["output"]
GLOSSARY_FILE = CONFIG["folders"]["glossary"]

DEFAULT_PROVIDER_ORDER = CONFIG["providers"]["default_order"]

# 确保文件夹存在
os.makedirs(INPUT_PDF_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def get_all_provider_names():
    return list(API_PROVIDERS.keys())

def get_enabled_providers():
    enabled = []
    for provider_name in get_all_provider_names():
        if provider_name in API_PROVIDERS:
            provider = API_PROVIDERS[provider_name]
            if provider.get("enabled", False) and provider.get("api_key"):
                enabled.append(provider_name)
    return enabled

def get_enabled_providers_in_order():
    enabled_set = set(get_enabled_providers())
    result = []
    for provider_name in DEFAULT_PROVIDER_ORDER:
        if provider_name in enabled_set:
            result.append(provider_name)
    for provider_name in get_all_provider_names():
        if provider_name not in result and provider_name in enabled_set:
            result.append(provider_name)
    return result

def get_provider_config(provider_name):
    if provider_name in API_PROVIDERS:
        return API_PROVIDERS[provider_name].copy()
    return None

def get_config(key, default=None):
    """获取配置值"""
    keys = key.split('.')
    value = CONFIG
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    return value

def set_config(key, value):
    """设置配置值"""
    keys = key.split('.')
    config = CONFIG
    for k in keys[:-1]:
        if k not in config:
            config[k] = {}
        config = config[k]
    config[keys[-1]] = value
    return save_config(CONFIG)
