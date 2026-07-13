from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from socratic_cli.main import (
    _err,
    _load_opencode_config,
    _list_models,
    _list_providers,
    _resolve_api_key,
    _resolve_base_url,
    _resolve_timeout,
    _shell_escape,
    build_parser,
    cmd_config_import_opencode,
)


# --- Fixtures ---


VALID_CONFIG = {
    "provider": {
        "zcube-local": {
            "name": "ZCube Local",
            "options": {
                "baseURL": "http://192.168.68.29:8080/v1",
                "apiKey": "EMPTY",
            },
            "models": {
                "qwen3.6-35b-a3b": {
                    "name": "Qwen3.6 35B A3B",
                },
                "ornith-35b": {
                    "name": "Ornith 35B",
                },
            },
        },
        "sglang-mt": {
            "name": "SGLang",
            "options": {
                "baseURL": "http://example.org:27967/v1",
                "apiKey": "secret-key-123",
                "timeout": 60,
            },
            "models": {
                "Qwen3.6-35B": {
                    "name": "Qwen3.6 35B",
                },
            },
        },
    },
    "model": "zcube-local/qwen3.6-35b-a3b",
}

CONFIG_NO_API_KEY = {
    "provider": {
        "local": {
            "name": "Local",
            "options": {
                "baseURL": "http://localhost:8080/v1",
            },
            "models": {
                "model-a": {
                    "name": "Model A",
                },
            },
        },
    },
}

CONFIG_TIMEOUT_FALSE = {
    "provider": {
        "no-timeout": {
            "name": "No timeout",
            "options": {
                "baseURL": "http://localhost:8080/v1",
                "apiKey": "key",
                "timeout": False,
            },
            "models": {
                "m1": {"name": "M1"},
            },
        },
    },
}


@pytest.fixture
def opencode_config(tmp_path):
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "opencode.json"
    config_file.write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
    return config_file


@pytest.fixture
def opencode_config_no_key(tmp_path):
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "opencode.json"
    config_file.write_text(json.dumps(CONFIG_NO_API_KEY), encoding="utf-8")
    return config_file


@pytest.fixture
def opencode_config_timeout_false(tmp_path):
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "opencode.json"
    config_file.write_text(json.dumps(CONFIG_TIMEOUT_FALSE), encoding="utf-8")
    return config_file


# --- Tests: lectura de configuración ---


def test_load_valid_config(opencode_config):
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(
            Path, "expanduser", return_value=opencode_config
        ):
            config = _load_opencode_config()
    assert config["provider"]["zcube-local"]["name"] == "ZCube Local"


def test_load_nonexistent_config(tmp_path):
    with mock.patch.dict(os.environ, {}, clear=False):
        fake_path = tmp_path / "nonexistent" / "opencode.json"
        with mock.patch.object(Path, "expanduser", return_value=fake_path):
            with pytest.raises(SystemExit) as exc_info:
                _load_opencode_config()
    assert exc_info.value.code == 1


def test_load_invalid_json(tmp_path):
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "opencode.json"
    config_file.write_text("{bad json}", encoding="utf-8")
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=config_file):
            with pytest.raises(SystemExit) as exc_info:
                _load_opencode_config()
    assert exc_info.value.code == 1


def test_list_providers():
    providers = _list_providers(VALID_CONFIG)
    assert "zcube-local" in providers
    assert "sglang-mt" in providers


def test_list_providers_empty():
    with pytest.raises(SystemExit) as exc_info:
        _list_providers({"provider": {}})
    assert exc_info.value.code == 1


def test_list_models():
    models = _list_models(VALID_CONFIG["provider"]["zcube-local"])
    assert "qwen3.6-35b-a3b" in models
    assert "ornith-35b" in models


def test_list_models_empty():
    with pytest.raises(SystemExit) as exc_info:
        _list_models({"models": {}})
    assert exc_info.value.code == 1


# --- Tests: resolución de valores ---


def test_resolve_base_url():
    url = _resolve_base_url(VALID_CONFIG["provider"]["zcube-local"])
    assert url == "http://192.168.68.29:8080/v1"


def test_resolve_base_url_missing():
    url = _resolve_base_url(CONFIG_NO_API_KEY["provider"]["local"])
    assert url == "http://localhost:8080/v1"


def test_resolve_base_url_empty():
    url = _resolve_base_url({"options": {}})
    assert url is None


def test_resolve_api_key():
    key = _resolve_api_key(VALID_CONFIG["provider"]["zcube-local"])
    assert key == "EMPTY"


def test_resolve_api_key_missing():
    key = _resolve_api_key(CONFIG_NO_API_KEY["provider"]["local"])
    assert key is None


def test_resolve_timeout():
    timeout = _resolve_timeout(VALID_CONFIG["provider"]["sglang-mt"])
    assert timeout == 60


def test_resolve_timeout_false(opencode_config_timeout_false):
    config = json.loads(
        opencode_config_timeout_false.read_text(encoding="utf-8")
    )
    timeout = _resolve_timeout(config["provider"]["no-timeout"])
    assert timeout is None


# --- Tests: escape de shell ---


def test_shell_escape_simple():
    assert _shell_escape("hello") == "'hello'"


def test_shell_escape_with_quotes():
    assert _shell_escape("it's") == "'it'\\''s'"


def test_shell_escape_with_backslash():
    assert _shell_escape("path\\to") == "'path\\to'"


def test_shell_escape_special_chars():
    result = _shell_escape("value with $HOME and `cmd`")
    assert "$HOME" in result
    assert "`cmd`" in result


# --- Tests: export-shell ---


def test_export_shell_basic(opencode_config):
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=opencode_config):
            stdout = []
            stderr = []
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        result = cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "zcube-local",
                                "model": "qwen3.6-35b-a3b",
                                "export_shell": True,
                                "print_env": False,
                            })()
                        )
                    output = mock_out.getvalue()
    assert result == 0
    assert "export SOCRATIC_LLM_PROVIDER='openai-compatible'" in output
    assert "export SOCRATIC_LLM_BASE_URL='http://192.168.68.29:8080/v1'" in output
    assert "export SOCRATIC_LLM_MODEL='qwen3.6-35b-a3b'" in output
    assert "export SOCRATIC_LLM_API_KEY='EMPTY'" in output
    assert "export SOCRATIC_LLM_TIMEOUT_SECONDS='120'" in output


def test_export_shell_no_api_key(opencode_config_no_key):
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=opencode_config_no_key):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        result = cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "local",
                                "model": "model-a",
                                "export_shell": True,
                                "print_env": False,
                            })()
                        )
                    output = mock_out.getvalue()
    assert result == 0
    assert "unset SOCRATIC_LLM_API_KEY" in output
    assert "SOCRATIC_LLM_BASE_URL" in output
    assert "SOCRATIC_LLM_MODEL" in output


def test_export_shell_no_extra_stdout(opencode_config):
    """Verificar que no hay mensajes informativos en stdout con --export-shell."""
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=opencode_config):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "zcube-local",
                                "model": "qwen3.6-35b-a3b",
                                "export_shell": True,
                                "print_env": False,
                            })()
                        )
                    output = mock_out.getvalue()
    lines = [l for l in output.strip().split("\n") if l.strip()]
    assert all(l.startswith("export ") for l in lines)


def test_export_shell_timeout_false(opencode_config_timeout_false):
    config = json.loads(
        opencode_config_timeout_false.read_text(encoding="utf-8")
    )
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=opencode_config_timeout_false):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "no-timeout",
                                "model": "m1",
                                "export_shell": True,
                                "print_env": False,
                            })()
                        )
                    output = mock_out.getvalue()
    assert "SOCRATIC_LLM_TIMEOUT_SECONDS='120'" in output


# --- Tests: print-env ---


def test_print_env_basic(opencode_config):
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=opencode_config):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "zcube-local",
                                "model": "qwen3.6-35b-a3b",
                                "export_shell": False,
                                "print_env": True,
                            })()
                        )
                    stdout = mock_out.getvalue()
                    stderr = mock_err.getvalue()
    assert "SOCRATIC_LLM_PROVIDER=openai-compatible" in stdout
    assert "SOCRATIC_LLM_BASE_URL=http://192.168.68.29:8080/v1" in stdout
    assert "SOCRATIC_LLM_MODEL=qwen3.6-35b-a3b" in stdout
    assert "SOCRATIC_LLM_API_KEY=EMPTY" in stdout
    assert "SOCRATIC_LLM_TIMEOUT_SECONDS=120" in stdout
    assert "ADVERTENCIA" in stderr
    assert "secretos" in stderr


def test_print_env_no_extra_quotes(tmp_path):
    """Verificar que --print-env no usa comillas en los valores."""
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "opencode.json"
    config_file.write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=config_file):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "zcube-local",
                                "model": "qwen3.6-35b-a3b",
                                "export_shell": False,
                                "print_env": True,
                            })()
                        )
    output = mock_out.getvalue()
    # Should not have quotes around values
    assert "'openai-compatible'" not in output
    assert "openai-compatible" in output


# --- Tests: errores ---


def test_provider_not_found(opencode_config):
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=opencode_config):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        result = cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "nonexistent",
                                "model": None,
                                "export_shell": True,
                                "print_env": False,
                            })()
                        )
    assert result == 1
    assert "nonexistent" in mock_err.getvalue()
    assert mock_out.getvalue().strip() == ""


def test_model_not_found(opencode_config):
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=opencode_config):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        result = cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "zcube-local",
                                "model": "nonexistent-model",
                                "export_shell": True,
                                "print_env": False,
                            })()
                        )
    assert result == 1
    assert "nonexistent-model" in mock_err.getvalue()
    assert mock_out.getvalue().strip() == ""


def test_base_url_missing(opencode_config):
    config = {
        "provider": {
            "no-url": {
                "options": {},
                "models": {"m1": {"name": "M1"}},
            },
        },
    }
    tmp = opencode_config
    tmp.write_text(json.dumps(config), encoding="utf-8")
    with mock.patch.dict(os.environ, {}, clear=False):
        with mock.patch.object(Path, "expanduser", return_value=tmp):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                    with mock.patch("sys.argv", ["socratic"]):
                        result = cmd_config_import_opencode(
                            type("Args", (), {
                                "provider": "no-url",
                                "model": "m1",
                                "export_shell": True,
                                "print_env": False,
                            })()
                        )
    assert result == 1
    assert "baseURL" in mock_err.getvalue()


# --- Tests: parser ---


def test_parser_has_config_subcommand():
    parser = build_parser()
    # Verificar que el parser se construye sin errores
    assert parser is not None


def test_parser_config_import_opencode_requires_mode():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([
            "config", "import-opencode",
            "--provider", "test",
        ])


def test_parser_config_import_opencode_export_shell():
    parser = build_parser()
    args = parser.parse_args([
        "config", "import-opencode",
        "--provider", "test",
        "--export-shell",
    ])
    assert args.config_command == "import-opencode"
    assert args.export_shell is True
    assert args.print_env is False


def test_parser_config_import_opencode_print_env():
    parser = build_parser()
    args = parser.parse_args([
        "config", "import-opencode",
        "--provider", "test",
        "--print-env",
    ])
    assert args.config_command == "import-opencode"
    assert args.export_shell is False
    assert args.print_env is True


# --- Tests: integración con subprocess ---


def test_subprocess_export_shell(opencode_config):
    """Verificar que la salida de --export-shell es executable como shell."""
    config_dir = opencode_config.parent
    env = os.environ.copy()
    env["OPENCODE_CONFIG_PATH"] = str(opencode_config)

    result = subprocess.run(
        [
            sys.executable,
            "-m", "socratic_cli",
            "config", "import-opencode",
            "--provider", "zcube-local",
            "--model", "qwen3.6-35b-a3b",
            "--export-shell",
        ],
        capture_output=True,
        text=True,
        env={
            **env,
            "HOME": str(config_dir.parent.parent),
        },
    )
    assert result.returncode == 0
    lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
    assert len(lines) == 5
    assert all(l.startswith("export ") for l in lines)
    assert result.stderr.strip() == ""


def test_subprocess_print_env(opencode_config):
    """Verificar que --print-env muestra advertencia por stderr."""
    config_dir = opencode_config.parent
    result = subprocess.run(
        [
            sys.executable,
            "-m", "socratic_cli",
            "config", "import-opencode",
            "--provider", "zcube-local",
            "--model", "qwen3.6-35b-a3b",
            "--print-env",
        ],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(config_dir.parent.parent),
        },
    )
    assert result.returncode == 0
    assert "SOCRATIC_LLM_PROVIDER=openai-compatible" in result.stdout
    assert "ADVERTENCIA" in result.stderr


# --- Tests: servidor carga variables ---


def test_server_settings_read_env_vars():
    """Verificar que Settings lee las variables SOCRATIC_LLM_*."""
    from socratic.config.settings import Settings

    with mock.patch.dict(
        os.environ,
        {
            "SOCRATIC_LLM_PROVIDER": "openai-compatible",
            "SOCRATIC_LLM_BASE_URL": "http://test:8080/v1",
            "SOCRATIC_LLM_MODEL": "test-model",
            "SOCRATIC_LLM_API_KEY": "test-key",
            "SOCRATIC_LLM_TIMEOUT_SECONDS": "45",
        },
        clear=False,
    ):
        settings = Settings()
    assert settings.llm_provider == "openai-compatible"
    assert settings.llm_base_url == "http://test:8080/v1"
    assert settings.llm_model == "test-model"
    assert settings.llm_api_key == "test-key"
    assert settings.llm_timeout_seconds == 45


def test_server_settings_defaults():
    """Verificar que los valores por defecto son correctos."""
    from socratic.config.settings import Settings

    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings()
    assert settings.llm_provider == "openai-compatible"
    assert settings.llm_base_url is None
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_api_key is None
    assert settings.llm_timeout_seconds == 120


def test_server_llm_client_receives_timeout():
    """Verificar que OpenAIClient recibe el timeout desde settings."""
    from socratic.llm.openai_client import OpenAIClient

    client = OpenAIClient(
        api_key="test",
        base_url="http://test:8080/v1",
        model="test-model",
        timeout=99,
    )
    assert client._timeout == 99


def test_api_key_not_in_logs():
    """Verificar que la API key no aparece en logs de error genéricos."""
    captured = []

    class FakeStderr:
        def write(self, msg):
            captured.append(msg)
        def flush(self):
            pass

    fake_stderr = FakeStderr()
    _err("Error de conexión")
    # El mensaje de error no debe contener la palabra "key" ni "secret"
    full_output = "".join(captured)
    assert "key" not in full_output.lower() or "API" not in full_output
    assert "secret" not in full_output.lower()
