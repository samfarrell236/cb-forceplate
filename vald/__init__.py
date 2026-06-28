"""VALD data-access package: loader (CSV now / API later) + canonical schema."""
from . import schema  # noqa: F401
from .loader import get_tests, detect_mapping  # noqa: F401
