import pdfplumber
import pymupdf
import re
import os

try:
    from debug_logger import get_debug_logger
    _debug = get_debug_logger()
except ImportError:
    class SimpleDebug:
        def is_enabled(self): return False
        def log_extraction_start(self, *args): pass
        def log_extraction_page(self, *args): pass
        def log_block_extracted(self, *args): pass
        def log_block_filtered(self, *args): pass
        def log_extraction_complete(self, *args): pass
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

def clean_text(text):
    text = re.sub(r"★校了台紙★", "", text)
    text = re.sub(r"[︙]", "…", text)
    text = re.sub(r"S\nA\nM\nP\nL\nE", "", text)
    text = re.sub(r"[Ⅰ Ⅴ Ⅱ Ⅵ Ⅶ]+", "—", text)
    text = re.sub(r"(\(cid:\d+\))+", "——", text)
    text = re.sub(r"A", "！", text)
    text = re.sub(r"B", "！！", text)
    text = re.sub(r"C", "!!!", text)
    text = re.sub(r"D", "!!!!", text)
    text = re.sub(r"E", "？", text)
    text = re.sub(r"F", "！？", text)
    text = re.sub(r"FFFF", "～～～～", text)
    text = re.sub(r"G", "～", text)
    text = re.sub(r"g", "—", text)
    text = re.sub(r"h", "—", text)
    text = re.sub(r"H", "～～", text)
    text = re.sub(r"I", "♡", text)
    text = re.sub(r"j", "—", text)
    text = re.sub(r"J", "～", text)
    return text

class TextExtractor:
    def __init__(self, rubi_size=6.5, x_position_threshold=1.92, y_position_threshold=2.35):
        self.rubi_size = rubi_size
        self.x_position_threshold = x_position_threshold
        self.y_position_threshold = y_position_threshold

    def extract_text_from_pdf(self, pdf_path):
        extracted_blocks = []
        try:
            _debug.log_extraction_start(pdf_path)
            with pdfplumber.open(pdf_path) as plumber_pdf:
                for page_number, page in enumerate(plumber_pdf.pages):
                    page_width = page.width
                    page_height = page.height
                    char_data = page.chars
                    _debug.log_extraction_page(page_number + 1, len(char_data))
                    block_text = []
                    block_chars = []
                    prev_char = None
                    first_char = None

                    for char in char_data:
                        rubyfliter = not should_filter_kana(char, prev_char, self.rubi_size)
                        if rubyfliter:
                            if prev_char is not None and is_new_block(prev_char, char, self.x_position_threshold, self.y_position_threshold):
                                if block_text and first_char:
                                    text = clean_text(''.join(block_text))
                                    if text.strip():
                                        fontname = get_block_fontname(block_chars, first_char)
                                        x0 = first_char["x0"] / page_width
                                        y0 = 1 - first_char["y0"] / page_height
                                        block_data = {
                                            "page": page_number + 1,
                                            "text": text,
                                            "font": fontname,
                                            "size": first_char["size"],
                                            "x": x0,
                                            "y": y0
                                        }
                                        extracted_blocks.append(block_data)
                                        _debug.log_block_extracted(len(extracted_blocks), page_number + 1, text, fontname, first_char["size"])
                                    else:
                                        _debug.log_block_filtered(len(extracted_blocks) + 1, "空文本")
                                block_text = []
                                block_chars = []
                            if not block_text:
                                first_char = char
                            block_text.append(char["text"])
                            block_chars.append(char)
                            prev_char = char

                    if block_text and first_char:
                        text = clean_text(''.join(block_text))
                        if text.strip():
                            fontname = get_block_fontname(block_chars, first_char)
                            x0 = first_char["x0"] / page_width
                            y0 = 1 - first_char["y0"] / page_height
                            block_data = {
                                "page": page_number + 1,
                                "text": text,
                                "font": fontname,
                                "size": first_char["size"],
                                "x": x0,
                                "y": y0
                            }
                            extracted_blocks.append(block_data)
                            _debug.log_block_extracted(len(extracted_blocks), page_number + 1, text, fontname, first_char["size"])
                        else:
                            _debug.log_block_filtered(len(extracted_blocks) + 1, "空文本")
        except Exception as e:
            _debug.log_error("文本提取", str(e))
            print(f"提取PDF文本时发生错误: {str(e)}")
            raise
        _debug.log_extraction_complete(len(extracted_blocks))
        return extracted_blocks

    def merge_and_extract(self, input_folder):
        pdf_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')])
        all_blocks = []
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_folder, pdf_file)
            blocks = self.extract_text_from_pdf(pdf_path)
            all_blocks.extend(blocks)
        return all_blocks

def extract_text_from_folder(input_folder, rubi_size=5.0, x_position_threshold=0.3, y_position_threshold=0.5):
    extractor = TextExtractor(rubi_size, x_position_threshold, y_position_threshold)
    return extractor.merge_and_extract(input_folder)
