# Manga PDF Translator MCP Server

日本漫画PDF自动翻译系统 - 支持通过API调用的MCP服务器

## 功能特点

- 从PDF中提取日文漫画文本（对话气泡、旁白等）
- 集成多个大模型API供应商（DeepSeek、Ollama、OpenAI、Claude等）
- 支持API供应商自动切换，翻译失败后自动尝试下一个
- 术语表功能，适配多种表头格式
- 上下文翻译机制，提高翻译质量
- 翻译最大重试5次（可配置），失败后退回原文
- 生成带原文注释的PDF（可配置）
- 生成带翻译注释的PDF（必须）
- 生成注释txt文件（LabelPlus格式）

## 系统架构

```
manga-PDF-Script/pdf-auto-trans-cli/
├── api_providers.py       # API供应商配置（支持多供应商切换）
├── config.py              # 主配置文件
├── prompt_template.py     # 翻译提示词模板
├── text_extractor.py     # 文本提取模块
├── translator.py         # 翻译处理模块
├── pdf_annotator.py     # PDF注释生成模块
├── annot_exporter.py     # 注释导出模块
├── server.py             # MCP服务器
├── main.py               # 命令行入口
├── *词汇表*.xlsx         # 术语表
├── output/               # 输出文件夹
└── */
    └── withJP/           # 输入PDF文件夹
```

## 安装依赖

```bash
pip install flask pdfplumber pymupdf requests pandas openpyxl
```

## 快速开始

### 1. 配置API供应商

编辑 `api_providers.py` 文件，启用所需的API供应商并填入API密钥：

```python
API_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "api_base_url": "https://api.deepseek.com",
        "api_key": "your-deepseek-api-key",  # 填入您的密钥
        "model": "deepseek-chat",
        "enabled": True,  # 设置为True启用
    },
    "ollama": {
        "name": "Ollama (本地)",
        "api_base_url": "http://localhost:11434",
        "api_key": "",
        "model": "huihui_ai/qwen3.5-abliterated:0.8B",
        "enabled": True,  # 设置为True启用
    },
    # ... 其他供应商
}
```

支持的供应商：
- **DeepSeek**: 默认优先使用
- **Ollama**: 本地小模型（默认 huihui_ai/qwen3.5-abliterated:0.8B）无限制速度快
- **OpenAI**: GPT-4/GPT-3.5
- **Anthropic Claude**: Claude 3系列
- **Azure OpenAI**: Azure部署的OpenAI服务

### 2. 命令行运行

```bash
cd pdf-auto-trans-cli

# 基本用法（只需指定PDF文件夹）
python main.py "<漫画文件夹>"

# 指定术语表
python main.py "<漫画文件夹>" -g "自定义术语表.xlsx"

# 指定输出文件夹
python main.py "<漫画文件夹>" -o "output"

# 指定输出文件名
python main.py "<漫画文件夹>" -f "my_translation"

# 不生成原文注释PDF
python main.py "<漫画文件夹>" --no-original

# 不生成翻译注释PDF
python main.py "<漫画文件夹>" --no-translated

# 不生成txt文件
python main.py "<漫画文件夹>" --no-txt
```

### 3. API服务器运行

```bash
# 启动服务器（默认端口8078）
python server.py

# 指定端口
python server.py --port 9000
```

## 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `input` | 位置参数 | 输入PDF文件夹路径 | `<漫画文件夹>` |
| `--output` | `-o` | 输出文件夹路径 | `output` |
| `--glossary` | `-g` | 词汇表文件路径 | `怪屋谜案词汇表-20260215.xlsx` |
| `--filename` | `-f` | 输出文件名(不含扩展名) | `translated_manga` |
| `--no-original` |  | 不生成原文注释PDF | 生成 |
| `--no-translated` |  | 不生成翻译注释PDF | 生成 |
| `--no-txt` |  | 不生成注释txt文件 | 生成 |

## API接口文档

### 1. 健康检查

```http
GET http://localhost:8078/health
```

### 2. 获取可用供应商列表

```http
GET http://localhost:8078/api/providers
```

### 3. 配置API服务

```http
POST http://localhost:8078/api/config
Content-Type: application/json

{
  "api_config_list": [
    {
      "name": "DeepSeek",
      "api_base_url": "https://api.deepseek.com",
      "api_key": "your-key",
      "model": "deepseek-chat"
    }
  ]
}
```

### 4. 提取文本（不翻译）

```http
POST http://localhost:8078/api/extract
Content-Type: application/json

{
  "input_folder": "<漫画文件夹>"
}
```

### 5. 翻译文本

```http
POST http://localhost:8078/api/translate
Content-Type: application/json

{
  "input_folder": "<漫画文件夹>"
}
```

### 6. 完整处理流程

```http
POST http://localhost:8078/api/process
Content-Type: application/json

{
  "input_folder": "<漫画文件夹>",
  "output_folder": "output",
  "output_filename": "translated_manga",
  "generate_original": true,
  "generate_translated": true,
  "generate_txt": true
}
```

### 7. 简单文本翻译

```http
POST http://localhost:8078/api/translate/simple
Content-Type: application/json

{
  "text": [
    "今日から俺は",
    "この街で生き延びる"
  ]
}
```

### 8. 术语表管理

```http
# 获取术语表
GET http://localhost:8078/api/glossary

# 添加术语
POST http://localhost:8078/api/glossary
Content-Type: application/json

{
  "terms": {
    "新术语": "新翻译"
  }
}
```

## 配置说明

### API供应商配置 (api_providers.py)

```python
API_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "api_base_url": "https://api.deepseek.com",
        "api_key": "",           # API密钥
        "model": "deepseek-chat",
        "max_tokens": 4096,
        "temperature": 0.7,
        "enabled": False,        # 是否启用
    },
    "ollama": {
        "name": "Ollama (本地)",
        "api_base_url": "http://localhost:11434",
        "api_key": "",
        "model": "huihui_ai/qwen3.5-abliterated:0.8B",
        "max_tokens": 4096,
        "temperature": 0.7,
        "enabled": False,
    },
}
```

### 翻译配置

```python
TRANSLATION_CONFIG = {
    "context_lines_before": 1,    # 前置上下文行数
    "context_lines_after": 1,     # 后置上下文行数
    "batch_size": 25,            # 每批翻译的行数
    "max_retries": 5,           # 最大重试次数
    "retry_delay": 2,           # 重试延迟(秒)
}
```

### PDF配置

```python
PDF_CONFIG = {
    "rubi_size": 6.5,                  # 注音假名过滤阈值
    "x_position_threshold": 1.92,        # X方向文字块阈值
    "y_position_threshold": 2.35,        # Y方向文字块阈值
    "include_font_info": False,         # 是否包含字体信息
    "font_scale": 1.0,                  # 字体缩放比例
    "generate_original_annot_pdf": True, # 生成原文注释PDF
    "generate_translated_annot_pdf": True, # 生成翻译注释PDF
    "generate_annot_txt": True,         # 生成注释txt
}
```

## 术语表格式

术语表支持多种Excel格式：

| 原文 | 中文 | 备注 |
|------|------|------|
| 間取り図 | 平面图/户型平面图/布局图 | |
| 不動産屋 | 房产中介/中介公司 | |

系统会自动识别表头关键词：
- 原文列：`原文`、`jp`、`japanese`
- 中文列：`中文`、`cn`、`chinese`、`翻译`

## 输出文件

运行完成后会在输出文件夹生成以下文件：

1. **`translated_manga.pdf`** - 带翻译注释的PDF（必须生成）
2. **`translated_manga_original.pdf`** - 带原文注释的PDF（可配置）
3. **`translated_manga_annotations.txt`** - LabelPlus格式的注释txt文件（可配置）

## 使用示例

### Python代码调用

```python
import requests

base_url = "http://localhost:8078"

# 检查服务状态
health = requests.get(f"{base_url}/health")
print(health.json())

# 执行翻译
response = requests.post(f"{base_url}/api/process", json={
    "input_folder": "<漫画文件夹>",
    "output_folder": "output",
    "output_filename": "my_translation"
})
print(response.json())
```

### cURL调用

```bash
# 完整翻译流程
curl -X POST http://localhost:8078/api/process \
  -H "Content-Type: application/json" \
  -d '{"input_folder": "<漫画文件夹>"}'
```

## 故障排除

### 所有API供应商都失败

- 检查网络连接
- 确认API密钥是否正确
- 尝试使用其他供应商

### 文本提取不完整

- 调整 `rubi_size` 参数（增大可提取更多小字）
- 调整 `x_position_threshold` 和 `y_position_threshold` 参数

### Ollama本地模型连接失败

- 确认Ollama服务已启动
- 确认模型已下载（`ollama pull huihui_ai/qwen3.5-abliterated:0.8B`）

## 许可证
翻译部分代码来自[AiNiee](https://github.com/NEKOparapa/AiNiee)
GPL License ©几千块
