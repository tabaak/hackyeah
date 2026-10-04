"""Independent, fail-closed configuration. Legacy LLM_FORCE is intentionally unused."""
import os
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


def local_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Local inference endpoints must be HTTP loopback URLs")
    return value.rstrip("/")


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("CONTROL_DATA_DIR", ".control-data")).resolve())
    qwen_url: str = field(default_factory=lambda: local_url(os.getenv("CONTROL_QWEN_URL", "http://127.0.0.1:8001/v1")))
    qwen_model: str = field(default_factory=lambda: os.getenv("CONTROL_QWEN_MODEL", "Qwen3.8-27B"))
    qwen_path: str = field(default_factory=lambda: os.getenv("CONTROL_QWEN_PATH", ""))
    openjev_url: str = field(default_factory=lambda: local_url(os.getenv("CONTROL_OPENJEV_URL", "http://127.0.0.1:8003/v1")))
    openjev_model: str = field(default_factory=lambda: os.getenv("CONTROL_OPENJEV_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"))
    jev_key: str = field(default_factory=lambda: os.getenv("TYPESAFE_API_KEY", ""))
    jev_model: str = field(default_factory=lambda: os.getenv("CONTROL_JEV_MODEL", "jev-latest"))
    gate: str = field(default_factory=lambda: os.getenv("CONTROL_GATE", "openjev"))
    timeout: float = 90
    # Unvalidated local decisions are advisory; there is deliberately no enable-by-env discard flag.
    max_items: int = 100
    # {provider: {inputPerMillion: USD, outputPerMillion: USD}}; no invented default tariffs.
    pricing: dict = field(default_factory=lambda: json.loads(os.getenv("CONTROL_PRICING_JSON", "{}")))

    def __post_init__(self):
        local_url(self.qwen_url)
        local_url(self.openjev_url)
        if self.gate not in {"openjev", "jev"}:
            raise ValueError("CONTROL_GATE must be openjev or jev")
        name = self.qwen_model.lower().replace("-", "").replace("_", "")
        if "qwen3.8" not in name or "27b" not in name:
            raise ValueError("CONTROL_QWEN_MODEL must identify Qwen3.8-27B")
        if not isinstance(self.pricing, dict):
            raise ValueError("CONTROL_PRICING_JSON must be an object")
        for provider, rates in self.pricing.items():
            if provider not in {"jev", "openjev", "qwen"} or not isinstance(rates, dict) or set(rates) != {"inputPerMillion", "outputPerMillion"}:
                raise ValueError("Invalid pricing configuration")
            if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in rates.values()):
                raise ValueError("Invalid pricing value")
