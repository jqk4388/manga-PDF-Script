import os
import pymupdf


def rect_to_percentage(rect, page_width, page_height):
    return [
        rect.x0 / page_width,
        rect.y0 / page_height
    ]


def extract_annotations(pdf_path):
    document = pymupdf.open(pdf_path)
    total_pages = document.page_count
    annotations = []

    for page_num in range(len(document)):
        page = document.load_page(page_num)
        annot_list = page.annots()
        page_width = page.rect.width
        page_height = page.rect.height

        for annot in annot_list:
            subject = annot.info.get("subject", "")
            if not subject:
                subject = "字体：默认"
            annot_info = {
                "page": page_num + 1,
                "type": annot.type[0],
                "content": annot.info.get("content", ""),
                "coordinates_percentage": rect_to_percentage(annot.rect, page_width, page_height),
                "creation_date": annot.info.get("modDate", ""),
                "subject": subject
            }
            annotations.append(annot_info)

    annotations.sort(key=lambda x: x["creation_date"])
    annotations.sort(key=lambda x: x["page"])
    
    current_page = None
    index = 1
    for annot in annotations:
        if annot["page"] != current_page:
            current_page = annot["page"]
            index = 1
        annot["index"] = index
        index += 1

    return annotations, total_pages


def format_data(annotations):
    formatted = f"\n----------------[{annotations['index']}]----------------[{annotations['coordinates_percentage'][0]},{annotations['coordinates_percentage'][1]},1]\n{{{annotations['subject']}}}{annotations['content']}"
    return formatted


def export_annotations_to_lptxt(pdf_path, output_path=None):
    if output_path is None:
        output_path = os.path.splitext(pdf_path)[0] + "_annotations.txt"
    
    annotations, total_pages = extract_annotations(pdf_path)
    
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(f"1,0\n-\n框内\n框外\n-")
        
        annotated_pages = {}
        for annot in annotations:
            page = annot['page']
            if page not in annotated_pages:
                annotated_pages[page] = []
            annotated_pages[page].append(annot)
        
        for page_num in range(1, total_pages + 1):
            file.write(f"\n>>>>>>>>[{page_num:03d}.tif]<<<<<<<<")
            
            if page_num in annotated_pages:
                for annot in annotated_pages[page_num]:
                    formatted_data = format_data(annot)
                    file.write(formatted_data)
    
    print(f"注释导出完成: {output_path}")
    return output_path


def export_annotations_to_simple_txt(pdf_path, output_path=None):
    if output_path is None:
        output_path = os.path.splitext(pdf_path)[0] + "_simple.txt"
    
    annotations, total_pages = extract_annotations(pdf_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        current_page = None
        for annot in annotations:
            if annot['page'] != current_page:
                if current_page is not None:
                    f.write("\n")
                f.write(f"P{annot['page']}\n")
                current_page = annot['page']
            f.write(f"{annot['content']}\n\n")
    
    print(f"注释导出完成: {output_path}")
    return output_path
