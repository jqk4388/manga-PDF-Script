# -*- coding: utf-8 -*-
"""
PDF 批量转 TIFF 脚本
- 自动检测脚本所在文件夹中的 PDF 文件
- 如果没有找到 PDF，弹出文件夹选择对话框
- 渲染整页为 TIFF，输出尺寸与 PDF 页面物理尺寸一致
- 单页 PDF：直接输出到 tiff_output/，文件名与 PDF 同名
- 多页 PDF：输出到 tiff_output/<PDF名>/ 子文件夹，文件名 <PDF名>_p0001.tiff ...
- 色彩检测：
    彩色页面    → RGB TIFF（300 DPI，LZW 压缩）
    纯黑色油墨  → 灰度渲染 → 二值化 → 1-bit 黑白位图 TIFF（1200 DPI，50% 阈值，LZW 压缩）
"""

import sys
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import numpy as np
import rasterio

# ──────────────────────────────────────────────
OUTPUT_DPI    = 300    # 彩色/灰度输出分辨率
BW_DPI        = 1200   # 黑白位图输出分辨率
BW_THRESHOLD  = 128    # 二值化阈值（50%，0-255），>= 此值为白，< 此值为黑
COMPRESS      = True   # 是否启用 DEFLATE 压缩（代替 LZW）
# ──────────────────────────────────────────────


# ── LZW 压缩（TIFF LZW 格式）────────────────────────────────────────

def _lzw_compress(data: bytes) -> bytes:
    """
    TIFF LZW 压缩（字节流版）。
    压缩后每字节是代码流的 8 位，低位先写，byte-aligned。
    TIFF LZW 特有：每个 strip/tile 开头必须先写一个字节 0x00（早期规范要求）。

    返回: [0x00] + LZW代码字节流
    """
    CLEAR_CODE = 256
    EOI_CODE   = 257
    FIRST_CODE = 258

    def _make_table():
        return {(i,): i for i in range(256)}   # 键=单字节元组，值=代码号

    table     = _make_table()
    next_code = FIRST_CODE
    code_size = 9
    max_code  = 511   # 2^9 - 1 - 1（留一个给 next_code 触发出栈）

    bit_buf   = 0
    bit_count = 0
    out       = bytearray()
    sub_block = bytearray()

    # 位累加器：bit_buf 低位存最早写入的位
    # 每写入 code_size 位，bit_buf |= code << bit_count，bit_count += code_size
    # flush：取 bit_buf 的低 8 位为输出字节，bit_buf >>= 8，bit_count -= 8
    def _flush_bits():
        nonlocal bit_buf, bit_count
        while bit_count >= 8:
            out.append(bit_buf & 0xFF)
            sub_block.append(bit_buf & 0xFF)
            bit_buf   >>= 8
            bit_count -= 8

    def _clear_dict():
        nonlocal next_code, code_size, max_code
        nonlocal bit_buf, bit_count, table
        _flush_bits()
        bit_buf   |= CLEAR_CODE << bit_count
        bit_count += code_size
        table     = _make_table()   # 直接重新赋值（不能用 dict[:]=...，那是添加 slice 键）
        next_code = FIRST_CODE
        code_size = 9
        max_code  = 511

    def _emit(code: int):
        nonlocal bit_buf, bit_count, code_size, max_code, next_code, table
        bit_buf   |= code << bit_count
        bit_count += code_size
        _flush_bits()                # 只在够 8 位时输出，不在 emit 前 flush

        if next_code >= 4096:         # 字典满（代码 0-4095），发出 Clear
            _clear_dict()
            return

        next_code += 1
        if next_code > max_code and code_size < 12:
            code_size += 1
            max_code   = (1 << code_size) - 1

    def _emit_eoi():
        nonlocal bit_buf, bit_count, table
        bit_buf   |= EOI_CODE << bit_count
        bit_count += 9
        _flush_bits()               # 输出已满的字节
        _flush_bits()               # 再 flush 一次，输出剩余 <8 位的字节

    # 主循环
    prefix: tuple = ()
    for b in data:
        cb = b & 0xFF
        if not prefix:
            prefix = (cb,)
            continue
        nxt = prefix + (cb,)
        if nxt in table:
            prefix = nxt
            continue
        # nxt 不在 table 里：emit prefix, 添加 nxt
        _emit(table[prefix])
        if next_code < 4096:
            table[nxt] = next_code
            next_code += 1
            if next_code > max_code and code_size < 12:
                code_size += 1
                max_code   = (1 << code_size) - 1
            if next_code >= 4096:
                _clear_dict()
        # prefix 已被 emit，重新查找当前 (cb,) 是否还在 table
        if (cb,) not in table:
            _clear_dict()   # table 重置后单字节也可能不在（极少），再清一次
        prefix = (cb,)

    if prefix and prefix in table:
        _emit(table[prefix])
    _emit_eoi()

    # TIFF LZW 需要 MSB first，反转字节顺序并反转每个字节的位
    sub_block.reverse()
    for i in range(len(sub_block)):
        sub_block[i] = int('{:08b}'.format(sub_block[i])[::-1], 2)
    # TIFF LZW 格式：直接返回 LZW 字节流，无需 sub-block
    return bytes(sub_block)


# ── TIFF 写入工具（使用 rasterio）──────────────────────────





def save_tiff(path: Path, pix: fitz.Pixmap, dpi: int,
              grayscale: bool, binarize: bool, threshold: int):
    """将 fitz.Pixmap 保存为 TIFF 文件，使用 rasterio"""
    w, h = pix.width, pix.height
    raw = bytes(pix.samples)

    if binarize:
        # 二值化灰度数据
        gray_samples = np.frombuffer(raw, dtype=np.uint8).reshape(h, w)
        bw = (gray_samples >= threshold).astype(np.uint8) * 255  # 白=255, 黑=0
        array = bw
        count = 1
        dtype = 'uint8'
        photometric = 'minisblack'
    elif grayscale:
        array = np.frombuffer(raw, dtype=np.uint8).reshape(h, w)
        count = 1
        dtype = 'uint8'
        photometric = 'minisblack'
    else:
        array = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)
        count = 3
        dtype = 'uint8'
        photometric = 'rgb'

    profile = {
        'driver': 'GTiff',
        'width': w,
        'height': h,
        'count': count,
        'dtype': dtype,
        'crs': None,
        'transform': rasterio.transform.from_bounds(0, 0, w, h, w, h),
        'compress': 'lzw',
        'photometric': photometric,
        'resolution': (dpi, dpi)
    }

    with rasterio.open(str(path), 'w', **profile) as dst:
        if count == 3:
            dst.write(array.transpose(2, 0, 1))  # rasterio expects (bands, height, width)
        else:
            dst.write(array, 1)


# ── 色彩检测 ──────────────────────────────────────────────────────

def is_page_black_ink_only(page: fitz.Page) -> bool:
    """
    检测页面是否只含黑色油墨。
    低分辨率渲染 RGB，统计非灰色（彩色）像素占比，< 0.5% 视为纯黑墨。
    """
    mat = fitz.Matrix(1.0, 1.0)   # 72 DPI，快速检测
    pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csRGB)
    samples = pix.samples
    total   = pix.width * pix.height
    if total == 0:
        return True

    color_count = 0
    step = 3          # 每隔 3 像素采一次（加速）
    threshold = 10    # 色彩分量差异阈值

    for i in range(0, len(samples) - 2, 3 * step):
        r, g, b = samples[i], samples[i + 1], samples[i + 2]
        if abs(int(r) - int(g)) > threshold or abs(int(g) - int(b)) > threshold:
            color_count += 1

    sampled = total // step
    return (color_count / max(sampled, 1)) < 0.005


# ── 核心转换 ──────────────────────────────────────────────────────

def convert_pdf_to_tiff(pdf_path: Path, output_dir: Path,
                         dpi: int = OUTPUT_DPI, bw_dpi: int = BW_DPI,
                         bw_threshold: int = BW_THRESHOLD):
    """
    将单个 PDF 转换为 TIFF。
    - 彩色页面：dpi 渲染 → RGB TIFF
    - 纯黑墨页面：bw_dpi 渲染灰度 → 二值化 → 1-bit 黑白 TIFF
    - 单页 → tiff_output/<name>.tiff
    - 多页 → tiff_output/<name>/<name>_p0001.tiff ...
    """
    print(f"\n正在处理: {pdf_path.name}")
    doc   = fitz.open(str(pdf_path))
    total = len(doc)
    stem  = pdf_path.stem

    saved = 0
    for page_no in range(total):
        page      = doc[page_no]
        black_ink = is_page_black_ink_only(page)

        if black_ink:
            # 用 1200 DPI 渲染灰度，再二值化
            zoom     = bw_dpi / 72.0
            mat      = fitz.Matrix(zoom, zoom)
            pix      = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csGRAY)
            binarize = True
            out_dpi  = bw_dpi
            mode_label = f"黑白位图 {bw_dpi}DPI"
        else:
            zoom     = dpi / 72.0
            mat      = fitz.Matrix(zoom, zoom)
            pix      = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csRGB)
            binarize = False
            out_dpi  = dpi
            mode_label = f"彩色 {dpi}DPI"

        # 确定输出路径
        if total == 1:
            out_path = output_dir / f"{stem}.tiff"
        else:
            sub_dir  = output_dir / stem
            sub_dir.mkdir(parents=True, exist_ok=True)
            out_path = sub_dir / f"{stem}_p{page_no + 1:04d}.tiff"

        save_tiff(out_path, pix, out_dpi,
                  grayscale=black_ink, binarize=binarize, threshold=bw_threshold)
        saved += 1

        print(f"  第 {page_no + 1}/{total} 页  [{mode_label}]  →  {out_path.name}"
              f"  ({pix.width}x{pix.height}px)")

    doc.close()

    if total == 1:
        print(f"  ✓ 完成，保存至: {output_dir / (stem + '.tiff')}")
    else:
        print(f"  ✓ 完成，共 {saved} 张保存至: {output_dir / stem}")

    return saved


# ── GUI 工具 ──────────────────────────────────────────────────────

def get_script_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def find_pdfs_in_dir(directory: Path):
    pdfs = [p for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() == ".pdf"]
    return sorted(pdfs, key=lambda p: p.name.lower())


def pick_pdf_folder() -> Path | None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showinfo(
        "未找到 PDF 文件",
        "当前脚本目录中没有找到 PDF 文件。\n"
        "请在接下来的对话框中选择包含 PDF 的文件夹。",
        parent=root,
    )
    folder = filedialog.askdirectory(title="选择包含 PDF 文件的文件夹", parent=root)
    root.destroy()
    return Path(folder) if folder else None


# ── 主流程 ────────────────────────────────────────────────────────

def main():
    script_dir = get_script_dir()
    print(f"脚本目录: {script_dir}")

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

    output_dir = source_dir / "tiff_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录: {output_dir}")
    print(f"共找到 {len(pdf_files)} 个 PDF，开始转换（彩色 {OUTPUT_DPI} DPI / 黑白位图 {BW_DPI} DPI）...\n{'=' * 60}")

    total_images = 0
    success      = 0
    failed       = []

    for pdf_path in pdf_files:
        try:
            n = convert_pdf_to_tiff(pdf_path, output_dir,
                                    dpi=OUTPUT_DPI, bw_dpi=BW_DPI,
                                    bw_threshold=BW_THRESHOLD)
            total_images += n
            success += 1
        except Exception as e:
            print(f"  ✗ 转换失败: {e}")
            failed.append((pdf_path.name, str(e)))

    print(f"\n{'=' * 60}")
    print(f"转换完成！成功: {success}/{len(pdf_files)} 个 PDF，共生成 {total_images} 张 TIFF")
    if failed:
        print("失败文件：")
        for name, err in failed:
            print(f"  - {name}: {err}")
    print(f"输出目录: {output_dir}")

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        msg = (
            f"转换完成！\n\n"
            f"成功处理: {success}/{len(pdf_files)} 个 PDF\n"
            f"共生成: {total_images} 张 TIFF\n\n"
            f"输出目录:\n{output_dir}"
        )
        if failed:
            msg += f"\n\n失败 {len(failed)} 个:\n" + "\n".join(f[0] for f in failed)
        messagebox.showinfo("PDF → TIFF 转换完成", msg, parent=root)
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        import fitz
        import numpy as np
        import rasterio
    except ImportError:
        print("正在安装依赖 PyMuPDF, numpy, rasterio...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyMuPDF", "numpy", "rasterio"])
        import fitz
        import numpy as np
        import rasterio

    main()
    input("\n按 Enter 键退出...")
