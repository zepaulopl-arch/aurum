from aurum.cli import main


def test_context_presets_command_lists_presets(capsys):
    exit_code = main(["context", "presets"])

    assert exit_code == 0

    captured = capsys.readouterr()
    assert "AURUM MARKET CONTEXT PRESETS" in captured.out
    assert "normal" in captured.out
    assert "oil_war" in captured.out
