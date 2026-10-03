"""Environment parsing in app/config.py. Each test executes config.py afresh with a controlled environment."""
import importlib.util
import re
import shutil
import subprocess

import dotenv
import pytest

from tests.conftest import REPO

CONFIG = REPO / "backend" / "app" / "config.py"
ENV_VARS = re.findall(r'_env\("(\w+)"', CONFIG.read_text())


def load_config(monkeypatch, **env):
    """Run config.py as a new module with exactly `env`; the real .env file is not read."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    loaded = []
    monkeypatch.setattr(dotenv, "load_dotenv", lambda path=None, **kw: loaded.append(path))
    spec = importlib.util.spec_from_file_location("config_under_test", CONFIG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.settings, loaded


def test_reads_repo_root_dotenv(monkeypatch):
    _, loaded = load_config(monkeypatch)
    assert loaded == [REPO / ".env"]


def test_defaults(monkeypatch):
    s, _ = load_config(monkeypatch)
    assert (s.supabase_url, s.supabase_jwt_secret, s.serper_api_key) == ("", "", "")
    assert (s.openai_api_key, s.openai_model) == ("", "")
    assert s.openai_base_url == "https://api.openai.com/v1"
    assert s.local_llm_base_url == "http://localhost:8000/v1"
    assert s.local_llm_model == "bonsai-2-27b"
    assert s.local_llm_api_key == "not-needed"
    assert s.llm_force == ""
    assert s.llm_timeout_s == 120.0


def test_empty_values_fall_back_to_defaults(monkeypatch):
    s, _ = load_config(monkeypatch, LOCAL_LLM_BASE_URL="", LOCAL_LLM_MODEL="", OPENAI_BASE_URL="", LLM_TIMEOUT_S="")
    assert s.local_llm_base_url == "http://localhost:8000/v1"
    assert s.local_llm_model == "bonsai-2-27b"
    assert s.openai_base_url == "https://api.openai.com/v1"
    assert s.llm_timeout_s == 120.0


def test_values_are_read(monkeypatch):
    s, _ = load_config(monkeypatch, SUPABASE_URL="https://abc.supabase.co", OPENAI_MODEL="gpt-x",
                       LOCAL_LLM_BASE_URL="http://gpu-box:9000/v1", LLM_FORCE="local", LLM_TIMEOUT_S="30")
    assert s.supabase_url == "https://abc.supabase.co"
    assert s.openai_model == "gpt-x"
    assert s.local_llm_base_url == "http://gpu-box:9000/v1"
    assert s.llm_force == "local"
    assert s.llm_timeout_s == 30.0


def test_supabase_url_trailing_slash_is_removed(monkeypatch):
    # deps.py builds f"{supabase_url}/auth/v1"; a trailing slash would break the issuer check for every token.
    s, _ = load_config(monkeypatch, SUPABASE_URL="https://abc.supabase.co/")
    assert s.supabase_url == "https://abc.supabase.co"


def test_openai_key_alias(monkeypatch):
    s, _ = load_config(monkeypatch, OPENAI_KEY="sk-alias")
    assert s.openai_api_key == "sk-alias"
    s, _ = load_config(monkeypatch, OPENAI_KEY="sk-alias", OPENAI_API_KEY="sk-main")
    assert s.openai_api_key == "sk-main"
    s, _ = load_config(monkeypatch, OPENAI_KEY="sk-alias", OPENAI_API_KEY="")
    assert s.openai_api_key == "sk-alias"


def test_invalid_timeout_fails_at_startup(monkeypatch):
    with pytest.raises(ValueError):
        load_config(monkeypatch, LLM_TIMEOUT_S="soon")


def test_env_example_documents_every_variable():
    example = (REPO / ".env.example").read_text()
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", example, re.M))
    assert set(ENV_VARS) <= documented, f"missing in .env.example: {set(ENV_VARS) - documented}"


@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_secrets_file_is_git_ignored():
    def ignored(path):
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO).returncode == 0

    assert ignored(".env")
    assert not ignored(".env.example")
