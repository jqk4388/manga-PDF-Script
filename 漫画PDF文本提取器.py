import tkinter as tk
from tkinter import filedialog
import extracted_PDF_JPtext
import os

# 声明 file_path 为全局变量（初始化为空）
file_path = ""

def open_pdf():
    global file_path
    file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if file_path:
        file_name = os.path.basename(file_path)
        print(f"Selected PDF: {file_path}")
        label.config(text=f"当前打开：{file_name}")  # 更新标签文本

def extract_pdf():
    if file_path:
        print(f"Extracting from PDF: {file_path}")
        print(f"Text Size: {text_size_var.get()}")
        print(f"X Offset: {x_offset_var.get()}")
        print(f"Y Offset: {y_offset_var.get()}")
        extracted_PDF_JPtext.main(export_lptxt_var, pagekuaye, file_path, text_size_var, x_offset_var, y_offset_var)
    else:
        print("No PDF selected!")

# 更新滑块和文本框的联动功能
def update_text_size_slider(val):
    text_size_slider.set(float(val))

def update_text_size_entry(val):
    text_size_var.set(f"{float(val):.2f}")

def update_x_offset_slider(val):
    x_offset_slider.set(float(val))

def update_x_offset_entry(val):
    x_offset_var.set(f"{float(val):.2f}")

def update_y_offset_slider(val):
    y_offset_slider.set(float(val))

def update_y_offset_entry(val):
    y_offset_var.set(f"{float(val):.2f}")
# 定义勾选框的回调函数
def update_page():
    if checkbox_var.get():
        pagekuaye.set(2)
        kuaye = True
    else:
        pagekuaye.set(1)
        kuaye = False
    print("跨页:", kuaye)
    
# 创建主窗口
root = tk.Tk()
root.title("漫画PDF文本提取器")
# 设置窗口大小
window_width = 450
window_height = 250
root.geometry(f"{window_width}x{window_height}")

# 计算屏幕居中位置
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y}")  # 设置窗口位置
# 定义一个变量来保存page的值
pagekuaye = tk.IntVar(value=2)
# 定义一个保存勾选状态的变量
checkbox_var = tk.IntVar(value=1)

# 创建标签并将文本添加到标签中
label = tk.Label(root, justify="left")
label.grid(row=0, column=1, sticky="ew")  # 使用 pack() 方法将标签放置在窗口中

# 文件选择按钮
open_pdf_button = tk.Button(root, text="打开一个PDF", command=open_pdf)
open_pdf_button.grid(row=0, column=0, padx=10, pady=10)

# 滑块1和文本框：筛选过滤文字大小
tk.Label(root, text="过滤假名的字号").grid(row=1, column=0, sticky='w')
text_size_var = tk.StringVar(value="7.3")
text_size_slider = tk.Scale(root, from_=0, to=10, resolution=0.01, orient=tk.HORIZONTAL, 
                            command=update_text_size_entry)
text_size_slider.set(7.3)
text_size_slider.grid(row=1, column=1, sticky="ew")

text_size_entry = tk.Entry(root, textvariable=text_size_var, width=6)
text_size_entry.grid(row=1, column=2, sticky="ew") 
text_size_entry.bind("<Return>", lambda event: update_text_size_slider(text_size_var.get()))

# 滑块2和文本框：筛选 x 轴变动阈值
tk.Label(root, text="x 轴变动阈值").grid(row=2, column=0, sticky='w')
x_offset_var = tk.StringVar(value="20.00")
x_offset_slider = tk.Scale(root, from_=0, to=500, resolution=1, orient=tk.HORIZONTAL, 
                           command=update_x_offset_entry)
x_offset_slider.set(20)
x_offset_slider.grid(row=2, column=1, sticky="ew")

x_offset_entry = tk.Entry(root, textvariable=x_offset_var, width=6)
x_offset_entry.grid(row=2, column=2, sticky="ew")
x_offset_entry.bind("<Return>", lambda event: update_x_offset_slider(x_offset_var.get()))

# 滑块3和文本框：筛选 y 轴变动阈值
tk.Label(root, text="y 轴变动阈值").grid(row=3, column=0, sticky='w')
y_offset_var = tk.StringVar(value="5000.00")
y_offset_slider = tk.Scale(root, from_=0, to=9000, resolution=2, orient=tk.HORIZONTAL, 
                           command=update_y_offset_entry)
y_offset_slider.set(5000)
y_offset_slider.grid(row=3, column=1, sticky="ew")

y_offset_entry = tk.Entry(root, textvariable=y_offset_var, width=6)
y_offset_entry.grid(row=3, column=2, sticky="ew")
y_offset_entry.bind("<Return>", lambda event: update_y_offset_slider(y_offset_var.get()))

# 定义一个保存“是否导出lptxt”勾选状态的变量
export_lptxt_var = tk.IntVar(value=1)

# 创建一个勾选框
checkbox = tk.Checkbutton(root, text="是否跨页", variable=checkbox_var, command=update_page)
checkbox.grid(row=4, column=0)

# 创建“是否导出lptxt”勾选框，放在“是否跨页”右边
export_lptxt_checkbox = tk.Checkbutton(root, text="是否导出lptxt", variable=export_lptxt_var)
export_lptxt_checkbox.grid(row=4, column=1, sticky='w')

# 提取PDF按钮
extract_pdf_button = tk.Button(root, text="提取PDF", command=extract_pdf)
extract_pdf_button.grid(row=4, column=2, columnspan=3, padx=20, pady=20)

# 启动主循环
root.mainloop()
