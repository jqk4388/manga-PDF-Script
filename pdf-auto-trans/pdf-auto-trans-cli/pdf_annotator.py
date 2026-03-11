import pdfplumber
import pymupdf
import os
import re

try:
    from debug_logger import get_debug_logger
    _debug = get_debug_logger()
except ImportError:
    class SimpleDebug:
        def is_enabled(self): return False
        def log_annotation_start(self, *args): pass
        def log_annotation_page(self, *args): pass
        def log_annotation_added(self, *args): pass
        def log_annotation_skipped(self, *args): pass
        def log_annotation_complete(self, *args): pass
        def log_error(self, *args): pass
    _debug = SimpleDebug()

FILTER_FONTS = [
    "KentenGeneric",
    "AnitoStd",
    "NumberOnly",
    "Yanmaga-komanon",
]

FILTER_PUNCTUATION_FONTS = [
    "MNews",
    "RoHMincho"
]

FILTER_KANA_FONTS = [
    "Ryumin",
    "ATC-",
    "Antique",
]

def is_kana(char):
    c = char["text"]
    return (
        ("\u3040" <= c <= "\u309F") or
        ("\u30A0" <= c <= "\u30FF")
    )

def should_filter_kana(char, prev_char, rubi_size):
    fontname = char["fontname"]
    if any(f in fontname for f in FILTER_FONTS):
        return True
    if is_kana(char) and char["size"] < rubi_size:
        if any(x in fontname for x in FILTER_KANA_FONTS):
            return True
    if is_kana(char) and char["size"] >= rubi_size:
        if any(x in fontname for x in FILTER_KANA_FONTS):
            if prev_char and re.match(r'[\u4e00-\u9fff]', prev_char["text"]):
                dx = abs(float(char["x0"]) - float(prev_char["x0"]))
                dy = abs(float(char["top"]) - float(prev_char["top"]))
                dsize = abs(float(char["size"]) - float(prev_char["size"]))
                if dx > 1 and dy > 1 and dsize > 0.5:
                    return True
    return False

def is_new_block(prev_char, curr_char, x_position_threshold, y_position_threshold):
    prev_font = prev_char["fontname"]
    curr_font = curr_char["fontname"]
    size_threshold = 1
    font_size_diff = abs(float(curr_char["size"]) - float(prev_char["size"]))
    font_x_diff = abs(float(curr_char["x0"]) - float(prev_char["x0"]))
    font_y_diff = abs(float(curr_char["top"]) - float(prev_char["top"]))

    if prev_font == curr_font:
        if font_size_diff < size_threshold:
            if font_y_diff < font_x_diff:
                if font_y_diff > prev_char['size'] * y_position_threshold:
                    return True
            else:
                if font_x_diff > prev_char['size'] * x_position_threshold:
                    return True
        else:
            return True
    else:
        if font_size_diff < size_threshold:
            if font_x_diff > prev_char['size'] * x_position_threshold:
                return True
        else:
            if any(f in curr_font for f in FILTER_PUNCTUATION_FONTS) and font_size_diff <= float(curr_char["size"]) / 7.3:
                return False
            else:
                return True
    return False

def get_block_fontname(block_chars, first_char):
    for c in block_chars:
        if is_kana(c):
            fontname = c['fontname']
            if '+' in fontname:
                return fontname.split('+', 1)[-1]
            return fontname
    fontname = first_char['fontname']
    if '+' in fontname:
        return fontname.split('+', 1)[-1]
    return fontname


class PDFAnnotator:
    def __init__(self, rubi_size=5.0, x_position_threshold=0.3, y_position_threshold=0.5, 
                 include_font_info=False, font_scale=1.0):
        self.rubi_size = rubi_size
        self.x_position_threshold = x_position_threshold
        self.y_position_threshold = y_position_threshold
        self.include_font_info = include_font_info
        self.font_scale = font_scale

    def _get_annotation_text(self, block, use_translation=True):
        text = block.get("translation" if use_translation else "text", "")
        if self.include_font_info:
            fontname = block.get("font", "默认")
            fontsize = block.get("size", 0) * 0.708661
            text = f"{{字体：{fontname}}}{{字号：{fontsize:.1f}}}\n{text}"
        return text

    def _add_annotations_to_doc(self, doc, input_folder, blocks, use_translation=True):
        pdf_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')])
        
        page_annotations = {}
        for block in blocks:
            page_num = block.get("page", 1)
            if page_num not in page_annotations:
                page_annotations[page_num] = []
            page_annotations[page_num].append(block)
        
        _debug.log_annotation_start(len(blocks))
        _debug.log_info(f"  页面注释分布: {dict((k, len(v)) for k, v in page_annotations.items())}")
        
        plumber_pages_data = []
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_folder, pdf_file)
            with pdfplumber.open(pdf_path) as plumber_pdf:
                for plumber_page in plumber_pdf.pages:
                    page_data = {
                        "width": plumber_page.width,
                        "height": plumber_page.height,
                        "chars": list(plumber_page.chars)
                    }
                    plumber_pages_data.append(page_data)
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_folder, pdf_file)
            src_doc = pymupdf.open(pdf_path)
            doc.insert_pdf(src_doc)
            src_doc.close()
        
        page_count = doc.page_count
        
        total_annotations = 0
        skipped_annotations = 0
        
        for page_idx, page_data in enumerate(plumber_pages_data):
            page_num = page_idx + 1
            if page_num not in page_annotations:
                continue
                
            page = doc[page_idx]
            
            page_width = page_data["width"]
            page_height = page_data["height"]
            char_data = page_data["chars"]
            
            page_block_count = len(page_annotations.get(page_num, []))
            _debug.log_annotation_page(page_num, page_block_count)
            
            block_text = []
            block_chars = []
            prev_char = None
            first_char = None
            block_count = 0
            
            for idx, char in enumerate(char_data):
                from text_extractor import should_filter_kana, is_new_block
                rubyfliter = not should_filter_kana(char, prev_char, self.rubi_size)
                if rubyfliter:
                    if prev_char is not None and is_new_block(prev_char, char, self.x_position_threshold, self.y_position_threshold):
                        if block_text and first_char:
                            text = ''.join(block_text)
                            text = re.sub(r"★校了台紙★", "", text)
                            text = re.sub(r"[︙]", "…", text)
                            text = re.sub(r"S\nA\nM\nP\nL\nE", "", text)
                            text = re.sub(r"[Ⅰ Ⅴ Ⅱ Ⅵ Ⅶ]+", "—", text)
                            text = re.sub(r"(\(cid:\d+\))+", "——", text)
                            text = text.strip()
                            
                            if text and block_count < len(page_annotations[page_num]):
                                annot_text = self._get_annotation_text(page_annotations[page_num][block_count], use_translation)
                                from text_extractor import get_block_fontname
                                fontname = get_block_fontname(block_chars, first_char)
                                
                                x = first_char["x0"] + first_char["width"]/3 + 2 * self.font_scale
                                y = first_char["top"] - 10 * self.font_scale
                                rect = pymupdf.Rect(x, y, x+20, y+20)
                                
                                if 0 <= x <= page_width and 0 <= y <= page_height:
                                    annot = page.add_text_annot(rect.tl, annot_text)
                                    annot.set_opacity(0.75)
                                    annot.set_info(info={
                                        "title": "Auto",
                                        "subject": f"字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}"
                                    })
                                    _debug.log_annotation_added(block_count, annot_text[:30], x/page_width, 1-y/page_height)
                                    total_annotations += 1
                                else:
                                    x = max(0, min(x, page_width - 30))
                                    y = max(10, min(y, page_height - 10))
                                    annot = page.add_text_annot(rect.tl, annot_text)
                                    annot.set_opacity(0.75)
                                    annot.set_info(info={
                                        "title": "Auto",
                                        "subject": f"字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}"
                                    })
                                    _debug.log_annotation_added(block_count, annot_text[:30], x/page_width, 1-y/page_height)
                                    total_annotations += 1
                                block_count += 1
                            
                            block_text = []
                            block_chars = []
                    if not block_text:
                        first_char = char
                    block_text.append(char["text"])
                    block_chars.append(char)
                    prev_char = char
            
            if block_text and first_char:
                text = ''.join(block_text)
                text = re.sub(r"★校了台紙★", "", text)
                text = re.sub(r"[︙]", "…", text)
                text = re.sub(r"S\nA\nM\nP\nL\nE", "", text)
                text = re.sub(r"[Ⅰ Ⅴ Ⅱ Ⅵ Ⅶ]+", "—", text)
                text = re.sub(r"(\(cid:\d+\))+", "——", text)
                text = text.strip()
                
                if text.strip() and block_count < len(page_annotations[page_num]):
                    annot_text = self._get_annotation_text(page_annotations[page_num][block_count], use_translation)
                    from text_extractor import get_block_fontname
                    fontname = get_block_fontname(block_chars, first_char)
                    x = first_char["x0"] + first_char["width"] + 2 * self.font_scale
                    y = first_char["top"] - 10 * self.font_scale
                    rect = pymupdf.Rect(x, y, x+20, y+20)
                    
                    if 0 <= x <= page_width and 0 <= y <= page_height:
                        annot = page.add_text_annot(rect.tl, annot_text)
                        annot.set_opacity(0.75)
                        annot.set_info(info={
                            "title": "Auto",
                            "subject": f"字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}"
                        })
                        _debug.log_annotation_added(block_count, annot_text[:30], x/page_width, 1-y/page_height)
                        total_annotations += 1
                    else:
                        x = max(0, min(x, page_width - 30))
                        y = max(10, min(y, page_height - 10))
                        annot = page.add_text_annot(rect.tl, annot_text)
                        annot.set_opacity(0.75)
                        annot.set_info(info={
                            "title": "Auto",
                            "subject": f"字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}"
                        })
                        _debug.log_annotation_added(block_count, annot_text[:30], x/page_width, 1-y/page_height)
                        total_annotations += 1
        
        _debug.log_annotation_complete(total_annotations)
        _debug.log_info(f"  跳过注释数: {skipped_annotations}")

    def generate_all_outputs(self, input_folder, translated_blocks, output_folder,
                           generate_original=True, generate_translated=True, generate_txt=True,
                           base_filename="translated_manga",
                           filename_suffix="_translated"):
        os.makedirs(output_folder, exist_ok=True)
        results = {}
        
        if base_filename == "translated_manga":
            pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
            is_single_pdf = len(pdf_files) == 1
            
            if is_single_pdf:
                original_name = os.path.splitext(pdf_files[0])[0]
                final_filename = f"{original_name}{filename_suffix}"
            else:
                parent_folder_name = os.path.basename(os.path.abspath(input_folder))
                final_filename = f"{parent_folder_name}{filename_suffix}"
        else:
            final_filename = f"{base_filename}{filename_suffix}"
        
        if generate_original and translated_blocks:
            original_pdf_path = os.path.join(output_folder, f"{final_filename}_original.pdf")
            doc = pymupdf.open()
            self._add_annotations_to_doc(doc, input_folder, translated_blocks, use_translation=False)
            doc.save(original_pdf_path)
            doc.close()
            results['original_pdf'] = original_pdf_path
            print(f"原文注释PDF生成完成: {original_pdf_path}")
        
        if generate_translated and translated_blocks:
            translated_pdf_path = os.path.join(output_folder, f"{final_filename}.pdf")
            doc = pymupdf.open()
            self._add_annotations_to_doc(doc, input_folder, translated_blocks, use_translation=True)
            doc.save(translated_pdf_path)
            doc.close()
            
            from pdf_processor import PDFProcessor
            pdf_processor = PDFProcessor()
            compressed_path, final_size = pdf_processor.compress_pdf(
                translated_pdf_path, 
                max_size_mb=50
            )
            results['translated_pdf'] = compressed_path
            results['translated_pdf_size_mb'] = final_size
            print(f"翻译注释PDF生成完成: {compressed_path}")
            
            if generate_txt:
                from annot_exporter import export_annotations_to_lptxt
                txt_path = export_annotations_to_lptxt(compressed_path)
                results['annot_txt'] = txt_path
        
        return results


def add_translation_annotations(input_folder, translated_blocks, output_path,
                                rubi_size=5.0, x_position_threshold=0.3, y_position_threshold=0.5,
                                include_font_info=False, font_scale=1.0,
                                generate_original=False, generate_translated=True, generate_txt=True,
                                base_filename="translated_manga"):
    annotator = PDFAnnotator(rubi_size, x_position_threshold, y_position_threshold, 
                             include_font_info, font_scale)
    
    output_folder = os.path.dirname(output_path) or "."
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    
    return annotator.generate_all_outputs(
        input_folder, translated_blocks, output_folder,
        generate_original=generate_original,
        generate_translated=generate_translated,
        generate_txt=generate_txt,
        base_filename=base_name
    )
