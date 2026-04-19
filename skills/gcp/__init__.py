"""GCP Cloud Provider Skill for OpenSRE."""

try:
    from .skill import GCPSkill
    __all__ = ["GCPSkill"]
except ImportError:
    # Google Cloud SDK not installed
    GCPSkill = None  # type: ignore
    __all__ = []
