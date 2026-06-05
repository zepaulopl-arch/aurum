from pathlib import Path

from pymercator.cli import main


def test_features_check_command(tmp_path: Path, capsys):
    output = tmp_path / "features_catalog.json"

    output.write_text(
        """
{
  "features": [
    {
      "name": "return_1d",
      "group": "price",
      "enabled": true,
      "required": true,
      "description": "test"
    }
  ]
}
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "features",
            "check",
            "--file",
            str(output),
        ]
    )

    assert exit_code == 0

    captured = capsys.readouterr()
    assert "PYMERCATOR FEATURES CATALOG" in captured.out
    assert "return_1d" in captured.out
