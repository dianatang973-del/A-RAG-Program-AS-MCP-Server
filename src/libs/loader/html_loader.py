"""HTML Loader implementation.

This module implements HTML file parsing with conversion to Markdown.

Features:
- HTML to Markdown conversion via html2text
- Script/style tag removal and content cleaning
- Image extraction from <img> tags
- Title extraction from <title> or <h1> tags
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader

logger = logging.getLogger(__name__)


class HtmlLoader(BaseLoader):
    """HTML Loader using html2text for Markdown conversion.

    This loader:
    1. Cleans HTML (removes script, style, comments)
    2. Converts HTML to Markdown using html2text
    3. Extracts images from <img> tags
    4. Inserts image placeholders in the format [IMAGE: {image_id}]
    5. Records image metadata in Document.metadata.images

    Configuration:
        extract_images: Enable/disable image extraction (default: True)
        image_storage_dir: Base directory for image storage (default: data/images)

    Dependencies:
        - html2text: For HTML to Markdown conversion
        - beautifulsoup4: For HTML parsing and cleaning
    """

    def __init__(
        self,
        extract_images: bool = True,
        image_storage_dir: str | Path = "data/images"
    ):
        """Initialize HTML Loader.

        Args:
            extract_images: Whether to extract images from HTML.
            image_storage_dir: Base directory for storing image metadata.

        Raises:
            ImportError: If required dependencies are not installed.
        """
        if not HTML2TEXT_AVAILABLE:
            raise ImportError(
                "html2text is required for HtmlLoader. "
                "Install with: pip install html2text"
            )

        if not BS4_AVAILABLE:
            raise ImportError(
                "beautifulsoup4 is required for HtmlLoader. "
                "Install with: pip install beautifulsoup4"
            )

        self.extract_images = extract_images
        self.image_storage_dir = Path(image_storage_dir)

        # Configure html2text converter
        self._html_converter = html2text.HTML2Text()
        self._html_converter.ignore_links = False
        self._html_converter.ignore_images = True  # We handle images manually
        self._html_converter.ignore_emphasis = False
        self._html_converter.body_width = 0  # No line wrapping
        self._html_converter.unicode_snob = True
        self._html_converter.skip_internal_links = True

        # Table handling configuration
        self._html_converter.bypass_tables = False  # Convert tables to Markdown
        self._html_converter.ignore_tables = False  # Don't skip tables
        # html2text will convert HTML tables to Markdown table format

    def load(self, file_path: str | Path) -> Document:
        """Load and parse an HTML file.

        Args:
            file_path: Path to the HTML file.

        Returns:
            Document with Markdown text and metadata.

        Raises:
            FileNotFoundError: If the HTML file doesn't exist.
            ValueError: If the file is not a valid HTML file.
            RuntimeError: If parsing fails critically.
        """
        # Validate file
        path = self._validate_file(file_path)
        if path.suffix.lower() not in ['.html', '.htm']:
            raise ValueError(f"File is not an HTML file: {path}")

        # Compute document hash for unique ID
        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"

        # Read HTML content
        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except UnicodeDecodeError:
            # Fallback to other encodings
            try:
                with open(path, 'r', encoding='latin-1') as f:
                    html_content = f.read()
                logger.warning(f"File {path} read with latin-1 encoding fallback")
            except Exception as e:
                logger.error(f"Failed to read HTML file {path}: {e}")
                raise RuntimeError(f"HTML file reading failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to read HTML file {path}: {e}")
            raise RuntimeError(f"HTML file reading failed: {e}") from e

        # Parse and clean HTML
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract title before cleaning
            title = self._extract_title(soup)

            # Clean HTML (remove script, style, comments)
            cleaned_html = self._clean_html(soup)

        except Exception as e:
            logger.error(f"Failed to parse HTML {path}: {e}")
            raise RuntimeError(f"HTML parsing failed: {e}") from e

        # Initialize metadata
        metadata: Dict[str, Any] = {
            "source_path": str(path),
            "doc_type": "html",
            "doc_hash": doc_hash,
        }

        if title:
            metadata["title"] = title

        # Extract images before conversion
        images_info = []
        if self.extract_images:
            images_info = self._extract_images_from_soup(soup, doc_hash)

        # Convert to Markdown
        try:
            markdown_text = self._html_converter.handle(str(cleaned_html))
        except Exception as e:
            logger.error(f"Failed to convert HTML to Markdown {path}: {e}")
            raise RuntimeError(f"HTML to Markdown conversion failed: {e}") from e

        # Insert image placeholders
        if images_info:
            markdown_text, images_metadata = self._insert_image_placeholders(
                markdown_text, images_info
            )
            if images_metadata:
                metadata["images"] = images_metadata

        return Document(
            id=doc_id,
            text=markdown_text,
            metadata=metadata
        )

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from HTML.

        Priority: <title> tag > first <h1> tag > None

        Args:
            soup: BeautifulSoup parsed HTML.

        Returns:
            Title string if found, None otherwise.
        """
        # Try <title> tag first
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # Try first <h1> tag
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()

        return None

    def _clean_html(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Clean HTML by removing unwanted elements.

        Removes:
        - <script> tags
        - <style> tags
        - HTML comments
        - <noscript> tags

        Args:
            soup: BeautifulSoup parsed HTML.

        Returns:
            Cleaned BeautifulSoup object.
        """
        # Remove script tags
        for script in soup.find_all('script'):
            script.decompose()

        # Remove style tags
        for style in soup.find_all('style'):
            style.decompose()

        # Remove comments
        from bs4 import Comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove noscript tags
        for noscript in soup.find_all('noscript'):
            noscript.decompose()

        return soup

    def _extract_images_from_soup(
        self,
        soup: BeautifulSoup,
        doc_hash: str
    ) -> List[Dict[str, Any]]:
        """Extract image information from HTML.

        Args:
            soup: BeautifulSoup parsed HTML.
            doc_hash: Document hash for image ID generation.

        Returns:
            List of image info dictionaries.
        """
        images_info = []

        img_tags = soup.find_all('img')

        for img_index, img_tag in enumerate(img_tags):
            try:
                # Get image source
                src = img_tag.get('src', '')
                if not src:
                    continue

                # Get alt text
                alt_text = img_tag.get('alt', '')

                # Generate image ID
                image_id = self._generate_image_id(doc_hash, img_index + 1)

                # Store image info
                image_info = {
                    "id": image_id,
                    "src": src,
                    "alt_text": alt_text,
                    "index": img_index
                }
                images_info.append(image_info)

            except Exception as e:
                logger.warning(f"Failed to extract image {img_index}: {e}")
                continue

        if images_info:
            logger.info(f"Extracted {len(images_info)} images from HTML")

        return images_info

    def _insert_image_placeholders(
        self,
        markdown_text: str,
        images_info: List[Dict[str, Any]]
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Insert image placeholders into Markdown text.

        Args:
            markdown_text: Converted Markdown text.
            images_info: List of image information.

        Returns:
            Tuple of (modified_text, images_metadata_list)
        """
        images_metadata = []

        # Append image placeholders at the end
        # (since html2text doesn't preserve exact image positions)
        modified_text = markdown_text

        for image_info in images_info:
            image_id = image_info["id"]
            placeholder = f"\n[IMAGE: {image_id}]\n"

            # Insert placeholder
            text_offset = len(modified_text)
            modified_text += placeholder

            # Create metadata
            image_metadata = {
                "id": image_id,
                "path": image_info["src"],  # Original src (may be URL or relative path)
                "alt_text": image_info.get("alt_text", ""),
                "text_offset": text_offset,
                "text_length": len(placeholder.strip()),
                "position": {
                    "index": image_info["index"]
                }
            }
            images_metadata.append(image_metadata)

        return modified_text, images_metadata

    @staticmethod
    def _generate_image_id(doc_hash: str, sequence: int) -> str:
        """Generate unique image ID."""
        return f"{doc_hash[:8]}_img_{sequence}"
