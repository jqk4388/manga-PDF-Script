import pdfplumber
import tkinter as tk
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



def extract_readtext_from_pdf(pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold):
    """从PDF中提取文本，并过滤假名注音，按块分类"""
    # 确保传入的阈值是浮点数，如果是 StringVar，需要调用 get() 提取实际值
    if isinstance(pagekuaye, tk.StringVar):
        pagekuaye = float(pagekuaye.get())
    else:
        pagekuaye = int(pagekuaye.get())
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
        with pdfplumber.open(file_path) as pdf:
            full_text = []
            total_pages = len(pdf.pages)
            print(f"PDF共有 {total_pages} 页")
            
            for page_number, page in enumerate(pdf.pages):                    
                if page_number % pagekuaye == 0:  # 因为有跨页所以2页处理一次
                    print(f"正在处理第 {page_number + 1} 页")
                    page_text = [f"P{page_number + 1:03d}\n"]  # 在每页开头添加页码
                    char_data = page.chars
                    block_text = []  # 当前文字块
                    prev_char = None
                    
                    for char in char_data:
                        # 如果字体大小大于某个值，且不是【A-OTF リュウミン Pr6N B-KL】字体（假名），则保留
                        if char["size"] > rubi_size and char["fontname"] not in {"A-OTF リュウミン Pr6N B-KL", "RyuminPr6N-Bold"}:
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
        
        return '\n'.join(full_text)
    
    except Exception as e:
        print(f"提取PDF时发生错误: {str(e)}")
        return None

def extract_lptext_from_pdf(pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold):
    """从PDF中提取文本，并过滤假名注音，按块分类"""
    # 确保传入的阈值是浮点数，如果是 StringVar，需要调用 get() 提取实际值
    if isinstance(pagekuaye, tk.StringVar):
        pagekuaye = float(pagekuaye.get())
    else:
        pagekuaye = int(pagekuaye.get())
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
        with pdfplumber.open(file_path) as pdf:
            full_text = []
            total_pages = len(pdf.pages)
            print(f"PDF共有 {total_pages} 页")
            
            for page_number, page in enumerate(pdf.pages):
                page_width = page.width
                page_height = page.height

                if page_number % pagekuaye == 0:  # 因为有跨页所以2页处理一次
                    print(f"正在处理第 {page_number + 1} 页")
                    page_text = [f">>>>>>>>[{page_number + 1:03d}.tif]<<<<<<<<\n"]  # 在每页开头添加页码
                    char_data = page.chars
                    block_text = []  # 当前文字块
                    prev_char = None
                    idx = 0
                    first_char = None
                    
                    for char in char_data:
                        # 如果字体大小大于某个值，且不是【A-OTF リュウミン Pr6N B-KL】字体（假名），则保留
                        if char["size"] > rubi_size and char["fontname"] not in {"A-OTF リュウミン Pr6N B-KL", "RyuminPr6N-Bold"}:
                            if prev_char is not None and is_new_block(prev_char, char, x_position_threshold, y_position_threshold):
                                page_text.append(f"----------------[{idx+1}]----------------[{first_char['x0']/page_width},{1 - first_char['y0']/page_height},1]\n")
                                # 如果是新块，把前一个块加入到页文本中，并开始新的块
                                page_text.append(''.join(block_text) + '\n')
                                block_text = []
                                idx += 1
                            
                            first_char = char
                            block_text.append(char["text"])
                            prev_char = char
                    
                    # 添加当前页最后一个文字块
                    if block_text:
                        page_text.append(''.join(block_text) + '\n')
                    
                    # 将处理过的页面文本添加到总文本中
                    full_text.append(''.join(page_text))
        
        return '\n'.join(full_text)
    
    except Exception as e:
        print(f"提取PDF时发生错误: {str(e)}")
        return None

def save_text_to_file(text, pdf_file_path):
    """将提取的文本保存为txt文件，保存到与PDF文件相同的目录"""
    try:
        pdf_folder = os.path.dirname(pdf_file_path)
        pdf_name = os.path.splitext(os.path.basename(pdf_file_path))[0]
        output_file = os.path.join(pdf_folder, f"{pdf_name}_extracted.txt")
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

def save_lptext_to_file(text, pdf_file_path):
    """将提取的文本保存为txt文件，保存到与PDF文件相同的目录"""
    try:
        pdf_folder = os.path.dirname(pdf_file_path)
        pdf_name = os.path.splitext(os.path.basename(pdf_file_path))[0]
        output_file = os.path.join(pdf_folder, f"{pdf_name}_lp.txt")
        outputhead = "1,0\n-\n框内\n框外\n-\n"
        text = outputhead + text
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

def main(export_lptxt_var, pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold):
    """主函数，负责调用各个步骤并处理异常"""
    try:
        print("开始提取PDF中的文本...")
        extracted_text = extract_readtext_from_pdf(pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold)

        if extracted_text:
            print("文本提取完成，正在保存...")
            save_text_to_file(extracted_text, file_path)
            if export_lptxt_var.get() == 1:
                extracted_lptext = extract_lptext_from_pdf(pagekuaye, file_path, rubi_size, x_position_threshold, y_position_threshold)
                print("LP文本提取完成，正在保存...")
                save_lptext_to_file(extracted_lptext, file_path)
        else:
            print("未能提取到有效文本")
    
    except FileNotFoundError as e:
        print(f"错误: {str(e)}")
    except Exception as e:
        print(f"程序运行时发生错误: {str(e)}")

if __name__ == "__main__":
    main()
