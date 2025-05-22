FROM python:3.12-slim

# Ensure Python prints straight to stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && \
    \
    # TeX + Pandoc
    apt-get install -y --no-install-recommends \
      pandoc \
      texlive-latex-base \
      texlive-latex-extra \
      texlive-fonts-recommended \
    && \
    # Core LaTeX engine & driver
    apt-get install -y --no-install-recommends \
      texlive-binaries \
      latexmk \
      texlive-fonts-extra \
    && \
    # PDF→image & OCR tools
    apt-get install -y --no-install-recommends \
      poppler-utils \
      ghostscript \
      tesseract-ocr \
      libtesseract-dev \
      libleptonica-dev \
      pkg-config \
    && \
    # OpenCV deps & build tools
    apt-get install -y --no-install-recommends \
      libgl1-mesa-glx \
      libglib2.0-0 \
      build-essential \
    && \
    # Clean up
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8501

ENTRYPOINT ["streamlit","run","pdf_pipeline.py","--server.port=8501","--server.address=0.0.0.0"]
