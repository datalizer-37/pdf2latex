import os
import re
from langchain_openai import AzureChatOpenAI

class Config:
    def __init__(self):
        self.azure_endpoint = os.getenv("AZURE_ENDPOINT")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_api_version = os.getenv("OPENAI_API_VERSION")
        self.azure_model_name = os.getenv("AZURE_MODEL_NAME", "gpt-4o-mini")
        self.doc_intelligence_endpoint = os.getenv("DOC_INTELLIGENCE_ENDPOINT")
        self.doc_intelligence_key = os.getenv("DOC_INTELLIGENCE_KEY")

        required = [
            ('AZURE_ENDPOINT', self.azure_endpoint),
            ('OPENAI_API_KEY', self.openai_api_key),
            ('OPENAI_API_VERSION', self.openai_api_version),
            ('DOC_INTELLIGENCE_ENDPOINT', self.doc_intelligence_endpoint),
            ('DOC_INTELLIGENCE_KEY', self.doc_intelligence_key),
        ]
        missing = [name for name, val in required if not val]
        if missing:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

def strip_code_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
    s = re.sub(r"```$", "", s)
    return s.strip()

def read_text_file(txt_path: str) -> str:
    print(f"Opening text file: {txt_path}")
    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"Text file not found at {txt_path}")
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        raise ValueError(f"Text file {txt_path} is empty")
    print("Text file content read successfully.")
    return content

def generate_latex(txt_path: str, config: Config) -> str:
    text_content = read_text_file(txt_path)
    print("Initializing AzureChatOpenAI LLM...")
    llm = AzureChatOpenAI(
        deployment_name=config.azure_model_name,
        azure_endpoint=config.azure_endpoint.rstrip("/"),
        openai_api_key=config.openai_api_key,
        openai_api_version=config.openai_api_version,
        temperature=0.1,
        max_tokens=7000,
    )
    print("LLM initialized.")
    

    prompt = fr"""
    You are a LaTeX expert tasked with converting raw text from a physics exam paper into a well-structured LaTeX document. The input text contains sections, questions, and figure references in the format [FIGURE: figures/figure_X_Y.png]. Your job is to produce **LaTeX body content only** (no \documentclass, \usepackage, \begin{{document}}, or \end{{document}}) with the following requirements:

    **Instructions**

    1. **Structure and Formatting**
       - Identify sections (e.g., "SECTION - A", "SECTION - B") and format them as \section*{{Section A}}, \section*{{Section B}}, etc.
       - Identify questions (e.g., lines starting with a number like "1", "2") and format them using \begin{{enumerate}} and \item. Nest sub-questions (e.g., "(i)", "(ii)") using a nested \begin{{enumerate}}[label=(roman*)]. For example:
       - Format multiple-choice options (e.g., "(a)", "(b)") as a nested \begin{{enumerate}}[label=(alph*)] with each option as an \item.
       - Preserve general instructions and other text as paragraphs, using \textbf{{}} for headings like "General Instructions:" and ensuring proper spacing with \vspace{{1em}} between sections and questions where appropriate.
       - Use \textbf{{}} for headings like "ITL PUBLIC SCHOOL", "PHYSICS (042)", etc., and \hfill for aligning text like "Class: XII \hfill Date: ...".
       - Use \begin{{itemize}} for bulleted lists (e.g., instructions starting with ">").

    2. **Math and Physics Notation**
       - Ensure inline math is wrapped in $...$ (e.g., $x = 5$).
       - Ensure display math is wrapped in $$...$$ (e.g., $$E = mc^2$$).
       - Use proper physics notation:
         - Vectors: \vec{{v}}, \vec{{E}}, \vec{{p}}
         - Unit vectors: \hat{{v}}, \hat{{E}}
         - Matrices: \mathbf{{E}}, \mathbf{{v}}
         - Dot product: \vec{{E}}\cdot\vec{{p}}
         - Cross product: \vec{{E}}\times\vec{{p}}
         - Any ordinary word used as a vector: \vec{{word}}
       - Fix any incorrect or missing math notation (e.g., convert plain "E" to $\vec{{E}}$ if it's a vector in context, use $\mu\text{{C}}$ for microcoulombs).

    3. **Fix OCR and Formatting Errors**
       - Correct common OCR errors (e.g., "chqarges" to "charges", "nto be zero" to "to be zero").
       - Fix typos in the text (e.g., "Aderliga" might be a misspelling; correct it to a plausible word like "Adelriga" if it’s clearly wrong, but leave it if unsure).
       - Ensure proper LaTeX escaping (e.g., replace "&" with "\&" in text mode, use "\%" for percentages).
       - Remove stray ":selected:" tags or other artifacts from the OCR process.

    4. **Figure Handling**
       - The text contains figure references in the format [FIGURE: figures/figure_X_Y.png], which may appear anywhere in the text, including within case studies, sections, or questions.
       - *Every single [FIGURE: ...]* reference must be converted into a LaTeX figure block, preserving its exact placement in the text, even if it appears in a case study, between questions, or after an equation.
         \begin{{figure}}[H]
         \centering
         \includegraphics[width=0.8\textwidth]{{figures/figure_X_Y}}
         \caption{{A meaningful caption based on the context of the preceding question, section, or case study}}
         \label{{fig:fig<N>}}
         \end{{figure}}
       - Remove the ".png" extension from the figure path (e.g., [FIGURE: figures/figure_1_0.png] becomes \includegraphics[width=0.8\textwidth]{{figures/figure_1_0}}).
       - Generate a meaningful caption based on the surrounding context. For example:
         - If the figure follows a question about capacitors, use a caption like "Circuit diagram of capacitor combination."
         - If in a case study about equipotential surfaces, use a caption like "Equipotential surfaces and lines of force for a point charge."
       - Assign a unique label incrementing for each figure (e.g., \label{{fig:fig1}} for the first figure, \label{{fig:fig2}} for the second, etc.).
       - Ensure the figure block is inserted exactly where the [FIGURE: ...] appears in the text, even in complex sections like case studies, to maintain the document's structure. Do not skip any figures, even if they appear in unexpected places.

    5. **Output**
       - Return the cleaned and perfected LaTeX body content only (no \documentclass, \usepackage, \begin{{document}}, or \end{{document}}).
       - Ensure the output is ready to be wrapped in a full LaTeX document with the preamble:
         \documentclass{{article}}
         \usepackage{{amsmath, amssymb, physics, graphicx, float, enumitem}}

    **Input Text Content**

    {text_content}

    **Begin Converting to LaTeX**
    """

    print("Sending text content to LLM for LaTeX conversion...")
    ai_resp = llm.invoke(prompt)
    raw = ai_resp.content if hasattr(ai_resp, "content") else str(ai_resp)
    latex_content = strip_code_fences(raw)
    print("LLM processing complete. Text converted to LaTeX.")
    return latex_content