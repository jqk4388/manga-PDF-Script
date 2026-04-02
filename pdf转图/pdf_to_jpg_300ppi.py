# -*- coding: utf-8 -*-
"""
PDF 批量转 JPG 脚本
- 自动检测脚本所在文件夹中的 PDF 文件
- 如果没有找到 PDF，弹出文件夹选择对话框
- 渲染整页为 JPG，输出尺寸与 PDF 页面物理尺寸一致（300 DPI）
- 单页 PDF：直接输出到 jpg_output/，文件名与 PDF 同名
- 多页 PDF：输出到 jpg_output/<PDF名>/ 子文件夹，文件名 <PDF名>_p0001.jpg ...
- 检测页面色彩：纯黑色油墨 → 灰度图，否则 → RGB
"""

import sys
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

# ──────────────────────────────────────────────
# 输出 DPI（决定 JPG 尺寸）
# PDF 物理页面单位是 pt（1 pt = 1/72 inch）
# zoom = DPI / 72，即以该 DPI 渲染后的像素尺寸
OUTPUT_DPI = 300
# ──────────────────────────────────────────────


def get_script_dir() -> Path:
    """获取脚本所在目录（兼容 PyInstaller 打包）"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def find_pdfs_in_dir(directory: Path):
    """在指定目录中找所有 PDF 文件（非递归，忽略大小写后缀）"""
    pdfs = [p for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() == ".pdf"]
    return sorted(pdfs, key=lambda p: p.name.lower())


def is_page_black_ink_only(page: fitz.Page) -> bool:
    """
    检测页面是否只含黑色油墨。
    方法：以低分辨率渲染为 RGB，统计非灰色像素占比。
    非灰色像素（R≠G 或 G≠B 超过阈值）比例极低则视为纯黑墨。
    """
    # 低分辨率渲染即可，速度快
    zoom = 72 / 72  # 1x，72 DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csRGB)

    samples = pix.samples  # bytes: RGBRGB...
    total_pixels = pix.width * pix.height
    if total_pixels == 0:
        return True

    color_pixel_count = 0
    threshold = 10          # 色彩分量差异阈值（0-255）
    sample_step = 3         # 每隔 sample_step 个像素采样一次（加速）

    for i in range(0, len(samples) - 2, 3 * sample_step):
        r = samples[i]
        g = samples[i + 1]
        b = samples[i + 2]
        if abs(int(r) - int(g)) > threshold or abs(int(g) - int(b)) > threshold:
            color_pixel_count += 1

    sampled_pixels = total_pixels // sample_step
    color_ratio = color_pixel_count / max(sampled_pixels, 1)
    return color_ratio < 0.005   # 彩色像素占比 < 0.5% 视为纯黑墨


def render_page(page: fitz.Page, dpi: float, grayscale: bool) -> fitz.Pixmap:
    """渲染页面为 Pixmap，按指定 DPI 和色彩模式"""
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    colorspace = fitz.csGRAY if grayscale else fitz.csRGB
    pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=colorspace)
    return pix


def convert_pdf_to_jpg(pdf_path: Path, output_dir: Path, dpi: float = OUTPUT_DPI):
    """
    将单个 PDF 转换为 JPG。
    - 单页 PDF：jpg_output/<name>.jpg
    - 多页 PDF：jpg_output/<name>/<name>_p0001.jpg ...
    返回生成的图片数量。
    """
    print(f"\n正在处理: {pdf_path.name}")
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    stem = pdf_path.stem

    saved = 0
    for page_no in range(total):
        page = doc[page_no]

        # 色彩检测
        grayscale = is_page_black_ink_only(page)
        mode_label = "灰度" if grayscale else "彩色"

        # 渲染
        pix = render_page(page, dpi, grayscale)

        # 确定输出路径
        if total == 1:
            # 单页：直接放 output_dir，文件名与 PDF 同名
            out_path = output_dir / f"{stem}.jpg"
        else:
            # 多页：放子文件夹
            sub_dir = output_dir / stem
            sub_dir.mkdir(parents=True, exist_ok=True)
            out_path = sub_dir / f"{stem}_p{page_no + 1:04d}.jpg"

        pix.save(str(out_path), output="jpeg", jpg_quality=95)
        saved += 1

        print(f"  第 {page_no + 1}/{total} 页  [{mode_label}]  →  {out_path.name}"
              f"  ({pix.width}x{pix.height}px, {dpi:.0f} DPI)")

    doc.close()

    if total == 1:
        print(f"  ✓ 完成，保存至: {output_dir / (stem + '.jpg')}")
    else:
        print(f"  ✓ 完成，共 {saved} 张图片保存至: {output_dir / stem}")

    return saved


def pick_pdf_folder() -> Path | None:
    """弹出文件夹选择对话框，返回用户选择的路径"""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showinfo(
        "未找到 PDF 文件",
        "当前脚本目录中没有找到 PDF 文件。\n"
        "请在接下来的对话框中选择包含 PDF 的文件夹。",
        parent=root,
    )

    folder = filedialog.askdirectory(
        title="选择包含 PDF 文件的文件夹",
        parent=root,
    )
    root.destroy()

    return Path(folder) if folder else None


def main():
    script_dir = get_script_dir()
    print(f"脚本目录: {script_dir}")

    # 1. 检测脚本目录是否有 PDF
    pdf_files = find_pdfs_in_dir(script_dir)

    if pdf_files:
        source_dir = script_dir
        print(f"在脚本目录中找到 {len(pdf_files)} 个 PDF 文件。")
    else:
        print("脚本目录中未找到 PDF 文件，弹出文件夹选择框...")
        source_dir = pick_pdf_folder()
        if source_dir is None:
            print("未选择文件夹，退出。")
            return
        pdf_files = find_pdfs_in_dir(source_dir)
        if not pdf_files:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showwarning(
                "没有找到 PDF",
                f"所选文件夹中没有 PDF 文件:\n{source_dir}",
                parent=root,
            )
            root.destroy()
            print("所选文件夹中没有 PDF 文件，退出。")
            return

    # 2. 输出目录
    output_dir = source_dir / "jpg_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录: {output_dir}")
    print(f"共找到 {len(pdf_files)} 个 PDF，开始转换（{OUTPUT_DPI} DPI）...\n{'=' * 60}")

    total_images = 0
    success = 0
    failed = []

    for pdf_path in pdf_files:
        try:
            n = convert_pdf_to_jpg(pdf_path, output_dir, dpi=OUTPUT_DPI)
            total_images += n
            success += 1
        except Exception as e:
            print(f"  ✗ 转换失败: {e}")
            failed.append((pdf_path.name, str(e)))

    # 3. 汇总
    print(f"\n{'=' * 60}")
    print(f"转换完成！成功: {success}/{len(pdf_files)} 个 PDF，共生成 {total_images} 张 JPG")
    if failed:
        print("失败文件：")
        for name, err in failed:
            print(f"  - {name}: {err}")
    print(f"输出目录: {output_dir}")

    # 4. GUI 完成提示
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        msg = (
            f"转换完成！\n\n"
            f"成功处理: {success}/{len(pdf_files)} 个 PDF\n"
            f"共生成: {total_images} 张 JPG\n\n"
            f"输出目录:\n{output_dir}"
        )
        if failed:
            msg += f"\n\n失败 {len(failed)} 个:\n" + "\n".join(f[0] for f in failed)
        messagebox.showinfo("PDF → JPG 转换完成", msg, parent=root)
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        import fitz
    except ImportError:
        print("正在安装依赖 PyMuPDF...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyMuPDF"])
        import fitz

    main()
    input("\n按 Enter 键退出...")
