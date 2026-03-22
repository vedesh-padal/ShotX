class Shotx < Formula
  desc "A free, open-source screenshot and screen capture tool for Linux — inspired by ShareX."
  homepage "https://shotx.vedeshpadal.me"
  url "https://github.com/vedesh-padal/sharex-linux/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256_AFTER_RELEASE"
  license "GPL-3.0-only"

  depends_on :linux
  depends_on "uv"

  def install
    # Isolate the virtual environment into Homebrew's libexec directory
    ENV["UV_TOOL_DIR"] = libexec/"uv-tools"
    # Drop the 'shotx' executable directly into Homebrew's bin directory
    ENV["UV_TOOL_BIN_DIR"] = bin

    # Install directly from the downloaded source tarball
    system "uv", "tool", "install", "."
  end

  def caveats
    <<~EOS
      ShotX has been installed successfully via uv!
      
      To integrate with your desktop and system tray, run:
        shotx --setup-desktop
        shotx --install-autostart
    EOS
  end

  test do
    assert_match "ShotX — Screenshot and screen capture tool", shell_output("#{bin}/shotx --version")
  end
end
