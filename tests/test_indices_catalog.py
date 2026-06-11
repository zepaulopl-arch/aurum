from pathlib import Path

from aurum.indices_catalog import (
    validate_indices_catalog,
    write_indices_catalog,
)


def test_write_and_validate_indices_catalog(tmp_path: Path):
    output = tmp_path / "indices_catalog.json"

    result = write_indices_catalog(
        output=output,
        indices=[
            {
                "name": "IBOV",
                "symbol": "^BVSP",
                "provider": "yfinance",
                "category": "equity",
            }
        ],
    )

    validation = validate_indices_catalog(output)

    assert result["valid"] is True
    assert validation["valid"] is True
    assert validation["count"] == 1

