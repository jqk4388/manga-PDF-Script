#pip install Pillow pypdf pdfplumber PyMuPDF
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import os
from pypdf import PdfWriter, PdfReader
from pypdf.generic import DictionaryObject, NameObject, TextStringObject, ArrayObject, FloatObject
import pymupdf  # PyMuPDF
# 获取 .py 文件的绝对路径
file_path = os.path.abspath (__file__)
# 获取 .py 文件所在的目录
dir_path = os.path.dirname (file_path)
# 将当前目录切换到 .py 文件所在的目录
os.chdir (dir_path)


class JsonToPdfConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("JSON to PDF Converter v1.0-BY几千块")
        self.root.geometry("600x250")
        # 设置窗口在屏幕中央
        self.center_window()
        
        self.json_file_path = tk.StringVar()
        self.output_pdf_path = tk.StringVar()
        
        self.setup_ui()
    
    def center_window(self):
        # 更新窗口以获取正确的尺寸
        self.root.update_idletasks()
        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        # 获取窗口尺寸
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        # 计算居中位置
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        # 设置窗口位置
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def setup_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # JSON文件选择
        ttk.Label(main_frame, text="JSON文件:").grid(row=0, column=0, sticky=tk.W, pady=5)
        json_entry = ttk.Entry(main_frame, textvariable=self.json_file_path, width=50)
        json_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="浏览", command=self.browse_json_file).grid(row=0, column=2, padx=5, pady=5)
        
        # 输出PDF路径
        ttk.Label(main_frame, text="输出PDF:").grid(row=1, column=0, sticky=tk.W, pady=5)
        pdf_entry = ttk.Entry(main_frame, textvariable=self.output_pdf_path, width=50)
        pdf_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="浏览", command=self.browse_pdf_file).grid(row=1, column=2, padx=5, pady=5)
        
        # 转换按钮
        convert_btn = ttk.Button(main_frame, text="转换为PDF", command=self.convert_to_pdf)
        convert_btn.grid(row=2, column=0, columnspan=3, pady=20)
        
        # 进度条
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=3, column=0, columnspan=3, pady=10)
        
        # 状态标签
        self.status_label = ttk.Label(main_frame, text="就绪")
        self.status_label.grid(row=4, column=0, columnspan=3, pady=5)
    
    def browse_json_file(self):
        file_path = filedialog.askopenfilename(
            title="选择JSON文件",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.json_file_path.set(file_path)
            # 自动设置输出PDF路径
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(os.path.dirname(file_path), f"{base_name}.pdf")
            self.output_pdf_path.set(output_path)
    
    def browse_pdf_file(self):
        file_path = filedialog.asksaveasfilename(
            title="保存PDF文件",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.output_pdf_path.set(file_path)
    
    def convert_to_pdf(self):
        json_path = self.json_file_path.get()
        pdf_path = self.output_pdf_path.get()
        
        if not json_path or not pdf_path:
            messagebox.showerror("错误", "请指定JSON文件和输出PDF路径")
            return
        
        try:
            self.status_label.config(text="正在转换...")
            self.progress['value'] = 0
            self.root.update()
            
            # 创建带注释的PDF
            self.create_pdf_with_annotations(json_path, pdf_path)
            
            self.status_label.config(text="转换完成!")
            messagebox.showinfo("成功", f"PDF已保存到: {pdf_path}")
            
        except Exception as e:
            self.status_label.config(text="转换失败")
            messagebox.showerror("错误", f"转换过程中出现错误: {str(e)}")
    
    def create_pdf_with_annotations(self, json_path, output_pdf_path):
        """创建带注释的PDF"""
        # 读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 获取图片路径和目录
        directory = data.get("directory", os.path.dirname(json_path))
        
        # 读取图片信息，获取页面尺寸
        pages = data.get("pages", {})
        image_names = list(pages.keys())
        
        # 使用pypdf创建PDF
        pdf_writer = PdfWriter()
        
        # 更新进度
        total_pages = len(image_names)
        progress_step = 100 / total_pages if total_pages > 0 else 0
        
        # 创建临时PDF文件
        temp_pdf_path = output_pdf_path.replace('.pdf', '_temp.pdf')
        
        for i, img_name in enumerate(image_names):
            img_path = os.path.join(directory, img_name)
            
            # 检查图片是否存在
            if not os.path.exists(img_path):
                # 如果在当前目录下找不到，尝试直接使用图片名
                if os.path.exists(os.path.join(os.path.dirname(json_path), img_name)):
                    img_path = os.path.join(os.path.dirname(json_path), img_name)
                else:
                    print(f"警告: 图片 {img_path} 不存在，跳过")
                    continue

            # 获取图片尺寸
            with Image.open(img_path) as img:
                img_width, img_height = img.size
            
            # 创建临时PDF页面
            temp_pdf_page = pymupdf.open()  # 创建新的文档
            page = temp_pdf_page.new_page(width=img_width, height=img_height)
            page.insert_image(pymupdf.Rect(0, 0, img_width, img_height), filename=img_path)
            
            # 保存临时页面
            temp_page_path = f"temp_page_{i}.pdf"
            temp_pdf_page.save(temp_page_path)
            temp_pdf_page.close()
            
            # 将页面添加到PDF writer
            with open(temp_page_path, 'rb') as temp_pdf:
                temp_reader = PdfReader(temp_pdf)
                page_obj = temp_reader.pages[0]
                pdf_writer.add_page(page_obj)
            
            # 清理临时文件
            if os.path.exists(temp_page_path):
                os.remove(temp_page_path)
            
            # 更新进度
            self.progress['value'] = (i + 1) * progress_step
            self.root.update()
        
        # 保存临时PDF
        with open(temp_pdf_path, "wb") as temp_pdf_file:
            pdf_writer.write(temp_pdf_file)
        
        # 使用PyMuPDF打开PDF并添加注释
        self.add_annotations_with_pymupdf(temp_pdf_path, output_pdf_path, data, directory)
        
        # 删除临时文件
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
    
    def add_annotations_with_pymupdf(self, temp_pdf_path, output_pdf_path, data, directory):
        """使用PyMuPDF添加注释"""
        # 使用PyMuPDF打开PDF
        doc = pymupdf.open(temp_pdf_path)
        
        pages = data.get("pages", {})
        image_names = list(pages.keys())
        
        for i, img_name in enumerate(image_names):
            if i >= len(doc):
                break
                
            page = doc[i]
            
            img_path = os.path.join(directory, img_name)
            
            # 获取图片尺寸
            with Image.open(img_path) as img:
                img_width, img_height = img.size
            
            # 获取当前图片的文本信息
            text_blocks = pages[img_name]
            
            # 添加注释
            for block in text_blocks:
                text = block.get("text", "")
                if isinstance(text, list):
                    text = " ".join(text)  # 将列表转换为字符串
                
                # 获取文本块坐标
                bounding_rect = block.get("_bounding_rect", [0, 0, 100, 100])
                x1, y1, width, height = bounding_rect
                
                # 计算相对位置（百分比）
                rel_x = x1 / img_width
                rel_y = y1 / img_height
                rel_width = width / img_width
                rel_height = height / img_height
                
                # 计算PDF中的绝对坐标（PyMuPDF使用左上角为原点）
                abs_x = rel_x * page.rect.width
                abs_y = rel_y * page.rect.height
                
                # 获取字体信息
                font_name = block.get("_detected_font_name", "Unknown")
                font_size = block.get("_detected_font_size", 12)
                # 转换字体大小：原大小 * 72 / 96
                converted_font_size = font_size * 72 / 96
                
                # 创建注释内容
                annotation_content = f"{text}"
                annotation_subject = f"字体: {font_name}}}{{字号: {converted_font_size}"
                
                # 创建注释矩形（在文本块位置添加注释图标）
                rect = pymupdf.Rect(abs_x, abs_y, abs_x + 20, abs_y + 20)
                
                # 添加文本注释
                if 0 <= abs_x <= page.rect.width and 0 <= abs_y <= page.rect.height:
                    annot = page.add_text_annot((abs_x, abs_y), annotation_content)
                    annot.set_info(title="Auto", subject=annotation_subject)
                    annot.update()
        
        # 保存带注释的PDF
        doc.save(output_pdf_path)
        doc.close()


def main():
    root = tk.Tk()
    app = JsonToPdfConverter(root)
    root.mainloop()


if __name__ == "__main__":
    main()