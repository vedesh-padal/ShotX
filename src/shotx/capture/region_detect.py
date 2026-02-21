"""Region detection engine.

Collects detectable regions from multiple sources and provides
hit-testing to find which region the cursor is over.

Sources:
    1. Window manager — top-level windows (from capture backend)
    2. AT-SPI2 — accessible children within windows (buttons, panels, etc.)

The regions are fed to the RegionOverlay for hover highlighting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QRect

from shotx.capture.backend import WindowInfo
from shotx.ui.overlay import DetectRegion

logger = logging.getLogger(__name__)


def build_detect_regions(
    windows: list[WindowInfo],
    include_atspi: bool = True,
) -> list[DetectRegion]:
    """Build a list of detectable regions from all sources.

    Args:
        windows: Top-level windows from the capture backend.
        include_atspi: Whether to query AT-SPI2 for sub-regions.

    Returns:
        List of DetectRegion sorted by area (smallest first).
    """
    regions: list[DetectRegion] = []

    # Tier 1: Top-level windows
    for win in windows:
        if win.width <= 0 or win.height <= 0:
            continue
        regions.append(
            DetectRegion(
                rect=QRect(win.x, win.y, win.width, win.height),
                label=win.title or win.app_name or f"Window {win.window_id}",
                depth=0,
            )
        )

    # Tier 2: AT-SPI2 accessible children
    if include_atspi:
        atspi_regions = _get_atspi_regions()
        regions.extend(atspi_regions)

    # Sort by area (smallest first) for innermost-first hit-testing
    regions.sort(key=lambda r: r.rect.width() * r.rect.height())

    logger.info(
        "Built %d detect regions (%d windows, %d AT-SPI2)",
        len(regions),
        len(windows),
        len(regions) - len(windows),
    )

    return regions


def find_region_at(x: int, y: int, regions: list[DetectRegion]) -> DetectRegion | None:
    """Find the smallest region containing the given point.

    Regions must be pre-sorted by area (smallest first).
    Returns the first (smallest) match, which is the most
    specific region — e.g., a button rather than its parent panel.
    """
    for region in regions:
        if region.rect.contains(x, y):
            return region
    return None


# --- AT-SPI2 integration ---


def _get_atspi_regions() -> list[DetectRegion]:
    """Query AT-SPI2 for accessible widget regions.

    AT-SPI2 (Assistive Technology Service Provider Interface) exposes
    the widget tree of running applications. Each widget (button, panel,
    text field, image) has a bounding rectangle in screen coordinates.

    Requires system packages: python3-gi, gir1.2-atspi-2.0

    Returns empty list if AT-SPI2 is not available.
    """
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
    except (ImportError, ValueError) as e:
        logger.debug("AT-SPI2 not available: %s", e)
        logger.debug("Install: sudo apt install python3-gi gir1.2-atspi-2.0")
        return []

    regions: list[DetectRegion] = []

    try:
        desktop = Atspi.get_desktop(0)
        if desktop is None:
            logger.debug("AT-SPI2: no desktop found")
            return []

        app_count = desktop.get_child_count()
        logger.debug("AT-SPI2: %d applications on desktop", app_count)

        for app_idx in range(app_count):
            try:
                app = desktop.get_child_at_index(app_idx)
                if app is None:
                    continue

                app_name = app.get_name() or f"App {app_idx}"

                # Walk each window of the application
                win_count = app.get_child_count()
                for win_idx in range(win_count):
                    try:
                        window = app.get_child_at_index(win_idx)
                        if window is None:
                            continue

                        # Recursively collect child regions
                        _collect_accessible_regions(
                            window, app_name, regions, depth=1, max_depth=4
                        )
                    except Exception:
                        continue

            except Exception:
                continue

    except Exception as e:
        logger.debug("AT-SPI2 enumeration failed: %s", e)

    return regions


def _collect_accessible_regions(
    node,
    app_name: str,
    regions: list[DetectRegion],
    depth: int,
    max_depth: int,
) -> None:
    """Recursively collect bounding rectangles from an AT-SPI2 node.

    Args:
        node: An Atspi.Accessible object.
        app_name: Parent application name (for labeling).
        regions: List to append DetectRegion objects to.
        depth: Current nesting depth.
        max_depth: Maximum depth to recurse (prevent runaway trees).
    """
    if depth > max_depth:
        return

    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        # Get the role to filter out non-visual elements
        role = node.get_role()

        # Only collect roles that represent visible, bounded regions
        # Skip menus (they may not be displayed), separators, etc.
        visual_roles = {
            Atspi.Role.WINDOW,
            Atspi.Role.FRAME,
            Atspi.Role.PANEL,
            Atspi.Role.FILLER,
            Atspi.Role.PAGE_TAB,
            Atspi.Role.PAGE_TAB_LIST,
            Atspi.Role.SCROLL_PANE,
            Atspi.Role.SPLIT_PANE,
            Atspi.Role.TOOL_BAR,
            Atspi.Role.STATUS_BAR,
            Atspi.Role.DRAWING_AREA,
            Atspi.Role.CANVAS,
            Atspi.Role.IMAGE,
            Atspi.Role.TABLE,
            Atspi.Role.TABLE_CELL,
            Atspi.Role.TREE_TABLE,
            Atspi.Role.PUSH_BUTTON,
            Atspi.Role.TOGGLE_BUTTON,
            Atspi.Role.TEXT,
            Atspi.Role.ENTRY,
            Atspi.Role.DOCUMENT_FRAME,
            Atspi.Role.DOCUMENT_WEB,
            Atspi.Role.HEADING,
            Atspi.Role.SECTION,
            Atspi.Role.FORM,
            Atspi.Role.LIST,
            Atspi.Role.LIST_ITEM,
        }

        if role in visual_roles:
            # Get bounding rectangle
            try:
                component = node.get_component_iface()
                if component is not None:
                    extent = component.get_extents(Atspi.CoordType.SCREEN)
                    x, y, w, h = extent.x, extent.y, extent.width, extent.height

                    # Filter out zero-size or off-screen regions
                    if w > 10 and h > 10 and x >= 0 and y >= 0:
                        name = node.get_name() or ""
                        role_name = node.get_role_name() or ""
                        label = f"{app_name}: {name}" if name else f"{app_name}: {role_name}"

                        regions.append(
                            DetectRegion(
                                rect=QRect(x, y, w, h),
                                label=label,
                                depth=depth,
                            )
                        )
            except Exception:
                pass  # Some nodes don't have Component interface

        # Recurse into children
        child_count = node.get_child_count()
        for i in range(child_count):
            try:
                child = node.get_child_at_index(i)
                if child is not None:
                    _collect_accessible_regions(
                        child, app_name, regions, depth + 1, max_depth
                    )
            except Exception:
                continue

    except Exception:
        pass
