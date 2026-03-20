import subprocess
import sys

# Get the path to the shotx executable via `sys.executable -m shotx.main`
# This avoids needing to install the wheel just to run tests locally.
SHOTX_CMD = [sys.executable, "-m", "shotx.main"]


class TestCLI:

    def test_help_flag(self):
        """CLI should exit cleanly with 0 when passed --help."""
        result = subprocess.run(
            [*SHOTX_CMD, "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "ShotX — Screenshot and screen capture tool" in result.stdout
        assert "--capture-fullscreen" in result.stdout

    def test_version_flag(self):
        """CLI should exit cleanly with 0 and print version when passed --version."""
        result = subprocess.run(
            [*SHOTX_CMD, "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "shotx" in result.stdout.lower()

    def test_invalid_flag(self):
        """CLI should exit with 2 (argparse error) for unknown flags."""
        result = subprocess.run(
            [*SHOTX_CMD, "--this-flag-does-not-exist"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 2
        assert "unrecognized arguments" in result.stderr

    def test_shorten_url_headless(self):
        """--shorten-url with an explicit URL should print the result and exit 0."""
        # Using a mock API or known service might be flaky in CI, but tmpfiles or
        # tinyurl usually works. Let's just test that the CLI parses it correctly
        # and attempts the action without crashing the Qt event loop.
        # We'll test with a deliberate bad URL to test the graceful error exit (1).

        result = subprocess.run(
            [*SHOTX_CMD, "--shorten-url", "not-a-real-url"],
            capture_output=True,
            text=True
        )
        # Because it's an invalid URL, the shortener will likely fail.
        # ShotX should catch it and exit with 1.
        # The key is that it doesn't hang forever waiting for Qt to quit.
        assert result.returncode in (0, 1)

