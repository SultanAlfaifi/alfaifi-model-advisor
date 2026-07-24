from __future__ import annotations

import re
import subprocess
import webbrowser
from urllib.parse import urlparse

from .catalog import TRUSTED_DOMAINS
from .models import HardwareProfile, ModelCandidate


SAFE_MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]*(?::[a-z0-9][a-z0-9_.-]*)?$", re.IGNORECASE)


def safe_official_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in TRUSTED_DOMAINS


def validate_installable(model: ModelCandidate) -> None:
    if not model.trusted:
        raise ValueError("Installation blocked: the model source is not trusted.")
    if not SAFE_MODEL_ID.fullmatch(model.id):
        raise ValueError("Installation blocked: the model identifier is unsafe.")
    if not safe_official_url(model.official_url):
        raise ValueError("Installation blocked: the model URL is outside the trusted domain allowlist.")
    if not model.install_command or not model.install_command.startswith("ollama pull "):
        raise ValueError("No trusted Ollama installation command is available for this model.")


def install_model(model: ModelCandidate, hardware: HardwareProfile) -> int:
    validate_installable(model)
    if not hardware.ollama.installed or not hardware.ollama.path:
        raise RuntimeError("Ollama is not installed or is unavailable in PATH.")
    result = subprocess.run([hardware.ollama.path, "pull", model.id], check=False)
    return result.returncode


def open_model_page(model: ModelCandidate) -> bool:
    if not safe_official_url(model.official_url):
        raise ValueError("The URL is outside the trusted domain allowlist.")
    return webbrowser.open(model.official_url)
