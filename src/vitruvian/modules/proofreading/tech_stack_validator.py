"""Camada 1 — Tech Stack Validator (Seleção Inicial)

Biologia: DNA Polimerase III seleciona nucleotídeo correto por complementaridade.
Software: Antes de gerar, valida alinhamento com tech stack do projeto.

Dois hooks:
  - pre_query: injeta lista de deps e regras de style no prompt (idempotente)
  - post_query: detecta uso de libs desconhecidas em pip/npm install e redireciona
"""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from pathlib import Path

from vitruvian.modules.base import Module

# Sentinel tag para tornar pre_query idempotente
_CONTEXT_TAG = "vitruvian_tech_stack_context"

from vitruvian.modules.base import Module, get_prompts

_PROMPTS = get_prompts("tech_stack")


class TechStackValidatorModule(Module):
    """Valida alinhamento com tech stack do projeto (Camada 1 Proofreading)."""

    def __init__(self, *, project_root: Path | str) -> None:
        super().__init__(name="tech_stack_validator")
        self.project_root = Path(project_root)
        self._known_deps: set[str] = set()
        self._style_rules: list[str] = []
        self._scan_done = False

    def pre_query(self, messages: list[dict]) -> list[dict]:
        """Injeta contexto do tech stack no prompt (idempotente)."""
        if not self._scan_done:
            self._scan_project()

        if not self._known_deps:
            return messages

        style_section = ""
        if self._style_rules:
            style_section = "Regras de style: " + "; ".join(self._style_rules)

        context_msg = {
            "role": "system",
            "content": _PROMPTS.get("context_template", "").format(
                deps=", ".join(sorted(self._known_deps)),
                style_section=style_section,
            ),
            "extra": {"vitruvian_tag": _CONTEXT_TAG},
        }

        # Idempotente: substitui a mensagem existente se já foi injetada
        for i, msg in enumerate(messages):
            if msg.get("extra", {}).get("vitruvian_tag") == _CONTEXT_TAG:
                messages[i] = context_msg
                return messages

        # Primeira injeção: insere após a primeira mensagem system
        insert_idx = 1 if messages and messages[0].get("role") == "system" else 0
        return [*messages[:insert_idx], context_msg, *messages[insert_idx:]]

    def post_query(self, message: dict) -> dict | None:
        """Detecta uso de libs desconhecidas em pip/npm install e redireciona."""
        if not self._known_deps:
            return message

        actions = message.get("extra", {}).get("actions", [])
        for action in actions:
            command = action.get("command", "")
            unknown = self._find_unknown_lib(command)
            if unknown:
                self.logger.warning(
                    "Lib desconhecida detectada: '%s' (não está no tech stack)", unknown
                )
                self._last_redirect = _PROMPTS.get("redirect_template", "").format(
                    lib=unknown,
                    deps=", ".join(sorted(self._known_deps)),
                )
                return None

        return message

    def reset(self) -> None:
        """Re-escaneia o projeto."""
        self._known_deps.clear()
        self._style_rules.clear()
        self._scan_done = False
        self._last_redirect: str | None = None

    # ------------------------------------------------------------------
    # Scanner de projeto
    # ------------------------------------------------------------------

    def _scan_project(self) -> None:
        """Escaneia manifests e configs do projeto."""
        self._scan_done = True
        self._scan_requirements_txt()
        self._scan_pyproject_toml()
        self._scan_package_json()
        self._scan_config_files()

        if self._known_deps:
            self.logger.info(
                "Tech stack detectado: %d deps, %d regras de style",
                len(self._known_deps),
                len(self._style_rules),
            )

    def _scan_requirements_txt(self) -> None:
        """Parseia requirements.txt."""
        req_file = self.project_root / "requirements.txt"
        if not req_file.exists():
            return
        try:
            for line in req_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    dep = re.split(r"[>=<!\[;]", line)[0].strip().lower()
                    if dep:
                        self._known_deps.add(dep)
        except OSError as e:
            self.logger.warning("Falha ao ler requirements.txt: %s", e)

    def _scan_pyproject_toml(self) -> None:
        """Parseia pyproject.toml com tomllib (stdlib 3.11+)."""
        toml_file = self.project_root / "pyproject.toml"
        if not toml_file.exists():
            return
        try:
            with toml_file.open("rb") as f:
                data = tomllib.load(f)

            # Dependencies
            for dep_str in data.get("project", {}).get("dependencies", []):
                dep = re.split(r"[>=<!\[;]", dep_str)[0].strip().lower()
                if dep:
                    self._known_deps.add(dep)

            # Ruff config
            ruff_cfg = data.get("tool", {}).get("ruff", {})
            line_len = ruff_cfg.get("line-length")
            if line_len:
                self._style_rules.append(f"ruff line-length={line_len}")
        except (OSError, tomllib.TOMLDecodeError) as e:
            self.logger.warning("Falha ao ler pyproject.toml: %s", e)

    def _scan_package_json(self) -> None:
        """Parseia package.json para deps."""
        pkg_file = self.project_root / "package.json"
        if not pkg_file.exists():
            return
        try:
            data = json.loads(pkg_file.read_text())
            for key in ("dependencies", "devDependencies"):
                if key in data and isinstance(data[key], dict):
                    self._known_deps.update(dep.lower() for dep in data[key])
        except (OSError, json.JSONDecodeError) as e:
            self.logger.warning("Falha ao ler package.json: %s", e)

    def _scan_config_files(self) -> None:
        """Escaneia config files de style/linting."""
        if (self.project_root / "tsconfig.json").exists():
            self._style_rules.append("tsconfig.json presente")

        for pattern in (".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml"):
            if (self.project_root / pattern).exists():
                self._style_rules.append(f"{pattern} presente")
                break

        for pattern in (".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierrc.yml"):
            if (self.project_root / pattern).exists():
                self._style_rules.append(f"{pattern} presente")
                break

    # ------------------------------------------------------------------
    # Detecção de libs desconhecidas
    # ------------------------------------------------------------------

    def _find_unknown_lib(self, command: str) -> str | None:
        """Detecta se o comando tenta instalar lib desconhecida.

        Usa shlex.split() para parsing robusto, pulando flags (-U, --upgrade, etc).
        """
        try:
            tokens = shlex.split(command)
        except ValueError:
            return None

        i = 0
        while i < len(tokens):
            token = tokens[i].lower()

            # pip install ...
            if token in ("pip", "pip3") and i + 1 < len(tokens) and tokens[i + 1] == "install":
                i += 2  # skip "pip install"
                while i < len(tokens):
                    pkg = tokens[i].lower()
                    if pkg.startswith("-"):
                        i += 1
                        # Flags com argumento: --target DIR, etc
                        if pkg in ("--target", "--prefix", "-t", "--root"):
                            i += 1
                        continue

                    # Clean pip specifiers (>=, ==, <=, [, ~=, !=)
                    clean_pkg = pkg
                    import re as _re
                    # Extract just the alphabetic base name
                    m = _re.match(r'^([a-z0-9_\-]+)', clean_pkg)
                    if m:
                        clean_pkg = m.group(1)

                    if clean_pkg not in self._known_deps:
                        return clean_pkg
                    i += 1
                return None

            # npm install ...
            if token == "npm" and i + 1 < len(tokens) and tokens[i + 1] == "install":
                i += 2
                while i < len(tokens):
                    pkg = tokens[i].lower()
                    if pkg.startswith("-"):
                        i += 1
                        continue

                    clean_pkg = pkg
                    if "@" in clean_pkg:
                        parts = clean_pkg.split("@")
                        # Se @ for no index 0 (ex: @types/react), remonta. Senão, quebra.
                        if not clean_pkg.startswith("@"):
                            clean_pkg = parts[0]
                        else:
                            clean_pkg = f"@{parts[1]}"

                    if clean_pkg not in self._known_deps:
                        return clean_pkg
                    i += 1
                return None

            i += 1

        return None

    @property
    def known_deps(self) -> set[str]:
        """Dependências conhecidas do projeto."""
        return set(self._known_deps)

    @property
    def style_rules(self) -> list[str]:
        """Regras de style detectadas."""
        return list(self._style_rules)

    @property
    def blocked_message(self) -> str | None:
        """Mensagem de redirecionamento para o agente (substitui mensagem refratária)."""
        msg = getattr(self, "_last_redirect", None)
        self._last_redirect = None  # Cosumir depois da leitura
        return msg
