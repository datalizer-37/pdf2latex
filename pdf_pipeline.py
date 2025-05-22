import os
import subprocess
import tempfile
import shutil
from dotenv import load_dotenv
import streamlit as st

# Load environment variables
load_dotenv()

from final import PDFProcessor
from test import Config, generate_latex

def save_uploaded_file(uploaded_file, suffix):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getbuffer())
    tmp.flush()
    return tmp.name


def main():
    st.title("📝 PDF → Word Converter (PDF output removed)")

    # Image DPI selection
    dpi = st.sidebar.slider(
        "Image DPI",
        min_value=100,
        max_value=600,
        value=300,
        step=50,
        help="- Higher → better detail\n- Lower → faster processing & smaller files"
    )

    st.markdown("---")
    uploaded_pdf = st.file_uploader("📄 Upload a PDF", type=["pdf"])
    if not uploaded_pdf:
        st.info("Upload a PDF to begin.")
        return

    if st.button("Process & Generate Word (.docx)"):
        pdf_path = save_uploaded_file(uploaded_pdf, ".pdf")

        # Prepare work directory
        work_dir = tempfile.mkdtemp(prefix="pdf2docx_")
        images_dir = os.path.join(work_dir, "images")
        figures_dir = os.path.join(work_dir, "figures")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(figures_dir, exist_ok=True)

        # Define paths
        corrected_pdf = os.path.join(work_dir, "corrected.pdf")
        txt_file      = os.path.join(work_dir, "output.txt")
        json_path     = os.path.join(work_dir, "analysis.json")
        tex_file      = os.path.join(work_dir, "paper_body.tex")
        docx_path     = os.path.join(work_dir, "paper_final.docx")

        config = Config()

        # 1) OCR & correction
        with st.spinner("Processing PDF…"):
            processor = PDFProcessor(
                pdf_path=pdf_path,
                endpoint=config.doc_intelligence_endpoint,
                key=config.doc_intelligence_key,
                dpi=dpi,
                images_dir=images_dir,
                fig_dir=figures_dir,
                corrected_pdf=corrected_pdf,
                json_path=json_path,
                output_txt=txt_file
            )
            try:
                processor.process()
            except Exception as e:
                st.error(f"Error processing PDF: {e}")
                return
        st.success("PDF processing complete.")

        # 2) Generate LaTeX body (intermediate)
        with st.spinner("Generating LaTeX…"):
            body = generate_latex(txt_file, config)
            tex_content = "\n".join([
                r"\documentclass{article}",
                r"\usepackage{amsmath,amssymb,physics,graphicx,float,enumitem}",
                r"\begin{document}", body, r"\end{document}"
            ])
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(tex_content)
        st.success("LaTeX source generated.")

        # 3) Convert to Word via Pandoc
        with st.spinner("Converting to Word…"):
            pandoc_cmd = [
                "pandoc", os.path.basename(tex_file),
                "-s", "-o", os.path.basename(docx_path),
                "--resource-path=.:images:figures"
            ]
            try:
                subprocess.run(pandoc_cmd, cwd=work_dir, check=True)
            except FileNotFoundError:
                st.error("`pandoc` not found. Add it to apt.txt.")
                return
            except subprocess.CalledProcessError as e:
                st.error(f"Pandoc to DOCX failed: {e}")
                return
        st.success("Word document created.")

        # 4) Offer Word download
        with open(docx_path, "rb") as f:
            st.download_button(
                "Download Word (.docx)",
                data=f.read(),
                file_name="paper_final.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

if __name__ == "__main__":
    main()
