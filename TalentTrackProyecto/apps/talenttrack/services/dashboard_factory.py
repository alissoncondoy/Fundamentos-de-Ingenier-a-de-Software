"""Compatibility shim.

Real implementation moved to `apps.talenttrack.application.dashboard.factory`.
"""

from ..application.dashboard.factory import DashboardFactory  # noqa

__all__ = ["DashboardFactory"]
