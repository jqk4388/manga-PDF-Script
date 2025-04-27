import tkinter as tk
from tkinter import filedialog
import extracted_PDF_JPtext
import os
import threading

# 声明 file_paths 为全局变量
file_paths = []

def open_pdfs():
    global file_paths
    file_paths = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
    if file_paths:
        file_names = [os.path.basename(path) for path in file_paths]
        short_names = [name[:5] + "..." if len(name) > 5 else name for name in file_names]
        # 每行显示最多5个文件名，自动换行
        lines = []
        for i in range(0, len(short_names), 5):
            lines.append(", ".join(short_names[i:i+5]))
        label.config(text="当前打开：\n" + "\n".join(lines))
        print(f"Selected PDFs: {file_paths}")

def extract_worker(pdf_list):
    for path in pdf_list:
        print(f"Extracting from PDF: {path}")
        print(f"Text Size: {text_size_var.get()}")
        print(f"X Offset: {x_offset_var.get()}")
        print(f"Y Offset: {y_offset_var.get()}")
        jiyingshe_info = jiyingshe_var.get()
        password = password_var.get()  # 获取密码值
        extracted_PDF_JPtext.main(jiyingshe_info, export_lptxt_var, export_blank_lptxt_var, 
                                pagekuaye, path, text_size_var, x_offset_var, y_offset_var, 
                                password=password)  # 传递密码参数

def extract_pdf():
    if file_paths:
        # 交错分割PDF列表，分成3组，分别给线程1、2、3
        n = 3
        pdf_lists = [[] for _ in range(n)]
        for idx, path in enumerate(file_paths):
            pdf_lists[idx % n].append(path)
        threads = []
        for pdf_list in pdf_lists:
            if pdf_list:  # 跳过空组
                t = threading.Thread(target=extract_worker, args=(pdf_list,))
                t.start()
                threads.append(t)
    else:
        print("没有选择PDF！")

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
root.resizable(True, True)  # 允许用户手动调整窗口大小

# 启动时居中窗口
root.update_idletasks()
win_width = root.winfo_reqwidth()
win_height = root.winfo_reqheight()
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = (screen_width - win_width) // 2
y = (screen_height - win_height) // 2
root.geometry(f"+{x}+{y}")

# 添加密码输入框
password_var = tk.StringVar(value="")
tk.Label(root, text="PDF密码(无密码留空):").grid(row=5, column=0, sticky='w')
password_entry = tk.Entry(root, textvariable=password_var, show="*")
password_entry.grid(row=5, column=1, sticky="ew")

# 定义一个变量来保存page的值
pagekuaye = tk.IntVar(value=2)
# 定义一个保存勾选状态的变量
checkbox_var = tk.IntVar(value=1)

# 创建标签并将文本添加到标签中
label = tk.Label(root, justify="left", anchor="w", wraplength=450)
label.grid(row=0, column=1, sticky="ew")

# 文件选择按钮
open_pdf_button = tk.Button(root, text="打开PDF文件（可多选）", command=open_pdfs)
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

jiyingshe_var = tk.BooleanVar(value=1)
jiyingshe_checkbox = tk.Checkbutton(root, text="假名过滤选项\n勾选按字体过滤\n不勾选按字号过滤", variable=jiyingshe_var)
jiyingshe_checkbox.grid(row=1, column=3)

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

# 创建“是否导出lptxt”勾选框
export_lptxt_checkbox = tk.Checkbutton(root, text="导出lptxt", variable=export_lptxt_var)
export_lptxt_checkbox.grid(row=4, column=1, sticky='w')
# 定义一个保存“是否导出空白lptxt”勾选状态的变量
export_blank_lptxt_var = tk.IntVar(value=0)

def on_export_lptxt_change():
    if export_lptxt_var.get():
        export_blank_lptxt_var.set(0)

def on_export_blank_lptxt_change():
    if export_blank_lptxt_var.get():
        export_lptxt_var.set(0)

def on_jiyingshe_change(*args):
    state = tk.DISABLED if jiyingshe_var.get() else tk.NORMAL
    text_size_slider.config(state=state)

# 绑定变量变化事件
jiyingshe_var.trace_add("write", on_jiyingshe_change)
# 启动时根据默认值设置控件状态
on_jiyingshe_change()

# 更新“导出lptxt”勾选框的回调
export_lptxt_checkbox.config(command=on_export_lptxt_change)

# 创建“导出空白lptxt”勾选框
export_blank_lptxt_checkbox = tk.Checkbutton(root, text="仅导出坐标", variable=export_blank_lptxt_var, command=on_export_blank_lptxt_change)
export_blank_lptxt_checkbox.grid(row=4, column=2, sticky='w')
# 提取PDF按钮
extract_pdf_button = tk.Button(root, text="提取PDF", command=extract_pdf)
extract_pdf_button.grid(row=4, column=3, columnspan=3, padx=20, pady=20)

# 启动主循环
root.mainloop()
