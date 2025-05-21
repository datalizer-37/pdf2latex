import os
import subprocess
import tempfile

import streamlit as st

from final import PDFProcessor
from test import Config, generate_latex

def save_uploaded_file(uploaded_file, suffix):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getbuffer())
    tmp.flush()
    return tmp.name

def main():
    st.title("📝 PDF -> LaTeX Converter")

    dpi = st.sidebar.slider(
        "Image DPI",
        min_value=100,
        max_value=600,
        value=300,
        step=50,
        help=(
            "- Higher → better detail\n"
            "- Lower  → faster processing & smaller files"
        )
    )
    compile_latex = st.sidebar.checkbox("Compile LaTeX to PDF", value=True)

    st.markdown("---")
    uploaded_pdf = st.file_uploader("📄 Upload a PDF", type=["pdf"])
    if not uploaded_pdf:
        st.info("Upload a PDF to begin.")
        return

    if st.button("▶️ Process & Generate"):
        pdf_path = save_uploaded_file(uploaded_pdf, suffix=".pdf")

        work_dir    = tempfile.mkdtemp(prefix="pdf2latex_")
        images_dir  = os.path.join(work_dir, "images")
        figures_dir = os.path.join(work_dir, "figures")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(figures_dir, exist_ok=True)

        corrected_pdf = os.path.join(work_dir, "corrected.pdf")
        txt_file      = os.path.join(work_dir, "output.txt")
        tex_file      = os.path.join(work_dir, "paper_itl_final.tex")
        json_path     = os.path.join(work_dir, "analysis.json")

        config = Config()

        with st.spinner("🛠️ Processing PDF…"):
            PDFProcessor(
                pdf_path=pdf_path,
                endpoint=config.doc_intelligence_endpoint,
                key=config.doc_intelligence_key,
                dpi=dpi,
                images_dir=images_dir,
                fig_dir=figures_dir,
                corrected_pdf=corrected_pdf,
                json_path=json_path,
                output_txt=txt_file
            ).process()
        st.success("✅ PDF processing complete.")


        with st.spinner("Generating LaTeX…"):
            latex_body = generate_latex(txt_file, config)
            full_tex = "\n".join([
                r"\documentclass{article}",
                r"\usepackage{amsmath, amssymb, physics, graphicx, float, enumitem}",
                r"\begin{document}",
                latex_body,
                r"\end{document}"
            ])
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(full_tex)
        st.success("✅ LaTeX source created.")


        if compile_latex:
            with st.spinner("Compiling to PDF…"):
                try:
                    res = subprocess.run(
                        ["pdflatex", "-interaction=batchmode", os.path.basename(tex_file)],
                        cwd=work_dir,
                        capture_output=True,
                        text=True
                    )
                    if res.returncode == 0:
                        compiled_pdf = tex_file.replace(".tex", ".pdf")
                        st.success("✅ Here’s your converted PDF:")
                        st.download_button(
                            "Download Converted PDF",
                            data=open(compiled_pdf, "rb").read(),
                            file_name="paper_itl_final.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error(f"Compilation failed:\n{res.stderr}")
                except FileNotFoundError:
                    st.error("`pdflatex` not found. Install TeX Live / MiKTeX and add it to your PATH.")

if __name__ == "__main__":
    main()
