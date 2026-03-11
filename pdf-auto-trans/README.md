# Manga PDF Translator

日本漫画PDF自动翻译系统

## 功能特点

- 从PDF中提取日文漫画文本（对话气泡、旁白等）
- 集成多个大模型API供应商（DeepSeek、Ollama、OpenAI、Claude等）
- 术语表功能，支持多种表头格式
- 翻译失败后自动尝试下一个供应商
- 生成带注释的PDF和LabelPlus格式的txt文件

## 系统架构

```
pdf-auto-trans-cli/
├── api_providers.py       # API供应商配置
├── config.py              # 主配置文件
├── prompt_template.py     # 翻译提示词模板
├── text_extractor.py      # 文本提取模块
├── translator.py          # 翻译处理模块
├── pdf_annotator.py      # PDF注释生成模块
├── server.py              # API服务器
├── main.py                # 命令行入口
└── output/                # 输出文件夹
```

## 安装依赖

```bash
pip install -r ../requirements.txt
```

## 快速开始

### 1. 配置API供应商

编辑 `api_providers.py`，启用至少一个API供应商：

```python
API_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "api_base_url": "https://api.deepseek.com",
        "api_key": "your-api-key",
        "model": "deepseek-chat",
        "enabled": True,
    },
    "ollama": {
        "name": "Ollama (本地)",
        "api_base_url": "http://localhost:11434",
        "api_key": "ollama",
        "model": "huihui_ai/qwen3.5-abliterated:9B",
        "enabled": True,
    },
}
```

支持的供应商：DeepSeek、Ollama、OpenAI、Claude、Azure OpenAI

### 2. 命令行运行

```bash
cd pdf-auto-trans-cli

# 基本用法
python main.py "<漫画文件夹>"

# 指定术语表
python main.py "<漫画文件夹>" -g "术语表.xlsx"

# 指定输出文件夹
python main.py "<漫画文件夹>" -o "output"

# 不生成原文注释PDF
python main.py "<漫画文件夹>" --no-original
```

### 3. API服务器运行

```bash
# 启动服务器（默认端口8078）
python server.py
```

## 命令行参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `input` | 位置参数 | 输入PDF文件夹路径 |
| `--output` | `-o` | 输出文件夹路径 |
| `--glossary` | `-g` | 术语表文件路径 |
| `--filename` | `-f` | 输出文件名 |
| `--no-original` | | 不生成原文注释PDF |
| `--no-txt` | | 不生成txt文件 |

## API接口

### 健康检查

```http
GET http://localhost:8078/health
```

### 翻译PDF

```http
POST http://localhost:8078/api/process
Content-Type: application/json

{
  "input_folder": "<漫画文件夹>",
  "output_folder": "output",
  "output_filename": "translated_manga"
}
```

### 简单文本翻译

```http
POST http://localhost:8078/api/translate/simple
Content-Type: application/json

{
  "text": ["今日から俺は", "この街で生き延びる"]
}
```

## 术语表格式

Excel文件，支持多种表头：

| 原文 | 中文 |
|------|------|
| 間取り図 | 平面图 |
| 不動産屋 | 房产中介 |

自动识别表头关键词：原文/jp/japanese、中文/cn/chinese/翻译

## 输出文件

- `translated_manga.pdf` - 带翻译注释的PDF
- `translated_manga_original.pdf` - 带原文注释的PDF
- `translated_manga_annotations.txt` - LabelPlus格式注释

## 故障排除

### API供应商失败
- 检查网络连接
- 确认API密钥正确
- 尝试其他供应商

### Ollama连接失败
1. 安装Ollama：https://ollama.ai
2. 下载模型：`ollama pull huihui_ai/qwen3.5-abliterated:9B`
3. 启动Ollama服务

## 许可证

GPL License © [几千块](https://github.com/jqk4388)
