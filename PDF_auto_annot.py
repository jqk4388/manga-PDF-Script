import pdfplumber
import fitz  # PyMuPDF
import os
import re

def is_new_block(prev_char, curr_char, x_position_threshold, y_position_threshold):
    """判断是否为新的文字块"""
    
    # 进行比较，判断是否为新块
    size_threshold = 1 #前后文字的大小差值
    if abs(float(curr_char["size"]) - float(prev_char["size"])) > size_threshold:
        return True
    if abs(float(curr_char["x0"]) - float(prev_char["x0"])) > x_position_threshold or abs(float(curr_char["top"]) - float(prev_char["top"])) > y_position_threshold:
        return True
    return False


def add_annotations_to_pdf(
    pdf_paths, 
    rubi_size, 
    x_position_threshold, 
    y_position_threshold, 
    include_font_info,
    font_scale,  # 字号放大默认1.5
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
                prev_char = None
                first_char = None
                page_width = plumber_page.width
                page_height = plumber_page.height
                block_count = 0
                for idx, char in enumerate(char_data):
                    # print(f"    字符{idx}: '{char['text']}' 字号:{char['size']} 字体:{char['fontname']} x0:{char['x0']} top:{char['top']}")
                    if char["size"] > rubi_size and char["fontname"] not in {"A-OTF リュウミン Pr6N B-KL", "RyuminPr6N-Bold"}:
                        if prev_char is not None and is_new_block(prev_char, char, x_position_threshold, y_position_threshold):
                            if block_text and first_char:
                                text = ''.join(block_text)
                                # 使用正则表达式进行替换
                                text = re.sub(r"★校了台紙★", "", text)
                                text = re.sub(r"[︙]", "…", text)
                                text = re.sub(r"S\nA\nM\nP\nL\nE", "", text) 
                                text = re.sub(r"[Ⅰ Ⅴ Ⅱ Ⅵ Ⅶ]+", "—", text)
                                text = re.sub(r"(\(cid:\d+\))+", "——", text)
                                fontname = first_char['fontname'].split('+')[-1] if '+' in first_char['fontname'] else first_char['fontname']

                                if include_font_info:                                    
                                    text = f"{{字体：{fontname}}}{{字号：{first_char['size']*0.708661*font_scale:.1f}}}\n" + text
                                x = first_char["x0"]-0.7*font_scale
                                y = first_char["top"]-6.9*font_scale
                                rect = fitz.Rect(x, y, x+20, y+20)
                                if 0 <= x <= page_width and 0 <= y <= page_height:
                                    print(f"      新文字块[{block_count+1}]，注释内容: {text}，位置: {rect}")
                                    annot = page.add_text_annot(rect.tl, text)
                                    annot.set_opacity(0.75)
                                    annot.set_info(info={"title": f"{fontname}",
                                                         "subject": f"{first_char['size']*0.708661*font_scale:.1f}",})
                                block_count += 1
                            block_text = []
                        if not block_text:
                            first_char = char
                        block_text.append(char["text"])
                        prev_char = char
                # 最后一个块
                if block_text and first_char:
                    text = ''.join(block_text)
                    fontname = first_char['fontname'].split('+')[-1] if '+' in first_char['fontname'] else first_char['fontname']
                    if include_font_info:
                        text = f"{{字体：{fontname}}}{{字号：{first_char['size']*0.708661*font_scale:.1f}}}\n" + text
                    x = first_char["x0"]
                    y = page_height - first_char["top"]
                    rect = fitz.Rect(x, y, x+20, y+20)
                    if 0 <= x <= page_width and 0 <= y <= page_height:
                        print(f"      最后文字块[{block_count+1}]，注释内容: {text}，位置: {rect}")
                        annot = page.add_text_annot(rect.tl, text)
                        annot.set_opacity(0.75)
                        annot.set_info(info={"title": f"{fontname}",
                                            "subject": f"{first_char['size']*0.708661*font_scale:.1f}",})
                # 添加注释到页面
                print(f"    本页共添加注释数: {len(page.get_text('dict')['blocks'])}")
        # 保存新PDF
        out_path = os.path.splitext(pdf_path)[0] + "_annotated.pdf"
        print(f"保存带注释的PDF到: {out_path}")
        doc.save(out_path)
        doc.close()