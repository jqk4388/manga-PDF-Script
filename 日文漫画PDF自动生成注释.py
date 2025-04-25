import tkinter as tk
from tkinter import filedialog, messagebox
from PDF_auto_annot import add_annotations_to_pdf

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
    try:
        add_annotations_to_pdf(
            pdf_paths, 
            rubi_size, 
            x_threshold, 
            y_threshold, 
            include_font_info
        )
        messagebox.showinfo("完成", "批量处理完成！")
    except Exception as e:
        messagebox.showerror("错误", str(e))

root = tk.Tk()
root.title("PDF批量注释工具")
# 设置窗口大小
window_width = 200
window_height = 250
root.geometry(f"{window_width}x{window_height}")

# 计算屏幕居中位置
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2
root.geometry(f"{window_width}x{window_height}+{x}+{y}")  # 设置窗口位置

tk.Label(root, text="假名字号过滤:").grid(row=0, column=0)
rubi_size_var = tk.DoubleVar(value=7.3)
tk.Scale(root, from_=4, to=15, resolution=0.01, orient="horizontal", variable=rubi_size_var).grid(row=0, column=1)

tk.Label(root, text="X轴偏移量:").grid(row=1, column=0)
x_var = tk.DoubleVar(value=40)
tk.Scale(root, from_=0, to=500, resolution=1, orient="horizontal", variable=x_var).grid(row=1, column=1)

tk.Label(root, text="Y轴偏移量:").grid(row=2, column=0)
y_var = tk.DoubleVar(value=5000)
tk.Scale(root, from_=0, to=9000, resolution=2, orient="horizontal", variable=y_var).grid(row=2, column=1)

fontinfo_var = tk.BooleanVar()
tk.Checkbutton(root, text="注释文本中包含字体信息", variable=fontinfo_var).grid(row=3, columnspan=2)

tk.Button(root, text="选择PDF并执行", command=run).grid(row=4, columnspan=2, pady=10)

root.mainloop()
