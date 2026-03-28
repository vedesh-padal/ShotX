# packaging/homebrew/shotx.rb
#
# This formula is maintained in the vedesh-padal/homebrew-tap repository.
# This copy in the ShotX repo is the source of truth for formula changes.
#
# To release a new version:
# 1. Get the PyPI .tar.gz SHA256:
#      curl -sL https://files.pythonhosted.org/packages/source/s/shotx/shotx-<VERSION>.tar.gz | sha256sum
# 2. Update `url` and `sha256` below.
# 3. Copy this file into homebrew-tap/Formula/shotx.rb and commit.

class Shotx < Formula
  include Language::Python::Virtualenv

  desc "Advanced screenshot and screen capture utility for Linux — inspired by ShareX"
  homepage "https://shotx.vedeshpadal.me"

  # Update url and sha256 on every release.
  # PyPI naming: hyphens become underscores, 0.9.5-beta.3 becomes 0.9.5b3
  url "https://files.pythonhosted.org/packages/source/s/shotx/shotx-<VERSION>.tar.gz"
  sha256 "<SHA256_OF_TARBALL>"
  license "GPL-3.0-only"

  # ShotX is Linux-only (Wayland/X11 capture, GTK/dbus dependencies)
  depends_on :linux

  depends_on "python@3.12"
  depends_on "gobject-introspection"  # PyGObject / dbus-next runtime
  depends_on "cairo"                  # Required by PyGObject
  depends_on "pkg-config"             # Build-time dep for PyGObject

  def install
    # Homebrew creates an isolated venv in libexec and symlinks the
    # entry point binary to bin/. This is the standard pattern for
    # Python CLI tools on Homebrew.
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      ShotX has been installed. For full feature support, install these
      system packages with your distro package manager:

        OCR text extraction:   sudo apt install tesseract-ocr
        QR code scanning:      sudo apt install libzbar0
        Screen recording (X11):  sudo apt install ffmpeg
        Screen recording (Wayland): sudo apt install wf-recorder

      On first run, ShotX will offer to integrate with your desktop
      (application menu + autostart). You can also run:
        shotx --tray
    EOS
  end

  test do
    # Verify the binary runs and version string is reported correctly
    assert_match version.to_s, shell_output("#{bin}/shotx --version")
  end
end
