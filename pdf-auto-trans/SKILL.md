---
name: "pdf-auto-trans"
description: "Japanese manga PDF auto-translation tool. Invoke when user wants to translate manga PDFs, extract Japanese text, or generate annotated PDFs with translations."
---

# Manga PDF Translator 使用指南
日本漫画PDF自动翻译系统，可从漫画PDF中提取日文文本，调用大模型API进行翻译，生成带注释的PDF和LabelPlus格式的txt文稿。

## 使用前配置

**使用前请先确认漫画文件夹位置、术语表路径、API密钥填写状态等信息。**

### 步骤1：配置API供应商

编辑 `pdf-auto-trans-cli/api_providers.py`，启用至少一个API供应商：

```python
API_PROVIDERS = {
    "ollama": {
        "name": "Ollama (本地)",
        "api_base_url": "http://localhost:11434",
        "api_key": "ollama",
        "model": "huihui_ai/qwen3.5-abliterated:9B",
        "enabled": True,
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_base_url": "https://api.deepseek.com",
        "api_key": "your-api-key",
        "model": "deepseek-chat",
        "enabled": True,
    },
}
```

支持的供应商：DeepSeek、Ollama、OpenAI、Claude、Azure OpenAI，可自定义添加其他供应商。

### 步骤2（可选）：配置术语表

术语表为Excel文件，包含两列：
- 第一列：日文术语
- 第二列：中文翻译

命令行使用：`--glossary <术语表路径>`

## 使用方法

### 命令行基本用法

```bash
cd pdf-auto-trans-cli
python main.py "漫画PDF文件夹路径"
```

### 常用选项

```bash
# 指定术语表
python main.py "文件夹" -g "术语表.xlsx"

# 指定输出文件夹
python main.py "文件夹" -o "output"

# 不生成原文注释PDF
python main.py "文件夹" --no-original

# 不生成txt文件
python main.py "文件夹" --no-txt

# 断点续译
python main.py "文件夹" --resume
```

### 命令行参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `input` | 位置参数 | 输入PDF文件夹路径 |
| `--output` | `-o` | 输出文件夹路径 |
| `--filename` | `-f` | 输出文件名 |
| `--glossary` | `-g` | 术语表路径 |
| `--no-original` | | 不生成原文注释PDF |
| `--no-txt` | | 不生成txt文件 |
| `--resume` | | 断点续译 |

## 常见问题

### Q: 提示"未启用任何API提供商"
A: 在 `api_providers.py` 中将 `enabled` 改为 `True`，并填写API密钥。

### Q: 翻译失败怎么办
A: 系统会自动重试5次，若所有供应商都失败会使用原文。检查API密钥和网络连接。

### Q: 如何使用本地Ollama
1. 安装Ollama：https://ollama.ai
2. 下载模型：`ollama pull huihui_ai/qwen3.5-abliterated:9B`
3. 启动Ollama服务后启用配置

## 输出文件

- `translated_manga.pdf` - 带翻译注释的PDF
- `translated_manga_original.pdf` - 带原文注释的PDF
- `translated_manga_annotations.txt` - LabelPlus格式注释文件
