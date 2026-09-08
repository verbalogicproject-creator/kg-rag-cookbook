from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigError
from .models import EmbeddingProfile

SECRET_NAMES = {".env", ".envrc", "id_rsa", "id_ed25519"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt"}


def _load_dotenv(path: Path) -> None:
    """Load project credentials only when the environment has no value already."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


@dataclass(frozen=True)
class HybridConfig:
    root: Path
    path: Path
    raw: dict[str, Any]

    @property
    def storage_path(self) -> Path:
        return self.resolve(self.raw["storage"]["path"])

    @property
    def config_hash(self) -> str:
        canonical = json.dumps(self.raw, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    def resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (self.root / path).resolve()

    def profile(self, name: str) -> EmbeddingProfile:
        try:
            raw = self.raw["profiles"][name]
        except KeyError as exc:
            raise ConfigError(f"unknown embedding profile: {name}") from exc
        formatting = {
            key: str(value)
            for key, value in raw.items()
            if key.endswith("format") or key.endswith("task_type")
        }
        return EmbeddingProfile(
            name=name,
            provider=str(raw["provider"]),
            model=str(raw["model"]),
            dimensions=int(raw["dimensions"]),
            normalization=str(raw["normalization"]),
            formatting=formatting,
        )

    def source_path(self, source: dict[str, Any]) -> Path:
        return self.resolve(str(source["path"]))


def is_secret_path(path: Path) -> bool:
    return path.name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES


def validate_config(config: HybridConfig, *, require_paths: bool = True) -> list[str]:
    raw = config.raw
    errors: list[str] = []
    if raw.get("schema") != "nlke-hybrid-rag/1.0":
        errors.append("schema must be nlke-hybrid-rag/1.0")
    for key in ("storage", "canonical_dependency", "sources", "profiles", "services", "retrieval", "enforcement"):
        if key not in raw:
            errors.append(f"missing {key}")
    source_ids: set[str] = set()
    for source in raw.get("sources", []):
        ident = source.get("id")
        if not isinstance(ident, str) or not ident:
            errors.append("source has no non-empty id")
            continue
        if ident in source_ids:
            errors.append(f"duplicate source id: {ident}")
        source_ids.add(ident)
        if not isinstance(source.get("cloud_eligible"), bool):
            errors.append(f"source {ident} must declare cloud_eligible")
        if not isinstance(source.get("include"), list) or not isinstance(source.get("exclude"), list):
            errors.append(f"source {ident} must declare include and exclude lists")
        path = config.source_path(source)
        if require_paths and not path.exists():
            errors.append(f"declared source is unavailable: {path}")
        if is_secret_path(path):
            errors.append(f"secret path cannot be a declared source: {path}")
    for name in ("local", "cloud"):
        try:
            profile = config.profile(name)
            # Dimensions must be declared and positive -- NOT a specific number.
            #
            # This read `!= 768` and was the only occurrence of that literal outside test
            # fixtures. Nothing depends on it: `embeddings.dimensions` is a per-row column,
            # profiles are separate vector spaces that are never compared to each other
            # (`both` mode fuses ranked LISTS through RRF, not vectors), and the invariant
            # that actually matters -- a vector matching its own profile's declared size --
            # is already enforced at store.py:173 and providers.py:190.
            #
            # So the literal pinned the size two particular models happened to share and
            # refused every other embedder. A 1024-dimension model is not a misconfiguration.
            if not isinstance(profile.dimensions, int) or profile.dimensions <= 0:
                errors.append(f"profile {name} must declare positive integer dimensions, got {profile.dimensions!r}")
            if profile.normalization != "l2/v1":
                errors.append(f"profile {name} must declare l2/v1 normalization")
        except (KeyError, ConfigError):
            errors.append(f"missing profile {name}")
    graph = raw.get("graph", {})
    if graph.get("read_only") is not True:
        errors.append("graph.read_only must be true")
    if require_paths and graph and not config.resolve(graph.get("path", "")).is_file():
        errors.append("declared graph database is unavailable")
    dependency = raw.get("canonical_dependency", {})
    if not config.resolve(str(dependency.get("path", ""))).is_dir():
        errors.append("canonical declared-core path is unavailable")
    if raw.get("retrieval", {}).get("default_mode") != "local":
        errors.append("retrieval.default_mode must be local")
    return errors


def load_config(path: str | Path = "hybrid-rag.json") -> HybridConfig:
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise ConfigError(f"configuration not found: {config_path}")
    _load_dotenv(config_path.parent / ".env")
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {config_path}: {exc}") from exc
    config = HybridConfig(root=config_path.parent, path=config_path, raw=raw)
    errors = validate_config(config)
    if errors:
        raise ConfigError("invalid hybrid-rag.json: " + "; ".join(errors))
    return config
