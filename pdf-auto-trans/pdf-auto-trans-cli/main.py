import os
import sys
import argparse
import tempfile

from config import (
    API_PROVIDERS,
    TRANSLATION_CONFIG,
    PDF_CONFIG,
    GLOSSARY_FILE,
    INPUT_PDF_FOLDER,
    OUTPUT_FOLDER,
    SERVER_CONFIG,
    DEFAULT_PROVIDER_ORDER,
    get_enabled_providers_in_order,
    OCR_CONFIG,
)
from prompt_template import TRANSLATION_PROMPT
from text_extractor import TextExtractor
from translator import MangaTranslator
from pdf_annotator import PDFAnnotator
from pdf_processor import PDFProcessor, OCRProcessor


def process_manga(
    input_folder=None,
    output_folder=None,
    api_config_list=None,
    translation_config=None,
    pdf_config=None,
    glossary_file=None,
    base_filename="translated_manga",
    filename_suffix="_translated",
    max_concurrent=5,
    use_cache=True,
    resume=False,
    clear_cache=False,
    list_checkpoints=False,
    use_ocr=False,
    ocr_config=None
):
    if input_folder is None:
        input_folder = INPUT_PDF_FOLDER
    if output_folder is None:
        output_folder = OUTPUT_FOLDER
    if translation_config is None:
        translation_config = TRANSLATION_CONFIG.copy()
    if pdf_config is None:
        pdf_config = PDF_CONFIG.copy()
    if glossary_file is None:
        glossary_file = GLOSSARY_FILE
    if ocr_config is None:
        ocr_config = OCR_CONFIG.copy()
    
    translation_config["manga_prompt_template"] = TRANSLATION_PROMPT

    os.makedirs(output_folder, exist_ok=True)

    print(f"=" * 60)
    print(f"Manga PDF Translator - 漫画PDF自动翻译系统")
    print(f"=" * 60)
    print(f"输入文件夹: {input_folder}")
    print(f"输出文件夹: {output_folder}")
    print(f"并行任务数: {max_concurrent}")
    print(f"启用缓存: {use_cache}")
    print(f"断点续译: {resume}")
    print(f"OCR模式: {use_ocr}")
    print(f"=" * 60)

    translator = MangaTranslator(
        api_config_list, 
        translation_config, 
        glossary_file,
        max_concurrent=max_concurrent,
        use_cache=use_cache,
        checkpoint_enabled=True
    )

    if list_checkpoints:
        checkpoints = translator.list_resumable_tasks()
        if checkpoints:
            print(f"\n可恢复的翻译任务: {checkpoints}")
        else:
            print(f"\n没有找到可恢复的翻译任务")
        return None

    if clear_cache:
        translator.clear_cache()
        print("缓存已清除")

    print(f"\n步骤1: 提取文本...")
    
    temp_merged_pdf = None
    try:
        pdf_processor = PDFProcessor()
        
        temp_dir = tempfile.mkdtemp()
        temp_merged_pdf = os.path.join(temp_dir, "merged.pdf")
        
        print("  正在合并PDF文件...")
        pdf_processor.merge_pdfs(input_folder, temp_merged_pdf)
        
        print("  正在检测PDF类型...")
        pdf_type = pdf_processor.detect_pdf_type(temp_merged_pdf)
        print(f"    - 总页数: {pdf_type['page_count']}")
        print(f"    - 文字页数: {pdf_type['text_pages']}")
        print(f"    - 空页数: {pdf_type['empty_pages']}")
        print(f"    - 是否扫描型: {pdf_type['is_scanned']}")
        
        if use_ocr or pdf_type.get('is_scanned', False):
            print("  执行OCR文字识别...")
            ocr_provider = ocr_config.get('provider', 'ollama')
            ocr_provider_config = ocr_config.get(ocr_provider, {})
            
            ocr_processor = OCRProcessor(ocr_provider, ocr_provider_config)
            extracted_blocks = ocr_processor.ocr_pdf(temp_merged_pdf)
            print(f"  OCR提取到 {len(extracted_blocks)} 个文本块")
        else:
            extractor = TextExtractor(
                rubi_size=pdf_config.get("rubi_size", 5.0),
                x_position_threshold=pdf_config.get("x_position_threshold", 0.3),
                y_position_threshold=pdf_config.get("y_position_threshold", 0.5)
            )
            extracted_blocks = extractor.extract_text_from_pdf(temp_merged_pdf)
            print(f"  提取到 {len(extracted_blocks)} 个文本块")
    finally:
        if temp_merged_pdf and os.path.exists(os.path.dirname(temp_merged_pdf)):
            import shutil
            try:
                shutil.rmtree(os.path.dirname(temp_merged_pdf))
            except:
                pass
    
    extracted_blocks = extracted_blocks if extracted_blocks else []

    if not extracted_blocks:
        print("未提取到任何文本!")
        return None

    print(f"\n步骤2: 翻译文本...")
    print("DEBUG: About to call translator.translate_text")
    translated_blocks = translator.translate_text(extracted_blocks, resume=resume)
    print(f"翻译完成 {len(translated_blocks)} 个文本块")

    cache_stats = translator.get_cache_stats()
    if cache_stats["total_entries"] > 0:
        print(f"缓存统计: {cache_stats['total_entries']} 条翻译记录")

    print(f"\n步骤3: 生成输出文件...")
    annotator = PDFAnnotator(
        rubi_size=pdf_config.get("rubi_size", 5.0),
        x_position_threshold=pdf_config.get("x_position_threshold", 0.3),
        y_position_threshold=pdf_config.get("y_position_threshold", 0.5),
        include_font_info=pdf_config.get("include_font_info", False),
        font_scale=pdf_config.get("font_scale", 1.0)
    )
    
    results = annotator.generate_all_outputs(
        input_folder,
        translated_blocks,
        output_folder,
        generate_original=pdf_config.get("generate_original_annot_pdf", True),
        generate_translated=pdf_config.get("generate_translated_annot_pdf", True),
        generate_txt=pdf_config.get("generate_annot_txt", True),
        base_filename=base_filename,
        filename_suffix=filename_suffix
    )

    print(f"\n" + "=" * 60)
    print(f"处理完成!")
    print(f"=" * 60)
    for key, path in results.items():
        print(f"  {key}: {path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Manga PDF Translator - 漫画PDF自动翻译系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s "pdf文件夹"                              # 基本翻译
  %(prog)s "pdf文件夹" -c 3                          # 使用3个并行任务
  %(prog)s "pdf文件夹" --no-cache                    # 不使用缓存
  %(prog)s "pdf文件夹" --resume                      # 断点续译
  %(prog)s --list-checkpoints                        # 列出可恢复的任务
  %(prog)s --clear-cache                             # 清除翻译缓存
        """
    )
    parser.add_argument('input', nargs='?', default=INPUT_PDF_FOLDER, 
                        help='输入PDF文件夹路径 (默认: %(default)s)')
    parser.add_argument('--output', '-o', default=None, 
                        help='输出文件夹路径')
    parser.add_argument('--glossary', '-g', default=GLOSSARY_FILE, 
                        help='词汇表文件路径')
    parser.add_argument('--filename', '-f', default='translated_manga', 
                        help='输出文件名(不含扩展名)')
    parser.add_argument('--suffix', '-s', default='_translated', 
                        help='输出文件后缀 (默认: _translated)')
    parser.add_argument('--no-original', action='store_true', 
                        help='不生成原文注释PDF')
    parser.add_argument('--no-translated', action='store_true', 
                        help='不生成翻译注释PDF')
    parser.add_argument('--no-txt', action='store_true', 
                        help='不生成注释txt文件')
    parser.add_argument('--concurrent', '-c', type=int, default=5, 
                        help='并行翻译任务数量 (默认: 5, 最大: 10)')
    parser.add_argument('--no-cache', action='store_true', 
                        help='禁用翻译缓存')
    parser.add_argument('--resume', '-r', action='store_true', 
                        help='从断点继续翻译')
    parser.add_argument('--clear-cache', action='store_true', 
                        help='清除翻译缓存')
    parser.add_argument('--list-checkpoints', action='store_true', 
                        help='列出可恢复的翻译任务')
    parser.add_argument('--ocr', action='store_true', 
                        help='强制使用OCR模式（用于扫描型PDF）')
    parser.add_argument('--no-ocr-auto', action='store_true', 
                        help='禁用自动OCR检测（即使PDF为扫描型也不OCR）')
    parser.add_argument('--debug', action='store_true', 
                        help='启用调试模式，显示详细日志')
    
    args = parser.parse_args()

    if args.debug:
        from debug_logger import get_debug_logger
        logger = get_debug_logger()
        logger.enable()
        print("调试模式已启用")
    
    max_concurrent = min(max(1, args.concurrent), 10)
    
    use_ocr = False
    if args.no_ocr_auto:
        use_ocr = False
    elif args.ocr:
        use_ocr = True
    
    enabled_providers = []
    api_providers = []
    local_providers = []
    
    provider_priority = {"api": 0, "local": 1}
    
    for provider_name in get_enabled_providers_in_order():
        if provider_name in API_PROVIDERS:
            provider = API_PROVIDERS[provider_name]
            if not provider.get("enabled", False):
                continue
            
            api_keys = provider.get("api_key", "")
            if not api_keys:
                continue
            
            if isinstance(api_keys, str):
                api_keys = [api_keys]
            
            for api_key in api_keys:
                if api_key:
                    provider_copy = provider.copy()
                    provider_copy["api_key"] = api_key
                    provider_copy["provider_name"] = provider_name
                    
                    p_type = provider.get("provider_type", "local")
                    if p_type == "local":
                        local_providers.append(provider_copy)
                    else:
                        api_providers.append(provider_copy)
    
    enabled_providers = api_providers + local_providers
    
    enabled_providers.sort(key=lambda p: provider_priority.get(p.get("provider_type", "local"), 99))
    
    for provider in enabled_providers:
        print(f"启用提供商: {provider['name']} - {provider['model']}")
    
    if not enabled_providers and not args.list_checkpoints and not args.clear_cache:
        print("错误: 未启用任何API提供商!")
        print("请在 api_providers.py 中设置 enabled=True 和 api_key")
        sys.exit(1)
    
    pdf_config = PDF_CONFIG.copy()
    if args.no_original:
        pdf_config["generate_original_annot_pdf"] = False
    if args.no_translated:
        pdf_config["generate_translated_annot_pdf"] = False
    if args.no_txt:
        pdf_config["generate_annot_txt"] = False
    
    results = process_manga(
        input_folder=args.input,
        output_folder=args.output,
        api_config_list=enabled_providers,
        glossary_file=args.glossary,
        base_filename=args.filename,
        filename_suffix=args.suffix,
        pdf_config=pdf_config,
        max_concurrent=max_concurrent,
        use_cache=not args.no_cache,
        resume=args.resume,
        clear_cache=args.clear_cache,
        list_checkpoints=args.list_checkpoints,
        use_ocr=use_ocr,
        ocr_config=OCR_CONFIG
    )


if __name__ == '__main__':
    main()
