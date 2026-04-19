"""Azure Cloud Provider Skill for OpenSRE."""

try:
    from .skill import AzureSkill
    __all__ = ["AzureSkill"]
except ImportError:
    # Azure SDK not installed
    AzureSkill = None  # type: ignore
    __all__ = []
