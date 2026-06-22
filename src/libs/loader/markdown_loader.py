"""Markdown Loader implementation.

This module implements Markdown file parsing with image reference extraction.

Features:
- Direct text loading (already in Markdown format)
- Image reference extraction from ![alt](path) syntax
- Title extraction from first heading
- Minimal processing (Markdown is already the target format)
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader

logger = logging.getLogger(__name__)


class MarkdownLoader(BaseLoader):
    """Markdown Loader for .md files.

    This loader:
    1. Reads Markdown text directly (no conversion needed)
    2. Extracts image references from ![alt](path) syntax
    3. Converts image references to [IMAGE: {image_id}] placeholders
    4. Records image metadata in Document.metadata.images

    Configuration:
        extract_images: Enable/disable image reference extraction (default: True)
        image_storage_dir: Base directory for image storage (default: data/images)

    Note: Unlike PDF, Markdown images are references to external files.
          The loader validates image paths but doesn't copy files.
    """

    def __init__(
        self,
        extract_images: bool = True,
        image_storage_dir: str | Path = "data/images"
    ):
        """Initialize Markdown Loader.

        Args:
            extract_images: Whether to extract image references from Markdown.
            image_storage_dir: Base directory for storing image metadata.
        """
        self.extract_images = extract_images
        self.image_storage_dir = Path(image_storage_dir)

    def load(self, file_path: str | Path) -> Document:
        """Load and parse a Markdown file.

        Args:
            file_path: Path to the Markdown file.

        Returns:
            Document with Markdown text and metadata.

        Raises:
            FileNotFoundError: If the Markdown file doesn't exist.
            ValueError: If the file is not a valid Markdown file.
            RuntimeError: If parsing fails critically.
        """
        # Validate file
        path = self._validate_file(file_path)
        if path.suffix.lower() not in ['.md', '.markdown']:
            raise ValueError(f"File is not a Markdown file: {path}")

        # Compute document hash for unique ID
        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"

        # Read Markdown content
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text_content = f.read()
        except UnicodeDecodeError:
            # Fallback to other encodings
            try:
                with open(path, 'r', encoding='latin-1') as f:
                    text_content = f.read()
                logger.warning(f"File {path} read with latin-1 encoding fallback")
            except Exception as e:
                logger.error(f"Failed to read Markdown file {path}: {e}")
                raise RuntimeError(f"Markdown file reading failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to read Markdown file {path}: {e}")
            raise RuntimeError(f"Markdown file reading failed: {e}") from e

        # Initialize metadata
        metadata: Dict[str, Any] = {
            "source_path": str(path),
            "doc_type": "markdown",
            "doc_hash": doc_hash,
        }

        # Extract title from first heading
        title = self._extract_title(text_content)
        if title:
            metadata["title"] = title

        # Handle image extraction
        if self.extract_images:
            try:
                text_content, images_metadata = self._extract_and_process_images(
                    path, text_content, doc_hash
                )
                if images_metadata:
                    metadata["images"] = images_metadata
            except Exception as e:
                logger.warning(
                    f"Image extraction failed for {path}, continuing with text-only: {e}"
                )

        return Document(
            id=doc_id,
            text=text_content,
            metadata=metadata
        )

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content.

        Args:
            file_path: Path to file.

        Returns:
            Hex string of SHA256 hash.
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title from first Markdown heading.

        Args:
            text: Markdown text content.

        Returns:
            Title string if found, None otherwise.
        """
        lines = text.split('\n')

        # Look for first heading (# Title)
        for line in lines[:20]:  # Check first 20 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()

        # Fallback: use first non-empty line
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:100]  # Limit length

        return None

    def _find_code_blocks(self, text: str) -> List[tuple[int, int]]:
        """Find all code block regions in Markdown text.

        Identifies both fenced code blocks (```...```) and indented code blocks.

        Args:
            text: Markdown text content.

        Returns:
            List of (start_pos, end_pos) tuples for code block regions.
        """
        code_blocks = []

        # Find fenced code blocks (``` or ~~~)
        # Pattern: ```...``` or ~~~...~~~
        fenced_pattern = r'(```|~~~).*?\n(.*?)\n\1'
        for match in re.finditer(fenced_pattern, text, re.DOTALL):
            code_blocks.append((match.start(), match.end()))

        # Find indented code blocks (4 spaces or 1 tab at line start)
        # This is more complex, so we'll skip for now to avoid false positives
        # Most modern Markdown uses fenced blocks anyway

        return code_blocks

    def _is_in_code_block(self, position: int, code_blocks: List[tuple[int, int]]) -> bool:
        """Check if a position is inside any code block.

        Args:
            position: Character position in text.
            code_blocks: List of (start, end) tuples for code blocks.

        Returns:
            True if position is inside a code block, False otherwise.
        """
        for start, end in code_blocks:
            if start <= position < end:
                return True
        return False

    def _extract_and_process_images(
        self,
        md_path: Path,
        text_content: str,
        doc_hash: str
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Extract image references from Markdown and convert to placeholders.

        Parses ![alt](path) syntax, validates image paths, and inserts
        [IMAGE: {image_id}] placeholders.

        Excludes images inside code blocks to avoid false positives.

        Args:
            md_path: Path to Markdown file (for resolving relative image paths).
            text_content: Markdown text content.
            doc_hash: Document hash for image ID generation.

        Returns:
            Tuple of (modified_text, images_metadata_list)
        """
        if not self.extract_images:
            logger.debug(f"Image extraction disabled for {md_path}")
            return text_content, []

        images_metadata = []
        modified_text = text_content

        # Find all code blocks first
        code_blocks = self._find_code_blocks(text_content)
        if code_blocks:
            logger.debug(f"Found {len(code_blocks)} code blocks to exclude")

        # Pattern: ![alt text](image_path "optional title")
        # Captures: alt text and image path
        image_pattern = r'!\[([^\]]*)\]\(([^\s\)]+)(?:\s+"[^"]*")?\)'

        matches = list(re.finditer(image_pattern, text_content))

        if not matches:
            logger.debug(f"No images found in {md_path}")
            return text_content, []

        # Filter out matches inside code blocks
        valid_matches = []
        for match in matches:
            if not self._is_in_code_block(match.start(), code_blocks):
                valid_matches.append(match)
            else:
                logger.debug(f"Skipping image in code block at position {match.start()}")

        if not valid_matches:
            logger.debug(f"No valid images found outside code blocks in {md_path}")
            return text_content, []

        # Process matches in reverse order to maintain text offsets
        offset_adjustment = 0

        for img_index, match in enumerate(valid_matches):
            try:
                alt_text = match.group(1)
                image_path_str = match.group(2)
                original_match = match.group(0)
                match_start = match.start()
                match_end = match.end()

                # Resolve image path (relative to Markdown file)
                image_path = self._resolve_image_path(md_path, image_path_str)

                # Generate image ID
                image_id = self._generate_image_id(doc_hash, img_index + 1)

                # Create placeholder
                placeholder = f"[IMAGE: {image_id}]"

                # Replace in text
                modified_text = (
                    modified_text[:match_start + offset_adjustment] +
                    placeholder +
                    modified_text[match_end + offset_adjustment:]
                )

                # Update offset for next replacement
                offset_adjustment += len(placeholder) - len(original_match)

                # Record metadata
                image_metadata = {
                    "id": image_id,
                    "path": str(image_path),
                    "alt_text": alt_text,
                    "text_offset": match_start + offset_adjustment - (len(placeholder) - len(original_match)),
                    "text_length": len(placeholder),
                    "position": {
                        "index": img_index,
                        "original_syntax": original_match
                    }
                }
                images_metadata.append(image_metadata)

                logger.debug(f"Extracted image reference: {image_id} -> {image_path}")

            except Exception as e:
                logger.warning(f"Failed to process image {img_index} in {md_path}: {e}")
                continue

        if images_metadata:
            logger.info(f"Extracted {len(images_metadata)} image references from {md_path}")

        return modified_text, images_metadata

    def _resolve_image_path(self, md_path: Path, image_path_str: str) -> Path:
        """Resolve image path relative to Markdown file.

        Args:
            md_path: Path to Markdown file.
            image_path_str: Image path from Markdown (may be relative or absolute).

        Returns:
            Resolved absolute path to image.
        """
        # Handle absolute paths and URLs
        if image_path_str.startswith(('http://', 'https://', '/')):
            # For URLs or absolute paths, return as-is
            return Path(image_path_str)

        # Resolve relative path
        md_dir = md_path.parent
        resolved_path = (md_dir / image_path_str).resolve()

        return resolved_path

    @staticmethod
    def _generate_image_id(doc_hash: str, sequence: int) -> str:
        """Generate unique image ID.

        Args:
            doc_hash: Document hash.
            sequence: Image sequence (1-based).

        Returns:
            Unique image ID string.
        """
        return f"{doc_hash[:8]}_img_{sequence}"
