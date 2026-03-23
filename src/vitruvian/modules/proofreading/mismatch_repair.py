"""Camada 3 — Mismatch Repair (Gate Pós-Execução)

Biologia: MutS/MutL varrem DNA recém-replicado buscando incompatibilidades
que escaparam das camadas anteriores.

Software: Após cada ação que modifica arquivos, executa testes existentes
e checa contra anti-patterns conhecidos do projeto.

Um hook:
  - post_action: roda testes + verifica anti-patterns após ações de escrita
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from vitruvian.modules.base import Module

# Comandos que indicam escrita/modificação de arquivos
_WRITE_PATTERNS = re.compile(
    r"(cat\s*>|tee\s|>>|sed\s+-i|mv\s|cp\s|echo\s.*>|write_file|edit_file|create_file|patch\s|touch\s|mkdir\s|curl\s.*-o|python[23]?\s+-c.*open.*[wa])",
    re.IGNORECASE,
)

# Timeout para execução de testes (segundos)
DEFAULT_TEST_TIMEOUT = 60


class MismatchRepairModule(Module):
    """Executa testes e checa anti-patterns após ações de escrita (Camada 3)."""

    def __init__(
        self,
        *,
        project_root: Path | str,
        test_command: str | None = None,
        anti_patterns_path: Path | str | None = None,
        test_timeout: int = DEFAULT_TEST_TIMEOUT,
    ) -> None:
        super().__init__(name="mismatch_repair")
        self.project_root = Path(project_root)
        self._test_command_override = test_command
        self._test_command: str | None = None
        self._anti_patterns: list[dict] = []
        self._anti_patterns_path = (
            Path(anti_patterns_path) if anti_patterns_path
            else self.project_root / ".vitruvian" / "anti_patterns.json"
        )
        self.test_timeout = test_timeout
        self._scan_done = False

    def post_action(self, action: dict, result: dict) -> dict:
        """Após ações de escrita: roda testes + checa anti-patterns."""
        if not self._scan_done:
            self._scan_project()

        command = action.get("command", "")

        # Só verifica para ações que modificam arquivos
        if not self._is_write_action(command):
            return result

        # Inicializa extra se não existir
        if "extra" not in result:
            result["extra"] = {}

        warnings: list[str] = []

        # 1. Anti-pattern check no output
        output = result.get("output", "")
        ap_warnings = self._check_anti_patterns(output + "\n" + command)
        warnings.extend(ap_warnings)

        # 2. Roda testes se disponível
        if self._test_command:
            test_result = self._run_tests()
            if test_result is not None:
                result["extra"]["test_result"] = test_result
                if test_result["returncode"] != 0:
                    warnings.append(
                        f"⚠️ Testes falharam após esta ação. "
                        f"Output: {test_result['output'][:500]}"
                    )

        if warnings:
            result["extra"]["proofreading_warnings"] = warnings
            self.logger.warning(
                "Mismatch Repair: %d warnings após ação: %.60s...",
                len(warnings),
                command,
            )

        return result

    def reset(self) -> None:
        """Re-escaneia o projeto."""
        self._test_command = None
        self._anti_patterns.clear()
        self._scan_done = False

    # ------------------------------------------------------------------
    # Scanner
    # ------------------------------------------------------------------

    def _scan_project(self) -> None:
        """Detecta test runner e carrega anti-patterns."""
        self._scan_done = True

        # Test command
        if self._test_command_override:
            self._test_command = self._test_command_override
        else:
            self._test_command = self._detect_test_runner()

        # Anti-patterns
        self._load_anti_patterns()

        self.logger.info(
            "Mismatch Repair: test_command=%s, anti_patterns=%d",
            self._test_command or "(nenhum)",
            len(self._anti_patterns),
        )

    def _detect_test_runner(self) -> str | None:
        """Auto-detecta o test runner do projeto."""
        # pytest
        if (self.project_root / "pytest.ini").exists():
            return "python -m pytest --tb=short -q"

        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "[tool.pytest" in content:
                    return "python -m pytest --tb=short -q"
            except OSError:
                pass

        # npm test
        pkg_json = self.project_root / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                if "test" in data.get("scripts", {}):
                    return "npm test"
            except (OSError, json.JSONDecodeError):
                pass

        # Makefile
        makefile = self.project_root / "Makefile"
        if makefile.exists():
            try:
                content = makefile.read_text()
                if "test:" in content:
                    return "make test"
            except OSError:
                pass

        return None

    def _load_anti_patterns(self) -> None:
        """Carrega anti-patterns de .vitruvian/anti_patterns.json.

        Pre-compila regexes; patterns inválidos são ignorados com warning.
        """
        if not self._anti_patterns_path.exists():
            return
        try:
            data = json.loads(self._anti_patterns_path.read_text())
            raw_patterns = []
            if isinstance(data, list):
                raw_patterns = data
            elif isinstance(data, dict) and "patterns" in data:
                raw_patterns = data["patterns"]

            for entry in raw_patterns:
                if not isinstance(entry, dict):
                    continue
                regex_str = entry.get("regex", "")
                reason = entry.get("reason", "anti-pattern detectado")
                if not regex_str or not isinstance(regex_str, str):
                    continue
                try:
                    compiled = re.compile(regex_str)
                    self._anti_patterns.append({
                        "compiled": compiled,
                        "reason": reason,
                    })
                except re.error as e:
                    self.logger.warning(
                        "Anti-pattern regex inválido ignorado: '%s' (%s)", regex_str, e
                    )
        except (OSError, json.JSONDecodeError):
            self.logger.warning("Falha ao ler anti_patterns.json")

    # ------------------------------------------------------------------
    # Verificações
    # ------------------------------------------------------------------

    def _is_write_action(self, command: str) -> bool:
        """Verifica se o comando modifica arquivos."""
        return bool(_WRITE_PATTERNS.search(command))

    def _check_anti_patterns(self, text: str) -> list[str]:
        """Checa texto contra anti-patterns pre-compilados."""
        warnings = []
        for pattern in self._anti_patterns:
            compiled = pattern["compiled"]
            reason = pattern["reason"]
            if compiled.search(text):
                warnings.append(f"⚠️ Anti-pattern: {reason} (match: {compiled.pattern})")
        return warnings

    def _run_tests(self) -> dict | None:
        """Executa o test runner do projeto."""
        if not self._test_command:
            return None

        try:
            import shlex
            proc = subprocess.run(
                shlex.split(self._test_command),
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.test_timeout,
                cwd=self.project_root,
            )
            return {
                "returncode": proc.returncode,
                "output": (proc.stdout + "\n" + proc.stderr).strip(),
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "output": f"Testes excederam timeout de {self.test_timeout}s",
            }
        except OSError as e:
            self.logger.warning("Falha ao executar testes: %s", e)
            return None

    # ------------------------------------------------------------------
    # Propriedades
    # ------------------------------------------------------------------

    @property
    def test_command(self) -> str | None:
        """Comando de teste detectado/configurado."""
        return self._test_command

    @property
    def anti_patterns(self) -> list[dict]:
        """Anti-patterns carregados."""
        return list(self._anti_patterns)
