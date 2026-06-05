from pathlib import Path

from pymercator.features_catalog import (
    validate_features_catalog,
    write_features_catalog,
)


def test_write_features_catalog_creates_valid_template(tmp_path: Path):
    output = tmp_path / "features_catalog.json"

    payload = write_features_catalog(output=output)

    assert payload["valid"] is True
    assert payload["features"] >= 5
    assert output.exists()


def test_validate_features_catalog_rejects_duplicate_names(tmp_path: Path):
    output = tmp_path / "features_catalog.json"
    output.write_text(
        """
{
  "features": [
    {"name": "return_1d", "group": "returns", "enabled": true},
    {"name": "return_1d", "group": "returns", "enabled": true}
  ]
}
""",
        encoding="utf-8",
    )

    payload = validate_features_catalog(output)

    assert payload["valid"] is False
    assert "duplicated name return_1d" in "\\n".join(payload["errors"])
