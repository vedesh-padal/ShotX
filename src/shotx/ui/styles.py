"""Shared QSS Styles for ShotX UI components.

Arrow icons are written as tiny SVG files to a cache directory because
Qt's QSS `image:` property only accepts file paths — inline data URIs
are silently ignored.
"""

import os
import tempfile

# ---------------------------------------------------------------------------
# Arrow SVG generation
# ---------------------------------------------------------------------------

_ARROW_COLOR = "dcddde"  # light gray matching the dark theme text

_SVG_DOWN = (
    "<svg width='12' height='12' viewBox='0 0 12 12' "
    "xmlns='http://www.w3.org/2000/svg'>"
    "<path d='M2 4 L6 8 L10 4' stroke='#{color}' stroke-width='2' "
    "fill='none' stroke-linecap='round' stroke-linejoin='round'/>"
    "</svg>"
)

_SVG_UP = (
    "<svg width='10' height='10' viewBox='0 0 10 10' "
    "xmlns='http://www.w3.org/2000/svg'>"
    "<path d='M2 7 L5 3 L8 7' stroke='#{color}' stroke-width='2' "
    "fill='none' stroke-linecap='round' stroke-linejoin='round'/>"
    "</svg>"
)

_SVG_DOWN_SMALL = (
    "<svg width='10' height='10' viewBox='0 0 10 10' "
    "xmlns='http://www.w3.org/2000/svg'>"
    "<path d='M2 3 L5 7 L8 3' stroke='#{color}' stroke-width='2' "
    "fill='none' stroke-linecap='round' stroke-linejoin='round'/>"
    "</svg>"
)


def _ensure_arrow_svgs() -> dict[str, str]:
    """Write arrow SVGs to a cache dir and return their absolute paths."""
    cache_dir = os.path.join(tempfile.gettempdir(), "shotx_icons")
    os.makedirs(cache_dir, exist_ok=True)

    arrows: dict[str, tuple[str, str]] = {
        "combo_down": ("combo_down.svg", _SVG_DOWN),
        "spin_up": ("spin_up.svg", _SVG_UP),
        "spin_down": ("spin_down.svg", _SVG_DOWN_SMALL),
    }

    paths: dict[str, str] = {}
    for key, (filename, template) in arrows.items():
        filepath = os.path.join(cache_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write(template.format(color=_ARROW_COLOR))
        paths[key] = filepath.replace("\\", "/")
    return paths


# ---------------------------------------------------------------------------
# QSS construction
# ---------------------------------------------------------------------------

def _build_settings_qss() -> str:
    """Build the full QSS string with correct file-path references."""
    p = _ensure_arrow_svgs()
    return f"""
QDialog {{
    background-color: #313338;
    color: #dcddde;
}}

QListWidget {{
    border: none;
    background-color: #2b2d31;
    border-radius: 6px;
    font-size: 14px;
    outline: none;
    color: #949ba4;
}}

QListWidget::item {{
    padding: 10px 14px;
    border-radius: 4px;
    margin: 4px 6px;
}}

QListWidget::item:hover {{
    background-color: rgba(255, 255, 255, 0.08);
    color: #dbdee1;
}}

QListWidget::item:selected {{
    background-color: #4752c4;
    color: #ffffff;
    font-weight: bold;
}}

QGroupBox {{
    font-weight: bold;
    border: 1px solid #1e1f22;
    border-radius: 8px;
    margin-top: 20px;
    background-color: #2b2d31;
    color: #dcddde;
    padding-top: 16px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 4px;
    padding: 0 4px;
    color: #f2f3f5;
    background-color: transparent;
}}

QLabel {{
    color: #dcddde;
}}

QCheckBox {{
    color: #dcddde;
    padding: 2px;
}}

QPushButton {{
    background-color: #4e5058;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    color: #ffffff;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: #6d6f78;
}}

QPushButton:pressed {{
    background-color: #404249;
}}

QLineEdit, QSpinBox, QComboBox {{
    border: 1px solid #1e1f22;
    border-radius: 6px;
    padding: 6px 8px;
    background-color: #1e1f22;
    color: #dbdee1;
    selection-background-color: #4752c4;
    selection-color: #ffffff;
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid #5865f2;
}}

/* ---- QComboBox arrow ---- */

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: url({p["combo_down"]});
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: #2b2d31;
    border: 1px solid #1e1f22;
    selection-background-color: #4752c4;
    color: #dcddde;
}}

/* ---- QSpinBox arrows ---- */

QSpinBox::up-button {{
    border: none;
    background-color: transparent;
    width: 20px;
}}

QSpinBox::down-button {{
    border: none;
    background-color: transparent;
    width: 20px;
}}

QSpinBox::up-arrow {{
    image: url({p["spin_up"]});
    width: 10px;
    height: 10px;
}}

QSpinBox::down-arrow {{
    image: url({p["spin_down"]});
    width: 10px;
    height: 10px;
}}
"""


# Module-level constant — ready to use via `from shotx.ui.styles import SETTINGS_QSS`
SETTINGS_QSS = _build_settings_qss()
