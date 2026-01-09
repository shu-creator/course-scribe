"""File readers for various document formats.

This module handles extraction of text content from different file types.
It's part of the I/O boundary layer, not the core skill logic.

Supported formats:
- .txt, .md: Plain text
- .pdf: PDF documents (with optional OCR for scanned documents)
- .docx: Microsoft Word documents
- .pptx: Microsoft PowerPoint presentations
"""

from pathlib import Path


class FileReadError(Exception):
    """Raised when a file cannot be read."""
    pass


def read_file(path: Path, use_ocr: bool = False) -> str:
    """Read text content from a file.

    Args:
        path: Path to the file
        use_ocr: If True, attempt OCR for PDFs that have no extractable text

    Returns:
        Extracted text content

    Raises:
        FileReadError: If the file cannot be read
    """
    suffix = path.suffix.lower()

    readers = {
        ".txt": _read_text,
        ".md": _read_text,
        ".pdf": lambda p: _read_pdf(p, use_ocr),
        ".docx": _read_docx,
        ".pptx": _read_pptx,
    }

    reader = readers.get(suffix)
    if reader is None:
        raise FileReadError(
            f"Unsupported file format: {suffix}\n"
            f"Supported formats: {', '.join(readers.keys())}"
        )

    try:
        return reader(path)
    except FileReadError:
        raise
    except Exception as e:
        raise FileReadError(f"Failed to read {path}: {e}") from e


def _read_text(path: Path) -> str:
    """Read plain text file."""
    return path.read_text(encoding="utf-8")


def _read_pdf(path: Path, use_ocr: bool = False) -> str:
    """Read PDF file.

    First attempts to extract embedded text.
    If no text found and use_ocr=True, attempts OCR.
    """
    try:
        import pdfplumber
    except ImportError:
        raise FileReadError(
            "pdfplumber is required for PDF files.\n"
            "Install with: pip install pdfplumber"
        )

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    text = "\n".join(text_parts)

    # If no text extracted and OCR requested, try OCR
    if not text.strip() and use_ocr:
        text = _ocr_pdf(path)

    if not text.strip():
        raise FileReadError(
            f"No text could be extracted from {path}.\n"
            "This may be a scanned PDF. Try with --ocr flag."
        )

    return text


def _ocr_pdf(path: Path) -> str:
    """Perform OCR on a PDF file."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        raise FileReadError(
            "OCR requires additional packages.\n"
            "Install with: pip install 'course-scribe[ocr]'\n"
            "Also requires Tesseract OCR to be installed on your system:\n"
            "  - macOS: brew install tesseract tesseract-lang\n"
            "  - Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-jpn\n"
            "  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki"
        )

    try:
        # Convert PDF pages to images
        images = convert_from_path(path)

        text_parts = []
        for i, image in enumerate(images):
            # Perform OCR on each page
            # Use Japanese + English for better results with Japanese documents
            page_text = pytesseract.image_to_string(
                image,
                lang="jpn+eng",  # Japanese + English
            )
            if page_text.strip():
                text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

        return "\n\n".join(text_parts)

    except pytesseract.TesseractNotFoundError:
        raise FileReadError(
            "Tesseract OCR is not installed on your system.\n"
            "Install it first:\n"
            "  - macOS: brew install tesseract tesseract-lang\n"
            "  - Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-jpn\n"
            "  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki"
        )


def _read_docx(path: Path) -> str:
    """Read Microsoft Word document.

    Extracts:
    - All paragraph text
    - Text from tables
    - Headers and footers
    """
    try:
        from docx import Document
    except ImportError:
        raise FileReadError(
            "python-docx is required for Word files.\n"
            "Install with: pip install python-docx"
        )

    doc = Document(path)
    text_parts = []

    # Extract paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)

    # Extract tables
    for table in doc.tables:
        table_text = _extract_table_text(table)
        if table_text:
            text_parts.append(table_text)

    return "\n\n".join(text_parts)


def _extract_table_text(table) -> str:
    """Extract text from a Word table."""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        if any(cells):  # Skip empty rows
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _read_pptx(path: Path) -> str:
    """Read Microsoft PowerPoint presentation.

    Extracts:
    - Slide titles
    - All text from shapes
    - Notes for each slide
    """
    try:
        from pptx import Presentation
    except ImportError:
        raise FileReadError(
            "python-pptx is required for PowerPoint files.\n"
            "Install with: pip install python-pptx"
        )

    prs = Presentation(path)
    slides_text = []

    for slide_num, slide in enumerate(prs.slides, 1):
        slide_parts = [f"=== Slide {slide_num} ==="]

        # Extract title if present
        if slide.shapes.title:
            title_text = slide.shapes.title.text.strip()
            if title_text:
                slide_parts.append(f"# {title_text}")

        # Extract text from all shapes
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                # Skip if already added as title
                if shape == slide.shapes.title:
                    continue
                slide_parts.append(shape.text.strip())

            # Handle tables in slides
            if shape.has_table:
                table_text = _extract_pptx_table(shape.table)
                if table_text:
                    slide_parts.append(table_text)

        # Extract notes
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                slide_parts.append(f"\n[Notes: {notes}]")

        slides_text.append("\n".join(slide_parts))

    return "\n\n".join(slides_text)


def _extract_pptx_table(table) -> str:
    """Extract text from a PowerPoint table."""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def get_supported_formats() -> list[str]:
    """Return list of supported file extensions."""
    return [".txt", ".md", ".pdf", ".docx", ".pptx"]
