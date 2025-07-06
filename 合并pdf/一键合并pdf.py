# 导入PyPDF2和re模块
from pypdf import PdfReader, PdfWriter
import re
import os
import tkinter as tk
from tkinter import filedialog
from PIL import Image

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

def get_image_files():
    image_exts = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif', '.webp')
    files = os.listdir('.')
    image_files = [f for f in files if f.lower().endswith(image_exts)]
    numbers = re.compile(r'(\d+)')
    def numerical_sort(value):
        parts = numbers.split(value)
        parts[1::2] = map(int, parts[1::2])
        return parts
    return sorted(image_files, key=numerical_sort)

def select_pdf_folder():
    root = tk.Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory(title="请选择包含PDF的文件夹")
    root.destroy()
    return folder_selected

def save_pdf_with_binding(images_or_writer, out_path):
    """
    images_or_writer: 可以是PIL图片列表，也可以是PdfWriter对象
    out_path: 输出PDF路径
    """
    if isinstance(images_or_writer, list):
        # 图片合并
        from pypdf import PdfWriter
        import io
        writer = PdfWriter()
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        for img in images_or_writer:
            buf = io.BytesIO()
            img.save(buf, format="PDF")
            buf.seek(0)
            reader = PdfReader(buf)
            for page in reader.pages:
                writer.add_page(page)
        writer.create_viewer_preferences()
        writer.viewer_preferences.direction = "/R2L"
        for page in writer.pages:
            page.compress_content_streams()
        with open(out_path, "wb") as f:
            writer.write(f)
    else:
        # PdfWriter合并
        writer = images_or_writer
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        writer.create_viewer_preferences()
        writer.viewer_preferences.direction = "/R2L"
        for page in writer.pages:
            page.compress_content_streams(level=9)
        with open(out_path, "wb") as f:
            writer.write(f)

# 定义一个函数来合并pdf文件，并设置右侧装订方向
def merge_pdf_with_binding():
    initial_dir = os.getcwd()
    output_dir = initial_dir
    while True:
        pdf_files = get_pdf_files()
        if pdf_files:
            break
        # 没有pdf，查找图片
        image_files = get_image_files()
        if image_files:
            images = []
            for img_file in image_files:
                img = Image.open(img_file)
                # if img.mode != 'RGB':
                #     img = img.convert('RGB')
                images.append(img)
            parent_dir = os.path.basename(output_dir)
            out_name = parent_dir + ".pdf"
            out_path = os.path.join(output_dir, out_name)
            if images:
                save_pdf_with_binding(images, out_path)
                print(f"已将图片合并为PDF: {out_path}")
                return out_path
            else:
                print("未找到可用图片，程序终止。")
                return
        # 没有pdf和图片，弹出文件夹选择
        folder = select_pdf_folder()
        if not folder:
            print("未选择文件夹，程序终止。")
            return
        os.chdir(folder)
        output_dir = os.path.dirname(folder)
    writer = PdfWriter()
    # 合并PDF文件
    for file in pdf_files:
        reader = PdfReader(file)
        for page in reader.pages:
            writer.add_page(page)
    parent_dir = os.path.basename(output_dir)
    out_name = parent_dir + ".pdf"
    out_path = os.path.join(output_dir, out_name)
    save_pdf_with_binding(writer, out_path)
    return out_path

# 调用merge_pdf_with_binding函数，传入输出文件名
out_pdf_path = merge_pdf_with_binding()