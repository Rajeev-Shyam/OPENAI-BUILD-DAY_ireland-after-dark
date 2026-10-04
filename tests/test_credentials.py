"""Credential selection must not execute dotenv or disclose key values."""
import pytest

from data.pipeline.credentials import load_nta_api_key


def test_explicit_file_quotes_comments_and_environment_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("NTA_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text('IGNORED=other\nexport NTA_API_KEY="file-token" # comment\n')
    assert load_nta_api_key(env) == "file-token"
    monkeypatch.setenv("NTA_API_KEY", "environment-token")
    assert load_nta_api_key(tmp_path / "does-not-exist") == "environment-token"


def test_file_is_never_sourced_as_shell(tmp_path, monkeypatch):
    monkeypatch.delenv("NTA_API_KEY", raising=False)
    env = tmp_path / ".env"
    marker = tmp_path / "must-not-exist"
    env.write_text(f'UNRELATED=$(touch {marker})\nNTA_API_KEY="literal-$TOKEN"\n')
    assert load_nta_api_key(env) == "literal-$TOKEN"
    assert not marker.exists()


@pytest.mark.parametrize("contents", [
    "NTA_API_KEY=\n", "UNRELATED=value\n", "NTA_API_KEY=one\nNTA_API_KEY=two\n",
    'NTA_API_KEY="private-secret\n', 'NTA_API_KEY="private secret"\n',
])
def test_bad_credentials_fail_without_exposing_values(tmp_path, monkeypatch, contents):
    monkeypatch.delenv("NTA_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(contents)
    with pytest.raises(ValueError) as error:
        load_nta_api_key(env)
    assert "private" not in str(error.value)


def test_environment_header_injection_rejected(monkeypatch):
    monkeypatch.setenv("NTA_API_KEY", "secret\r\nInjected: value")
    with pytest.raises(ValueError, match="whitespace") as error:
        load_nta_api_key()
    assert "secret" not in str(error.value)
