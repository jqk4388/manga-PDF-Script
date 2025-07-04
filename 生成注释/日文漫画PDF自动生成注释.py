import tkinter as tk
from tkinter import filedialog, messagebox
from PDF_auto_annot import add_annotations_to_pdf
version = "250606"

def run():
    pdf_paths = filedialog.askopenfilenames(
        title="选择PDF文件", filetypes=[("PDF Files", "*.pdf")]
    )
    if not pdf_paths:
        return
    rubi_size = rubi_size_var.get()
    x_threshold = x_var.get()
    y_threshold = y_var.get()
    include_font_info = fontinfo_var.get()
    filter_color = filter_color_var.get()  # 新增
    try:
        add_annotations_to_pdf(
            pdf_paths, 
            rubi_size, 
            x_threshold, 
            y_threshold, 
            include_font_info,
            font_scale_var,  #字号放大
            filter_color,    # 新增参数
        )
        messagebox.showinfo("完成", "批量处理完成！")
    except Exception as e:
        messagebox.showerror("错误", str(e))

root = tk.Tk()
root.title("PDF批量注释工具"+ version)
root.resizable(True, True)  # 允许用户调整窗口大小

# 启动时居中窗口（不指定固定宽高）
root.update_idletasks()
win_width = root.winfo_reqwidth()
win_height = root.winfo_reqheight()
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = (screen_width - win_width) // 2
y = (screen_height - win_height) // 2
root.geometry(f"+{x}+{y}")
root.geometry("")  # 自动适应内容

tk.Label(root, text="假名字号过滤:").grid(row=0, column=0)
rubi_size_var = tk.DoubleVar(value=6.5)
rubi_size_scale = tk.Scale(root, from_=4, to=10, resolution=0.01, orient="horizontal", variable=rubi_size_var)
rubi_size_scale.grid(row=0, column=1)

# 新增过滤标签颜色勾选框
filter_color_var = tk.BooleanVar(value=True)
tk.Checkbutton(root, text="过滤标签颜色", variable=filter_color_var).grid(row=0, column=2, sticky='w')

tk.Label(root, text="竖向行距倍数：").grid(row=1, column=0)
x_var = tk.DoubleVar(value=1.92)
tk.Scale(root, from_=1, to=3, resolution=0.01, orient="horizontal", variable=x_var).grid(row=1, column=1)

tk.Label(root, text="横向行距倍数：").grid(row=2, column=0)
tk.Label(root, text="数值越小，\n拆分的气泡越多。\n上下拆分调小竖向倍数\n左右拆分调小横向倍数").grid(row=1, column=2)
y_var = tk.DoubleVar(value=2.35)
tk.Scale(root, from_=1, to=5, resolution=0.01, orient="horizontal", variable=y_var).grid(row=2, column=1)

# 字号不放大，只偏移
tk.Label(root, text="偏移倍率：").grid(row=3, column=0, sticky='w')
font_scale_var = tk.StringVar(value="1")
font_scale_slider = tk.Scale(root, from_=-1, to=2, resolution=0.1, orient=tk.HORIZONTAL,
                             variable=font_scale_var)
font_scale_slider.set(1)
font_scale_slider.grid(row=3, column=1, sticky="ew")
font_scale_entry = tk.Entry(root, textvariable=font_scale_var, width=6)
font_scale_entry.grid(row=3, column=2, sticky="ew")

fontinfo_var = tk.BooleanVar()
tk.Checkbutton(root, text="注释文本中包含字体信息", variable=fontinfo_var).grid(row=4, columnspan=2)
tk.Button(root, text="选择PDF并执行", command=run).grid(row=4, column=2, pady=10)

root.mainloop()
