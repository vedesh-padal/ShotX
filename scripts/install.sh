#!/usr/bin/env bash
# ShotX Installer
# Usage: curl -sSL https://raw.githubusercontent.com/vedesh-padal/ShotX/main/scripts/install.sh | sh
#
# Supports: Ubuntu/Debian (apt), Fedora/RHEL/CentOS (dnf/yum), Arch/Manjaro (pacman),
#           openSUSE (zypper), Alpine (apk)
# Requires: bash, git, Python 3.10+, internet connection
#
# After install, run: shotx

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_URL="https://github.com/vedesh-padal/ShotX.git"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/shotx"
BIN_DIR="${HOME}/.local/bin"
LAUNCHER="${BIN_DIR}/shotx"
DESKTOP_FILE="${HOME}/.config/autostart/shotx.desktop"
PYTHON_MIN="3.10"

# ---------------------------------------------------------------------------
# Color output helpers (gracefully degraded if not a TTY)
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' BOLD='' RESET=''
fi

info()    { printf "${CYAN}[ShotX]${RESET} %s\n" "$*"; }
success() { printf "${GREEN}[ShotX] ✓${RESET} %s\n" "$*"; }
warn()    { printf "${YELLOW}[ShotX] ⚠${RESET} %s\n" "$*"; }
die()     { printf "${RED}[ShotX] ✗${RESET} %s\n" "$*" >&2; exit 1; }
step()    { printf "\n${BOLD}━━━ %s${RESET}\n" "$*"; }

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
check_command() {
    command -v "$1" >/dev/null 2>&1
}

require_command() {
    if ! check_command "$1"; then
        die "Required command '${1}' not found. Please install it and re-run this script."
    fi
}

check_python_version() {
    local python_bin="$1"
    local version
    version=$("$python_bin" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || true)
    if [ -z "$version" ]; then
        return 1
    fi
    # Compare major.minor numerically
    local major minor min_major min_minor
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)
    min_major=$(echo "$PYTHON_MIN" | cut -d. -f1)
    min_minor=$(echo "$PYTHON_MIN" | cut -d. -f2)
    if [ "$major" -gt "$min_major" ] || { [ "$major" -eq "$min_major" ] && [ "$minor" -ge "$min_minor" ]; }; then
        return 0
    fi
    return 1
}

find_python() {
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if check_command "$candidate" && check_python_version "$candidate"; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

# ---------------------------------------------------------------------------
# Package manager detection & dependency installation
# ---------------------------------------------------------------------------
detect_pm() {
    if check_command apt-get; then   echo "apt"
    elif check_command dnf;       then echo "dnf"
    elif check_command yum;       then echo "yum"
    elif check_command pacman;    then echo "pacman"
    elif check_command zypper;    then echo "zypper"
    elif check_command apk;       then echo "apk"
    else                               echo "unknown"
    fi
}

install_system_deps() {
    local pm="$1"
    step "Installing system dependencies (${pm})"

    case "$pm" in
        apt)
            info "Updating package lists..."
            sudo apt-get update -qq
            sudo apt-get install -y --no-install-recommends \
                git python3 python3-pip \
                libcairo2-dev pkg-config \
                gobject-introspection \
                libglib2.0-dev \
                libegl1 libgl1 libopengl0 \
                libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
                libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
                libxcb-shape0 libxcb-xfixes0 libxcb-xinerama0 \
                libxcb-xkb1 libxkbcommon-x11-0 libdbus-1-3 \
                wl-clipboard xclip \
                || true  # non-fatal: xclip/wl-clipboard may not exist on all systems
            # libgirepository package name differs by Ubuntu version
            if apt-cache show libgirepository-2.0-dev >/dev/null 2>&1; then
                sudo apt-get install -y --no-install-recommends libgirepository-2.0-dev
            else
                sudo apt-get install -y --no-install-recommends libgirepository1.0-dev || true
            fi
            ;;
        dnf)
            sudo dnf install -y --setopt=install_weak_deps=False \
                git python3 python3-pip \
                cairo-devel pkgconf-pkg-config \
                gobject-introspection-devel \
                mesa-libGL mesa-libEGL \
                libxcb xcb-util-wm xcb-util-image xcb-util-keysyms \
                xcb-util-cursor xkbcommon-x11 dbus-libs \
                wl-clipboard xclip
            ;;
        yum)
            # RHEL/CentOS fallback — dnf preferred
            sudo yum install -y \
                git python3 python3-pip \
                cairo-devel pkgconfig \
                gobject-introspection-devel \
                mesa-libGL mesa-libEGL \
                libxcb xkbcommon-x11 dbus-libs
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --needed \
                git python python-pip \
                cairo pkgconf \
                gobject-introspection \
                mesa \
                xcb-util-wm xcb-util-image xcb-util-keysyms \
                xcb-util-cursor libxkbcommon-x11 dbus \
                wl-clipboard xclip
            ;;
        zypper)
            sudo zypper install -y --no-recommends \
                git python3 python3-pip \
                cairo-devel pkgconf \
                gobject-introspection-devel \
                Mesa-libGL Mesa-libEGL \
                libxcb-devel xkbcommon-x11 dbus-1 \
                wl-clipboard xclip
            ;;
        apk)
            # Alpine Linux (musl-based) — minimal support
            sudo apk add --no-cache \
                git python3 py3-pip \
                cairo-dev pkgconf \
                gobject-introspection-dev \
                mesa-gl mesa-egl \
                libxcb libxkbcommon dbus \
                wl-clipboard
            ;;
        *)
            warn "Could not detect a supported package manager."
            warn "Please manually install the system dependencies listed at:"
            warn "  https://shotx.vedeshpadal.me/getting-started/installation/"
            ;;
    esac

    success "System dependencies installed."
}

# ---------------------------------------------------------------------------
# uv installation
# ---------------------------------------------------------------------------
install_uv() {
    step "Installing uv (Python package manager)"
    if check_command uv; then
        local version
        version=$(uv --version) || true
        success "uv already installed (${version})"
        return
    fi
    info "Downloading uv installer..."
    if check_command curl; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif check_command wget; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        die "Neither 'curl' nor 'wget' found. Cannot download uv."
    fi

    # Add uv to PATH for the rest of this script
    export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

    if ! check_command uv; then
        die "uv installation failed. Please install uv manually: https://docs.astral.sh/uv/"
    fi
    success "uv installed successfully."
}

# ---------------------------------------------------------------------------
# ShotX installation
# ---------------------------------------------------------------------------
install_shotx() {
    step "Installing ShotX from source"

    if [ -d "${INSTALL_DIR}/.git" ]; then
        info "Existing installation found at ${INSTALL_DIR}. Updating..."
        git -C "${INSTALL_DIR}" fetch --tags origin
        git -C "${INSTALL_DIR}" checkout main
        git -C "${INSTALL_DIR}" pull --ff-only
    else
        info "Cloning ShotX repository to ${INSTALL_DIR}..."
        mkdir -p "$(dirname "${INSTALL_DIR}")"
        git clone --depth=1 "${REPO_URL}" "${INSTALL_DIR}"
    fi

    info "Creating / updating virtual environment..."
    uv sync --project "${INSTALL_DIR}" --group all 2>&1 | grep -v "^$" || true

    success "ShotX installed to ${INSTALL_DIR}"
}

create_launcher() {
    step "Creating launcher script at ${LAUNCHER}"
    mkdir -p "${BIN_DIR}"
    cat > "${LAUNCHER}" <<EOF
#!/usr/bin/env bash
# ShotX launcher — auto-generated by install.sh
exec uv run --project "${INSTALL_DIR}" python -m shotx.main "\$@"
EOF
    chmod +x "${LAUNCHER}"
    success "Launcher created: ${LAUNCHER}"
}

setup_autostart() {
    step "Setting up XDG autostart entry"
    if [ -n "${SKIP_AUTOSTART:-}" ]; then
        info "SKIP_AUTOSTART set — skipping autostart setup."
        return
    fi
    mkdir -p "$(dirname "${DESKTOP_FILE}")"
    cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=ShotX
Comment=Screenshot and screen capture tool
Exec=${LAUNCHER} --tray
Icon=${INSTALL_DIR}/src/shotx/resources/icons/shotx.png
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
    success "Autostart entry created: ${DESKTOP_FILE}"
}

# ---------------------------------------------------------------------------
# PATH advice
# ---------------------------------------------------------------------------
check_bin_in_path() {
    case ":${PATH}:" in
        *":${BIN_DIR}:"*)
            return 0 ;;
    esac
    return 1
}

print_path_advice() {
    if ! check_bin_in_path; then
        warn ""
        warn "${BIN_DIR} is not in your PATH."
        warn "Add this line to your shell config (~/.bashrc, ~/.zshrc, ~/.profile, etc.):"
        warn ""
        warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        warn ""
        warn "Then restart your shell or run: source ~/.bashrc"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    printf "\n%b%bShotX Installer%b\n" "${BOLD}" "${CYAN}" "${RESET}"
    printf "════════════════════════════════════\n\n"

    # 1. Detect package manager
    PM=$(detect_pm)
    info "Package manager detected: ${PM}"

    # 2. Install system deps (skip if SKIP_SYSTEM_DEPS is set)
    if [ -n "${SKIP_SYSTEM_DEPS:-}" ]; then
        warn "SKIP_SYSTEM_DEPS set — skipping system dependency installation."
    else
        install_system_deps "${PM}"
    fi

    # 3. Verify Python 3.10+
    step "Checking Python version"
    PYTHON=$(find_python || true)
    if [ -z "${PYTHON}" ]; then
        die "Python ${PYTHON_MIN}+ not found. Please install Python ${PYTHON_MIN} or later."
    fi
    PY_VER=$("$PYTHON" -c "import sys; print('%d.%d' % sys.version_info[:2])")
    success "Found Python ${PY_VER} (${PYTHON})"

    # 4. Install uv
    install_uv

    # 5. Clone / update ShotX
    install_shotx

    # 6. Create launcher
    create_launcher

    # 7. Setup autostart (optional, set SKIP_AUTOSTART=1 to disable)
    setup_autostart

    # 8. PATH check
    print_path_advice

    printf "\n%b%b━━━ Installation complete! ━━━%b\n\n" "${BOLD}" "${GREEN}" "${RESET}"
    printf "Run %bshotx%b to start ShotX in system tray mode.\n" "${BOLD}" "${RESET}"
    printf "Run %bshotx --help%b to see all CLI options.\n\n" "${BOLD}" "${RESET}"
}

main "$@"
