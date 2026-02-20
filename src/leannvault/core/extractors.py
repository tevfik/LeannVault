"""
Text extractors for various file formats.

Supports PDF, PPTX, DOCX, and JSON (email) files.
"""

from pathlib import Path
from typing import Optional


def extract_text_from_pptx(file_path: Path) -> Optional[str]:
    """
    Extract text from a PowerPoint file.

    Args:
        file_path: Path to the PPTX file.

    Returns:
        Extracted text or None if extraction failed.
    """
    try:
        from pptx import Presentation
    except ImportError:
        return None

    try:
        prs = Presentation(str(file_path))
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text.strip())
        return "\n".join(texts) if texts else None
    except Exception:
        return None


def extract_text_from_docx(file_path: Path) -> Optional[str]:
    """
    Extract text from a Word document.

    Args:
        file_path: Path to the DOCX file.

    Returns:
        Extracted text or None if extraction failed.
    """
    try:
        from docx import Document
    except ImportError:
        return None

    try:
        doc = Document(str(file_path))
        texts = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        return "\n".join(texts) if texts else None
    except Exception:
        return None


def extract_text_from_pdf(file_path: Path) -> Optional[str]:
    """
    Extract text from a PDF file.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Extracted text or None if extraction failed.
    """
    try:
        import pdfplumber
    except ImportError:
        return None

    try:
        texts = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    texts.append(text.strip())
        return "\n".join(texts) if texts else None
    except Exception:
        return None


def extract_text_from_json_email(file_path: Path) -> Optional[str]:
    """
    Extract text from a JSON email export.

    Args:
        file_path: Path to the JSON file.

    Returns:
        Extracted text or None if extraction failed.
    """
    import json

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        parts = []
        if "subject" in data:
            parts.append(f"Subject: {data['subject']}")
        if "body" in data:
            parts.append(data["body"])
        elif "bodyPreview" in data:
            parts.append(data["bodyPreview"])
        if "from" in data:
            parts.append(f"From: {data['from']}")
        return "\n".join(parts) if parts else None
    except Exception:
        return None
