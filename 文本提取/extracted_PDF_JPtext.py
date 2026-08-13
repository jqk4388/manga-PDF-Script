import pdfplumber
import tkinter as tk
from tkinter import simpledialog
from pdfminer.pdfdocument import PDFPasswordIncorrect
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


def get_block_fontname(block_chars, first_char):
    """优先取block中第一个假名的字体，否则用first_char字体，并去掉+号后的编码"""
    for c in block_chars:
        if c.get("text") and re.match(r"[\u3040-\u30ff]", c["text"]):
            fontname = c["fontname"]
            if "+" in fontname:
                return fontname.split("+", 1)[-1]
            return fontname
    fontname = first_char["fontname"]
    if "+" in fontname:
        return fontname.split("+", 1)[-1]
    return fontname


def get_block_font_info(block_chars, first_char):
    """返回字体和字号信息"""
    fontname = get_block_fontname(block_chars, first_char)
    size_pt = float(first_char["size"]) * 0.708661
    return f"{{字体：{fontname}，字号：{size_pt:.1f}}}"


def handle_pdf_password_exception(e, file_path):
    """判断是否为PDF密码错误异常，如果是则弹窗要求输入密码，否则返回None"""
    if isinstance(e, PDFPasswordIncorrect):
        root = tk.Tk()
        root.withdraw()
        pwd = simpledialog.askstring("PDF加密", f"文件 {os.path.basename(file_path)} 需要密码，请输入：", show='*', parent=root)
        root.destroy()
        return pwd
    return None

def extract_readtext_from_pdf(jiyingshe_info, pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold, password=None):
    """从PDF中提取文本，并过滤假名注音，按块分类，返回文本、pdf对象和pages"""
    # 确保传入的阈值是浮点数，如果是 StringVar，需要调用 get() 提取实际值
    if isinstance(pagekuaye, tk.IntVar):
        pagekuaye = int(pagekuaye.get())
    else:
        pagekuaye = int(pagekuaye)
    if isinstance(rubi_size, tk.StringVar):
        rubi_size = float(rubi_size.get())
    else:
        rubi_size = float(rubi_size)
    if isinstance(x_position_threshold, tk.StringVar):
        x_position_threshold = float(x_position_threshold.get())
    else:
        x_position_threshold = float(x_position_threshold)
    if isinstance(y_position_threshold, tk.StringVar):
        y_position_threshold = float(y_position_threshold.get())
    else:
        y_position_threshold = float(y_position_threshold)
    try:
        if password is not None:
            pdf = pdfplumber.open(file_path, password=password)
        else:
            pdf = pdfplumber.open(file_path)
        pages = pdf.pages
        total_pages = len(pages)
        full_text = []
        for page_number, page in enumerate(pages):
            if page_number % pagekuaye == 0:
                print(f"正在处理第 {page_number + 1} 页")
                page_text = [f"P{page_number + 1:03d}\n"]  # 在每页开头添加页码
                char_data = page.chars
                block_text = []  # 当前文字块
                prev_char = None
                for char in char_data:
                    if jiyingshe_info:
                        rubyfliter = all(
                            x not in char["fontname"]
                            for x in [
                                "RyuminPr6N-Bold",
                                "RyuminPro-Medium",
                                "ATC-*303*002030ea30e530a630df30f3*M"
                            ]
                        )
                    else:
                        rubyfliter = char["size"] > rubi_size
                    if rubyfliter:
                        if prev_char is not None and is_new_block(prev_char, char, x_position_threshold, y_position_threshold):
                            # 如果是新块，把前一个块加入到页文本中，并开始新的块
                            page_text.append(''.join(block_text) + '\n')
                            block_text = []
                        
                        block_text.append(char["text"])
                        prev_char = char
                
                # 添加当前页最后一个文字块
                if block_text:
                    page_text.append(''.join(block_text) + '\n')
                
                # 将处理过的页面文本添加到总文本中
                full_text.append(''.join(page_text))
        
        return '\n'.join(full_text), pdf, pages
    
    except Exception as e:
        pwd = handle_pdf_password_exception(e, file_path)
        if pwd:
            # 用新密码递归调用自己
            return extract_readtext_from_pdf(
                jiyingshe_info, pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold, password=pwd
            )
        print(f"提取PDF时发生错误: {str(e)}")
        return None, None, None

def extract_lptext_from_pdf(jiyingshe_var, blank, pagekuaye, rubi_size, x_position_threshold, y_position_threshold, pdf=None, pages=None, include_font_info=False):
    """从PDF中提取文本，并过滤假名注音，按块分类。可复用已打开的pdf和pages。"""
    # 确保传入的阈值是浮点数，如果是 StringVar，需要调用 get() 提取实际值
    if isinstance(pagekuaye, tk.StringVar):
        pagekuaye = float(pagekuaye.get())
    elif isinstance(pagekuaye, tk.IntVar):
        pagekuaye = int(pagekuaye.get())
    else:
        pagekuaye = int(pagekuaye)
    if isinstance(rubi_size, tk.StringVar):
        rubi_size = float(rubi_size.get())
    else:
        rubi_size = float(rubi_size)
    if isinstance(x_position_threshold, tk.StringVar):
        x_position_threshold = float(x_position_threshold.get())
    else:
        x_position_threshold = float(x_position_threshold)
    if isinstance(y_position_threshold, tk.StringVar):
        y_position_threshold = float(y_position_threshold.get())
    else:
        y_position_threshold = float(y_position_threshold)
    try:
        if pdf is None or pages is None:
            return None  # 必须传入pdf和pages
        total_pages = len(pages)
        full_text = []
        for page_number, page in enumerate(pages):
            page_width = page.width
            page_height = page.height
            if page_number % pagekuaye == 0:
                print(f"正在处理第 {page_number + 1} 页")
                page_text = [f">>>>>>>>[{page_number + 1:03d}.tif]<<<<<<<<\n"]  # 在每页开头添加页码
                char_data = page.chars
                block_text = []  # 当前文字块
                block_chars = []
                first_char = None
                prev_char = None
                idx = 0
                rect_x0 = 0
                rect_y0 = 0
                
                for char in char_data:
                    if jiyingshe_var:
                        rubyfliter = all(
                            x not in char["fontname"]
                            for x in [
                                "RyuminPr6N-Bold",
                                "RyuminPro-Medium",
                                "ATC-*303*002030ea30e530a630df30f3*M"
                            ]
                        )
                    else:
                        rubyfliter = char["size"] > rubi_size
                    if rubyfliter:
                        if prev_char:
                            rect_x0 = prev_char['x0']/page_width
                            rect_y0 = 1 - prev_char['y0']/page_height
                        else:
                            rect_x0 = char['x0']/page_width
                            rect_y0 = 1 - char['y0']/page_height

                        if pagekuaye == 2: #跨页就不过滤
                            if blank == 1:
                                block_text.append("")
                        else:
                            if blank == 1:
                                block_text.append("")
                        if prev_char is None:
                            if pagekuaye == 2: #跨页就不过滤
                                    page_text.append(f"----------------[{idx+1}]----------------[{rect_x0},{rect_y0},1]\n")
                                    idx += 1
                            else:
                                if rect_x0 < 0 or rect_x0 > 1 or rect_y0 < 0 or rect_y0 > 1:
                                    page_text.append("")
                                else:
                                    page_text.append(f"----------------[{idx+1}]----------------[{rect_x0},{rect_y0},1]\n")
                                    idx += 1

                        if prev_char is not None and is_new_block(prev_char, char, x_position_threshold, y_position_threshold):
                            block_content = ''.join(block_text)
                            if include_font_info and block_content and first_char is not None:
                                page_text.append(get_block_font_info(block_chars, first_char))
                            if block_content:
                                page_text.append(block_content + '\n')
                            if pagekuaye == 2: #跨页就不过滤
                                    page_text.append(f"----------------[{idx+1}]----------------[{rect_x0},{rect_y0},1]\n")                                        
                                    idx += 1
                            else:
                                if rect_x0 < 0 or rect_x0 > 1 or rect_y0 < 0 or rect_y0 > 1:
                                    page_text.append("")
                                else:
                                    page_text.append(f"----------------[{idx+1}]----------------[{rect_x0},{rect_y0},1]\n")
                                    idx += 1
                            block_text = []
                            block_chars = []
                            first_char = None
                        
                        if not block_text:
                            first_char = char
                        block_text.append(char["text"])
                        block_chars.append(char)
                        prev_char = char                
                # 添加文字块到编号之后
                if block_text:
                    block_content = ''.join(block_text)
                    if include_font_info and block_content and first_char is not None:
                        page_text.append(get_block_font_info(block_chars, first_char) + '\n')
                    page_text.append(block_content + '\n')
                
                # 将处理过的页面文本添加到总文本中
                full_text.append(''.join(page_text))
        
        return '\n'.join(full_text)
    
    except Exception as e:
        print(f"提取LPtxt时发生错误: {str(e)}")
        return None

def save_text_to_file(text, pdf_file_path, enable_special_char_replace=True):
    """将提取的文本保存为txt文件，保存到与PDF文件相同的目录。可通过开关控制是否执行特殊字符替换。"""
    try:
        pdf_folder = os.path.dirname(pdf_file_path)
        pdf_name = os.path.splitext(os.path.basename(pdf_file_path))[0]
        output_file = os.path.join(pdf_folder, f"{pdf_name}_extracted.txt")
        if enable_special_char_replace:
            # 使用正则表达式进行替换
            text = re.sub(r"★校了台紙★", "", text)
            text = re.sub(r"[︙]", "…", text)
            text = re.sub(r"[Ⅰ Ⅴ Ⅱ Ⅵ Ⅶ]+", "——", text)
            text = re.sub(r"(\(cid:\d+\))+", "——", text)
            text = re.sub(r"A", "！", text)
            text = re.sub(r"B", "！！", text)
            text = re.sub(r"C", "!!!", text)
            text = re.sub(r"D", "!!!!", text)
            text = re.sub(r"E", "？", text)
            text = re.sub(r"F", "！？", text)
            text = re.sub(r"FFFF", "～～～～", text)
            text = re.sub(r"G", "～", text)
            text = re.sub(r"g", "—", text) #横排——
            text = re.sub(r"h", "—", text) #竖排——
            text = re.sub(r"H", "～～", text)
            text = re.sub(r"I", "♡", text)
            text = re.sub(r"j", "—", text)
            text = re.sub(r"J", "～", text)
        print(f"正在保存文件 {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"文本成功保存到 {output_file}")
    
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")

def save_lptext_to_file(text, pdf_file_path, enable_special_char_replace=True):
    """将提取的文本保存为txt文件，保存到与PDF文件相同的目录。可通过开关控制是否执行特殊字符替换。"""
    try:
        pdf_folder = os.path.dirname(pdf_file_path)
        pdf_name = os.path.splitext(os.path.basename(pdf_file_path))[0]
        output_file = os.path.join(pdf_folder, f"{pdf_name}_lp.txt")
        outputhead = "1,0\n-\n框内\n框外\n-\n"
        text = outputhead + text
        if enable_special_char_replace:
            # 使用正则表达式进行替换
            text = re.sub(r"★校了台紙★", "", text)
            text = re.sub(r"[︙]", "…", text)
            text = re.sub(r"S\nA\nM\nP\nL\nE", "", text) 
            text = re.sub(r"[Ⅰ Ⅴ Ⅱ Ⅵ Ⅶ]+", "——", text)
            text = re.sub(r"(\(cid:\d+\))+", "——", text)
        print(f"正在保存文件 {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"文本成功保存到 {output_file}")
    
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")

def main(jiyingshe_var,export_lptxt_var, export_blank_lptxt_var, pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold, password=None, enable_special_char_replace=True, include_font_info=False):
    """主函数，负责调用各个步骤并处理异常"""
    try:
        export_lptxt_var = int(export_lptxt_var.get())
        export_blank_lptxt_var = int(export_blank_lptxt_var.get())
        filename = os.path.basename(file_path)
        print(f"正在处理文件: {filename}")
        extracted_text, pdf, pages =extract_readtext_from_pdf(
            jiyingshe_var, pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold, password=password
        )
        if extracted_text:
            # print("文本提取完成，正在保存...")
            save_text_to_file(extracted_text, file_path, enable_special_char_replace)
            if export_lptxt_var == 0:
                if export_blank_lptxt_var == 1:
                    extracted_lptext = extract_lptext_from_pdf(jiyingshe_var,1, pagekuaye, rubi_size, x_position_threshold, y_position_threshold, pdf, pages, include_font_info=include_font_info)
                    # print("LP文本提取完成，正在保存...")
                    save_lptext_to_file(extracted_lptext, file_path, enable_special_char_replace)
            else:
                extracted_lptext = extract_lptext_from_pdf(jiyingshe_var,0, pagekuaye, rubi_size, x_position_threshold, y_position_threshold, pdf, pages, include_font_info=include_font_info)
                # print("LP文本提取完成，正在保存...")
                save_lptext_to_file(extracted_lptext, file_path, enable_special_char_replace)
        else:
            print("未能提取到有效文本")
        if pdf is not None:
            pdf.close()
    
    except FileNotFoundError as e:
        print(f"错误: {str(e)}")
    except Exception as e:
        print(f"程序运行时发生错误: {str(e)}")

if __name__ == "__main__":
    main()
