"""Factory for creating Loader instances.

This module implements the Factory Pattern to instantiate the appropriate
Loader provider based on file extension, enabling automatic format detection
and selection of different document loaders without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.libs.loader.base_loader import BaseLoader

if TYPE_CHECKING:
    from src.core.settings import Settings


class LoaderFactory:
    """Factory for creating Loader provider instances.

    This factory automatically selects the appropriate Loader based on file
    extension, enabling seamless support for multiple document formats.

    Design Principles Applied:
    - Factory Pattern: Centralizes object creation logic.
    - Extension-Driven: Automatic loader selection based on file type.
    - Fail-Fast: Raises clear errors for unsupported formats.

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings()
        >>> loader = LoaderFactory.create_for_file(
        ...     "document.pdf",
        ...     settings,
        ...     extract_images=True
        ... )
        >>> document = loader.load("document.pdf")
    """

    # Registry: file extension -> Loader class
    _PROVIDERS: dict[str, type[BaseLoader]] = {}

    @classmethod
    def register_provider(
        cls, extension: str, provider_class: type[BaseLoader]
    ) -> None:
        """Register a Loader provider for a specific file extension.

        Args:
            extension: File extension (e.g., 'pdf', 'docx', 'md').
                       Leading dot is optional and will be normalized.
            provider_class: The BaseLoader subclass implementing the provider.

        Raises:
            ValueError: If provider_class doesn't inherit from BaseLoader.

        Example:
            >>> LoaderFactory.register_provider('pdf', PdfLoader)
            >>> LoaderFactory.register_provider('.docx', DocxLoader)
        """
        if not issubclass(provider_class, BaseLoader):
            raise ValueError(
                f"Provider class {provider_class.__name__} must inherit from BaseLoader"
            )

        # Normalize extension: remove leading dot, convert to lowercase
        normalized_ext = extension.lstrip(".").lower()
        cls._PROVIDERS[normalized_ext] = provider_class

    @classmethod
    def create_for_file(
        cls,
        file_path: str | Path,
        settings: Settings | None = None,
        **loader_kwargs: Any,
    ) -> BaseLoader:
        """Create a Loader instance based on file extension.

        Automatically detects the file type from the extension and instantiates
        the appropriate Loader implementation.

        Args:
            file_path: Path to the file to be loaded.
            settings: Optional application settings (may be required by some loaders).
            **loader_kwargs: Additional keyword arguments passed to the Loader constructor.

        Returns:
            An instance of the appropriate Loader for the file type.

        Raises:
            ValueError: If the file extension is not supported.
            FileNotFoundError: If the file doesn't exist.

        Example:
            >>> loader = LoaderFactory.create_for_file(
            ...     "report.pdf",
            ...     extract_images=True,
            ...     image_storage_dir="data/images"
            ... )
            >>> document = loader.load("report.pdf")
        """
        path = Path(file_path)

        # Validate file exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Extract and normalize extension
        extension = path.suffix.lstrip(".").lower()

        if not extension:
            raise ValueError(
                f"Cannot determine file type: '{path}' has no extension"
            )

        # Look up provider class
        provider_class = cls._PROVIDERS.get(extension)

        if provider_class is None:
            available = ", ".join(sorted(cls._PROVIDERS.keys())) if cls._PROVIDERS else "none"
            raise ValueError(
                f"Unsupported file format: '.{extension}'. "
                f"Available formats: {available}. "
                f"File: {path}"
            )

        # Instantiate the loader
        try:
            return provider_class(**loader_kwargs)
        except Exception as e:
            raise RuntimeError(
                f"Failed to instantiate Loader for '.{extension}' format: {e}"
            ) from e

    @classmethod
    def list_supported_extensions(cls) -> list[str]:
        """List all supported file extensions.

        Returns:
            Sorted list of supported file extensions (without leading dot).

        Example:
            >>> LoaderFactory.list_supported_extensions()
            ['pdf']
        """
        return sorted(cls._PROVIDERS.keys())

    @classmethod
    def is_supported(cls, file_path: str | Path) -> bool:
        """Check if a file format is supported.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file format is supported, False otherwise.

        Example:
            >>> LoaderFactory.is_supported("document.pdf")
            True
            >>> LoaderFactory.is_supported("document.xyz")
            False
        """
        path = Path(file_path)
        extension = path.suffix.lstrip(".").lower()
        return extension in cls._PROVIDERS


# Auto-register built-in providers when module is imported
def _register_builtin_providers() -> None:
    """Register built-in Loader providers with the factory.

    This function is called automatically when the module is imported.
    It registers all available loader implementations.
    """
    # Import here to avoid circular imports and handle missing dependencies gracefully
    try:
        from src.libs.loader.pdf_loader import PdfLoader
        LoaderFactory.register_provider("pdf", PdfLoader)
    except ImportError:
        pass  # PdfLoader not available (missing dependencies)

    try:
        from src.libs.loader.docx_loader import DocxLoader
        LoaderFactory.register_provider("docx", DocxLoader)
    except ImportError:
        pass  # DocxLoader not available (missing dependencies)

    try:
        from src.libs.loader.markdown_loader import MarkdownLoader
        LoaderFactory.register_provider("md", MarkdownLoader)
        LoaderFactory.register_provider("markdown", MarkdownLoader)
    except ImportError:
        pass  # MarkdownLoader not available

    try:
        from src.libs.loader.html_loader import HtmlLoader
        LoaderFactory.register_provider("html", HtmlLoader)
        LoaderFactory.register_provider("htm", HtmlLoader)
    except ImportError:
        pass  # HtmlLoader not available (missing dependencies)


# Register providers when module is imported
_register_builtin_providers()

