# 导入PyPDF2和re模块
from pypdf import PdfReader, PdfWriter
import re
import os
import tkinter as tk
from tkinter import filedialog

# 获取 .py 文件的绝对路径
file_path = os.path.abspath(__file__)
# 获取 .py 文件所在的目录
dir_path = os.path.dirname(file_path)
# 将当前目录切换到 .py 文件所在的目录
os.chdir(dir_path)

# 定义一个函数来获取当前目录下的所有pdf文件，并按照文件名中的数字进行排序
def get_pdf_files():
    files = os.listdir('.')
    pdf_files = [f for f in files if f.endswith('.pdf')]
    numbers = re.compile(r'(\d+)')
    def numerical_sort(value):
        parts = numbers.split(value)
        parts[1::2] = map(int, parts[1::2])
        return parts
    return sorted(pdf_files, key=numerical_sort)

def select_pdf_folder():
    root = tk.Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory(title="请选择包含PDF的文件夹")
    root.destroy()
    return folder_selected

# 定义一个函数来合并pdf文件，并设置右侧装订方向
def merge_pdf_with_binding(out_path):
    while True:
        pdf_files = get_pdf_files()
        if pdf_files:
            break
        # 没有pdf，弹出文件夹选择
        folder = select_pdf_folder()
        if not folder:
            print("未选择文件夹，程序终止。")
            return
        os.chdir(folder)
    writer = PdfWriter()
    # 合并PDF文件
    for file in pdf_files:
        reader = PdfReader(file)
        for page in reader.pages:
            writer.add_page(page)
    # 设置右侧装订方向的属性
    writer.create_viewer_preferences()
    writer.viewer_preferences.direction = "/R2L"
    for page in writer.pages:
        page.compress_content_streams()
    with open(out_path, "wb") as output_pdf:
        writer.write(output_pdf)

# 调用merge_pdf_with_binding函数，传入输出路径（可以自己修改）
merge_pdf_with_binding('merged.pdf')
os.startfile('merged.pdf')