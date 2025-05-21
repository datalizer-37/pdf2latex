import os
import warnings
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from pytesseract import Output
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
import json

class PDFProcessor:
    def __init__(self, pdf_path, endpoint, key, dpi=300, images_dir="images", fig_dir="figures", corrected_pdf="corrected.pdf", json_path="analysis.json", output_txt="output.txt", pad_px=20, white_thr=245):
        self.pdf_path = pdf_path
        self.endpoint = endpoint
        self.key = key
        self.dpi = dpi
        self.images_dir = images_dir
        self.fig_dir = fig_dir
        self.corrected_pdf = corrected_pdf
        self.json_path = json_path
        self.output_txt = output_txt
        self.pad_px = pad_px
        self.white_thr = white_thr
        self.processed_images = []
        self.layout = {}
        self.fig_paths_by_idx = {}
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.fig_dir, exist_ok=True)
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        Image.MAX_IMAGE_PIXELS = None
        self.client = DocumentIntelligenceClient(self.endpoint, AzureKeyCredential(self.key))

    def fix_pdf(self):
        print("Starting PDF fixing...")
        pages = convert_from_path(self.pdf_path, dpi=self.dpi)
        total_pages = len(pages)
        print(f"Fixing PDF: processing {total_pages} pages...")
        out_pages = []
        for i, page in enumerate(pages, 1):
            print(f"Processing page {i}...")
            try:
                d = pytesseract.image_to_osd(page, output_type=Output.DICT)
                angle = int(d.get("rotate", 0))
                if angle:
                    print(f"Rotating page {i} by {360 - angle} degrees.")
                    page = page.rotate(360 - angle, expand=True)
            except pytesseract.TesseractError as e:
                print(f"Skipping OSD on page {i}: {e}")
                print(f"[Using original image for page {i} without rotation.")

            g = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2GRAY)
            r_mean = g.mean(axis=1)
            c_mean = g.mean(axis=0)
            r_idx = np.where(r_mean < self.white_thr)[0]
            c_idx = np.where(c_mean < self.white_thr)[0]
            if r_idx.size > 0 and c_idx.size > 0:
                y1, y2 = r_idx[0], r_idx[-1]
                x1, x2 = c_idx[0], c_idx[-1]
                y1 = max(y1 - self.pad_px, 0)
                x1 = max(x1 - self.pad_px, 0)
                y2 = min(y2 + self.pad_px, g.shape[0] - 1)
                x2 = min(x2 + self.pad_px, g.shape[1] - 1)
                print(f"Cropping page {i} to coordinates: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
                page = page.crop((x1, y1, x2, y2))
            save_path = os.path.join(self.images_dir, f"page_{i}_processed.png")
            page.save(save_path, "PNG")
            print(f"Saved processed page {i} to {save_path}")
            
            out_pages.append(page)
        if out_pages:
            out_pages[0].save(self.corrected_pdf, save_all=True, append_images=out_pages[1:], dpi=(self.dpi, self.dpi))
            print(f"Corrected PDF saved to {self.corrected_pdf}")
        self.processed_images = out_pages
        print("PDF fixing completed.")

    def analyze_pdf(self):
        print("Starting PDF analysis...")
        with open(self.corrected_pdf, "rb") as f:
            body = f.read()
        print("Analyzing PDF with Azure Document Intelligence...")
        poller = self.client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=body,
            content_type="application/pdf"
        )
        result = poller.result()
        layout = result.as_dict()
        total_pages = len(self.processed_images)
        existing = {p["pageNumber"]: p for p in layout.get("pages", [])}
        full_pages = []
        for pg in range(1, total_pages + 1):
            if pg in existing:
                full_pages.append(existing[pg])
            else:
                full_pages.append({
                    "pageNumber": pg,
                    "angle": 0,
                    "width": self.processed_images[pg-1].width / self.dpi,
                    "height": self.processed_images[pg-1].height / self.dpi,
                    "unit": "inch",
                    "words": [],
                    "lines": []
                })
        layout["pages"] = full_pages
        with open(self.json_path, "w", encoding="utf-8") as jf:
            json.dump(layout, jf, indent=4)
        print(f"Analysis completed. JSON saved to {self.json_path}")
        self.layout = layout
        pages_meta = {p["pageNumber"]: p for p in layout.get("pages", [])}
        figures = layout.get("figures", [])
        print("Extracting figures...")
        for idx, fig in enumerate(figures):
            region = fig.get("boundingRegions", [])[0]
            pg = region.get("pageNumber")
            meta = pages_meta.get(pg, {})
            Wj, Hj = meta.get("width", 1), meta.get("height", 1)
            coords = region.get("boundingBox", region.get("polygon", []))
            xs, ys = coords[0::2], coords[1::2]
            x0f, x1f = min(xs)/Wj, max(xs)/Wj
            y0f, y1f = min(ys)/Hj, max(ys)/Hj
            img = self.processed_images[pg - 1]
            Wp, Hp = img.size
            x0, x1 = int(x0f * Wp), int(x1f * Wp)
            y0, y1 = int(y0f * Hp), int(y1f * Hp)
            x0, x1 = max(0, x0), min(Wp, x1)
            y0, y1 = max(0, y0), min(Hp, y1)
            if x1 > x0 and y1 > y0:
                crop = img.crop((x0, y0, x1, y1))
                out_png = os.path.join(self.fig_dir, f"figure_{pg}_{idx}.png")
                crop.save(out_png)
                self.fig_paths_by_idx[idx] = out_png
                print(f"Saved figure {idx} to {out_png}")
        print(f"Extracted {len(self.fig_paths_by_idx)} figures.")
        print("PDF analysis completed.")

    def generate_text(self):
        print("Starting text generation...")
        def get_bounding_box_center(bounding_region):
            page = bounding_region["pageNumber"]
            polygon = bounding_region["polygon"]
            xs, ys = polygon[0::2], polygon[1::2]
            x_center = sum(xs) / len(xs)
            y_center = sum(ys) / len(ys)
            return page, y_center, x_center
        layout = self.layout
        paragraphs = layout.get("paragraphs", [])
        figures = layout.get("figures", [])
        elements = []
        for para_idx, para in enumerate(paragraphs):
            if not para.get("boundingRegions"):
                continue
            page, y_center, x_center = get_bounding_box_center(para["boundingRegions"][0])
            elements.append({
                "type": "paragraph",
                "index": para_idx,
                "page": page,
                "y_center": y_center,
                "x_center": x_center,
                "content": para.get("content", "")
            })
        for fig_idx, fig in enumerate(figures):
            if not fig.get("boundingRegions"):
                continue
            page, y_center, x_center = get_bounding_box_center(fig["boundingRegions"][0])
            elements.append({
                "type": "figure",
                "index": fig_idx,
                "page": page,
                "y_center": y_center,
                "x_center": x_center,
                "content": f"[FIGURE: {self.fig_paths_by_idx.get(fig_idx, '')}]"
            })
        elements.sort(key=lambda e: (e["page"], e["y_center"], e["x_center"]))
        with open(self.output_txt, "w", encoding="utf-8") as out:
            for element in elements:
                out.write(element["content"] + "\n\n")
        print(f"Output text written to {self.output_txt}")
        print("Text generation completed.")

    def process(self):
        print("Starting PDF processing...")
        self.fix_pdf()
        print("PDF fixing completed.")
        self.analyze_pdf()
        print("PDF analysis completed.")
        self.generate_text()
        print("Text generation completed.")
        print("PDF processing finished.")