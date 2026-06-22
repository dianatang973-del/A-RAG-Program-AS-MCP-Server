"""
Loader Module.

This package contains document loader components:
- Base loader class
- PDF loader
- DOCX loader
- Markdown loader
- HTML loader
- Loader factory for automatic format detection
- File integrity checker
"""

from src.libs.loader.base_loader import BaseLoader
from src.libs.loader.pdf_loader import PdfLoader
from src.libs.loader.docx_loader import DocxLoader
from src.libs.loader.markdown_loader import MarkdownLoader
from src.libs.loader.html_loader import HtmlLoader
from src.libs.loader.loader_factory import LoaderFactory
from src.libs.loader.file_integrity import FileIntegrityChecker, SQLiteIntegrityChecker

__all__ = [
    "BaseLoader",
    "PdfLoader",
    "DocxLoader",
    "MarkdownLoader",
    "HtmlLoader",
    "LoaderFactory",
    "FileIntegrityChecker",
    "SQLiteIntegrityChecker",
]
