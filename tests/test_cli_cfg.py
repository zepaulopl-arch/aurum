import subprocess


def test_cli_cfg_prints_header():
    out = subprocess.run(["python", "-m", "aurum.cli", "cfg"], capture_output=True, text=True)
    assert "AURUM CFG" in out.stdout
