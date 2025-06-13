import pdfplumber
import fitz  # PyMuPDF
import os
import re

# 过滤字体组,着重号等
FILTER_FONTS = [
    "KentenGeneric",
    "AnitoStd",
    "NumberOnly",
]
# 标点字体组
FILTER_PUNCTUATION_FONTS = [
    "MNews",
    "RoHMincho"
]
# 假名字体组
FILTER_KANA_FONTS = [
    "Ryumin", 
    "ATC-", 
    "Antique",
]
def is_kana(char):
    """判断是否为平假名或片假名"""
    c = char["text"]
    return (
        ("\u3040" <= c <= "\u309F") or  # 平假名
        ("\u30A0" <= c <= "\u30FF")     # 片假名
    )

def should_filter_kana(char, prev_char, rubi_size):
    """判断是否应过滤假名"""
    fontname = char["fontname"]
    # 1. 字体过滤
    if any(f in fontname for f in FILTER_FONTS):
        return True
    # 2. 是假名且字号小于rubi_size，字体名是假名常用的字体
    if is_kana(char) and char["size"] < rubi_size:
        if any(x in fontname for x in FILTER_KANA_FONTS):
            return True
    # 3. 是假名且字号大于rubi_size，且字体名是假名常用的字体，且前一个字符是汉字，且距离/字号差异大
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
    """判断是否为新的文字块，支持横排/竖排，只有当字体名包含FILTER_FONTS数组内容时才视为同一块"""
    prev_font = prev_char["fontname"]
    curr_font = curr_char["fontname"]
    size_threshold = 1
    font_size_diff = abs(float(curr_char["size"]) - float(prev_char["size"]))
    font_x_diff = abs(float(curr_char["x0"]) - float(prev_char["x0"]))
    font_y_diff = abs(float(curr_char["top"]) - float(prev_char["top"]))

    if prev_font == curr_font:
        if font_size_diff < size_threshold:
            # 判断排版方向
            if font_y_diff < font_x_diff:
                # 横排版，只判断y方向
                if font_y_diff > prev_char['size']*y_position_threshold:
                    return True
            else:
                # 竖排版，只判断x方向
                if font_x_diff > prev_char['size']*x_position_threshold:
                    return True
        else:
            # 字体同且字号差异大，是新块
            return True
    else:
        # 字体不同，且字号差异小
        if font_size_diff < size_threshold:
            # 直接判断位置(此处有BUG横排排版时，y方向差异大，x方向差异小，可能会误判。但先不修了)
            if font_x_diff > prev_char['size']*x_position_threshold:
                return True
        else:
            # 如果字体名是标点字体中的任意内容，且字号差一个字号的倍数7.3，视为同一块
            if any(f in curr_font for f in FILTER_PUNCTUATION_FONTS) and font_size_diff <= float(curr_char["size"])/7.3:
                return False
            else:
                # 字体不同且字号差异大，是新块
                return True
    return False

def get_block_fontname(block_chars, first_char):
    """优先取block中第一个假名的字体，否则用first_char字体，保留+号后部分"""
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

def should_filter_by_tag(char, filter_color):
    tag = char.get('tag', None)
    if tag == 'PlacedPDF':
        return False
    if tag == 'Metadata' or tag == 'OC':
        return True
    if tag is None:
        color = char.get('non_stroking_color', None)
        if filter_color:
            # 勾选时
            if color == (0, 0, 0, 0) or color == (0, 0, 0, 1):
                return True
            else:
                return False
        else:
            # 不勾选时
            if color == (0, 0, 0, 0):
                return True
            else:
                return False
    return False

def add_annotations_to_pdf(
    pdf_paths, 
    rubi_size, 
    x_position_threshold, 
    y_position_threshold, 
    include_font_info,
    font_scale, 
    filter_color,  # 新增参数
):
    """
    批量处理PDF文件，在每个文字块右上角添加注释。
    """
    font_scale = float(font_scale.get())
    for pdf_path in pdf_paths:
        print(f"正在处理文件: {pdf_path}")
        doc = fitz.open(pdf_path)
        with pdfplumber.open(pdf_path) as plumber_pdf:
            for page_number, (plumber_page, page) in enumerate(zip(plumber_pdf.pages, doc)):
                print(f"  处理第 {page_number+1} 页")
                char_data = plumber_page.chars
                block_text = []
                block_chars = []
                prev_char = None
                first_char = None
                page_width = plumber_page.width
                page_height = plumber_page.height
                block_count = 0
                for idx, char in enumerate(char_data):
                    # 过滤假名
                    rubyfliter = not should_filter_kana(char, prev_char, rubi_size)
                    # tag过滤
                    if should_filter_by_tag(char, filter_color):
                        rubyfliter = False
                    if rubyfliter:
                        if prev_char is not None and is_new_block(prev_char, char, x_position_threshold, y_position_threshold):
                            if block_text and first_char:
                                text = ''.join(block_text)
                                # 使用正则表达式进行替换
                                text = re.sub(r"★校了台紙★", "", text)
                                text = re.sub(r"[︙]", "…", text)
                                text = re.sub(r"S\nA\nM\nP\nL\nE", "", text) 
                                text = re.sub(r"[Ⅰ Ⅴ Ⅱ Ⅵ Ⅶ]+", "—", text)
                                text = re.sub(r"(\(cid:\d+\))+", "——", text)
                                fontname = get_block_fontname(block_chars, first_char)
                                if include_font_info:                                    
                                    text = f"{{字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}}}\n" + text
                                # 注释位置：第一个字符右上角，避免遮挡
                                x = first_char["x0"] + first_char["width"]/3 + 2 * font_scale
                                y = first_char["top"] - 10 * font_scale
                                rect = fitz.Rect(x, y, x+20, y+20)
                                if 0 <= x <= page_width and 0 <= y <= page_height:
                                    print(f"      新文字块[{block_count+1}]，注释内容: {text}，位置: {rect}")
                                    annot = page.add_text_annot(rect.tl, text)
                                    annot.set_opacity(0.75)
                                    annot.set_info(info={
                                        "title": "Auto",
                                        "subject": f"字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}"
                                    })
                                block_count += 1
                            block_text = []
                            block_chars = []
                        if not block_text:
                            first_char = char
                        block_text.append(char["text"])
                        block_chars.append(char)
                        prev_char = char
                # 最后一个块
                if block_text and first_char:
                    text = ''.join(block_text)
                    fontname = get_block_fontname(block_chars, first_char)
                    if include_font_info:
                        text = f"{{字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}}}\n" + text
                    x = first_char["x0"] + first_char["width"] + 2 * font_scale
                    y = first_char["top"] - 10 * font_scale
                    rect = fitz.Rect(x, y, x+20, y+20)
                    if 0 <= x <= page_width and 0 <= y <= page_height:
                        print(f"      最后文字块[{block_count+1}]，注释内容: {text}，位置: {rect}")
                        annot = page.add_text_annot(rect.tl, text)
                        annot.set_opacity(0.75)
                        annot.set_info(info={
                            "title": "Auto",
                            "subject": f"字体：{fontname}}}{{字号：{first_char['size']*0.708661:.1f}"
                        })
                # 添加注释到页面
                print(f"    本页共添加注释数: {block_count}")
        # 保存新PDF
        out_path = os.path.splitext(pdf_path)[0] + "_annotated.pdf"
        print(f"保存带注释的PDF到: {out_path}")
        doc.save(out_path)
        doc.close()