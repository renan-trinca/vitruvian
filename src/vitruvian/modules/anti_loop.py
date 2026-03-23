"""Módulo Anti-Loop (Sistema Cerebelar)

Detecta e interrompe ciclos de retry degenerativos.

Biologia: Inibição lateral cerebelar + período refratário neuronal.
Quando um padrão repetitivo não reduz o gradiente de erro, interneurônios
inibitórios desligam a rota sináptica e forçam nova estratégia.

Componentes:
  1. Action Fingerprinting — hash de cada ação + error_signature
  2. Regra de Inibição — N ações similares com mesmo erro → bloqueia
  3. Período Refratário — injeta prompt override forçando nova abordagem
  4. Exponential Backoff — cada inibição escala a restrição
  5. Circuit Breaker — escala para humano após max_inhibitions
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from vitruvian.exceptions import CircuitBreakerError
from vitruvian.modules.base import Module

# Threshold de similaridade para considerar duas ações "iguais"
DEFAULT_SIMILARITY_THRESHOLD = 0.90

# Número de repetições para disparar inibição
DEFAULT_REPETITION_LIMIT = 3

# Máximo de inibições antes de circuit breaker
DEFAULT_MAX_INHIBITIONS = 3

# Linhas finais do output usadas como error signature
ERROR_SIGNATURE_LINES = 3

# Limite de caracteres para sanitização de output em mensagens refratárias
MAX_SANITIZED_LEN = 500

# Regex para tokens perigosos a remover de outputs antes de injetar no prompt
_DANGEROUS_PATTERN = re.compile(
    r"```|<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>|<\|system\|>|<\|user\|>|<\|assistant\|>",
)

from vitruvian.modules.base import Module, get_prompts

_PROMPTS = get_prompts("anti_loop")


class AntiLoopModule(Module):
    """Detecta loops degenerativos e força mudança de estratégia."""

    def __init__(
        self,
        *,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        repetition_limit: int = DEFAULT_REPETITION_LIMIT,
        max_inhibitions: int = DEFAULT_MAX_INHIBITIONS,
    ) -> None:
        super().__init__(name="anti_loop")

        # --- Validação de inputs (Finding #5) ---
        if repetition_limit < 2:
            msg = f"repetition_limit deve ser >= 2, recebido: {repetition_limit}"
            raise ValueError(msg)
        if max_inhibitions < 1:
            msg = f"max_inhibitions deve ser >= 1, recebido: {max_inhibitions}"
            raise ValueError(msg)
        if not 0.0 <= similarity_threshold <= 1.0:
            msg = f"similarity_threshold deve estar entre 0.0 e 1.0, recebido: {similarity_threshold}"
            raise ValueError(msg)

        self.similarity_threshold = similarity_threshold
        self.repetition_limit = repetition_limit
        self.max_inhibitions = max_inhibitions

        # Estado interno
        self._action_history: list[dict] = []
        self._inhibition_count: int = 0
        self._failed_approaches: list[dict] = []
        self._last_refractory_message: str | None = None

    # ------------------------------------------------------------------
    # Hooks do ciclo de vida
    # ------------------------------------------------------------------

    def post_query(self, message: dict) -> dict | None:
        """Verifica se a resposta do LLM contém ações que formam loop.

        Intercepta ANTES da execução, no nível da resposta do modelo.
        Se loop detectado, retorna None (bloqueia) e prepara mensagem refratária.
        """
        actions = message.get("extra", {}).get("actions", [])
        if not actions:
            return message

        # Verifica cada ação proposta contra o histórico
        for action in actions:
            command = action.get("command", "")
            if not command:
                continue

            if self._is_degenerative(command):
                self._trigger_inhibition(command)
                return None  # Bloqueia toda a resposta

        return message

    def post_action(self, action: dict, result: dict) -> dict:
        """Registra a ação e seu resultado no histórico (fingerprinting)."""
        command = action.get("command", "")
        returncode = result.get("returncode", 0)
        output = result.get("output", "")

        self._action_history.append({
            "command": command,
            "returncode": returncode,
            "error_signature": self._extract_error_signature(output),
            "failed": returncode != 0,
        })

        return result

    def reset(self) -> None:
        """Reseta histórico para nova sessão."""
        self._action_history.clear()
        self._inhibition_count = 0
        self._failed_approaches.clear()
        self._last_refractory_message = None

    # ------------------------------------------------------------------
    # Detecção de loop
    # ------------------------------------------------------------------

    def _is_degenerative(self, command: str) -> bool:
        """Verifica se o comando é parte de um loop degenerativo.

        Condições (todas devem ser verdadeiras):
        1. Existem N-1 ações recentes no histórico
        2. Todas as ações recentes falharam
        3. Todas são similares ao comando proposto (>threshold)
        4. Todas têm a mesma error_signature (falham no MESMO erro)
        """
        recent = self._action_history[-(self.repetition_limit - 1):]

        if len(recent) < (self.repetition_limit - 1):
            return False

        # Todas falharam?
        if not all(entry["failed"] for entry in recent):
            return False

        # Todas similares ao comando proposto?
        if not all(
            self._similarity(command, entry["command"]) >= self.similarity_threshold
            for entry in recent
        ):
            return False

        # Todas com a mesma error_signature? (falham no MESMO erro)
        signatures = [entry["error_signature"] for entry in recent]
        return not signatures[0] or all(
            self._similarity(signatures[0], sig) >= self.similarity_threshold
            for sig in signatures[1:]
        )

    def _trigger_inhibition(self, command: str) -> None:
        """Dispara inibição: incrementa contador e prepara mensagem refratária.

        Escala a restrição a cada inibição (exponential backoff com mutação):
        - 1ª inibição: mensagem refratária simples
        - 2ª inibição: mensagem + lista de TODOS approaches tentados
        - 3ª inibição: circuit breaker → escala para humano
        """
        self._inhibition_count += 1

        # Registra o approach como falhado
        recent = self._action_history[-(self.repetition_limit - 1):]
        error_sig = recent[-1]["error_signature"] if recent else ""
        self._failed_approaches.append({
            "command": command,
            "error_signature": error_sig,
        })

        self.logger.warning(
            "INIBIÇÃO #%d: Loop degenerativo detectado. Comando: %.80s...",
            self._inhibition_count,
            command,
        )

        # Circuit breaker: escala para humano
        if self._inhibition_count >= self.max_inhibitions:
            raise CircuitBreakerError(
                module_name=self.name,
                inhibition_count=self._inhibition_count,
                failed_approaches=self._failed_approaches,
            )

        # --- Sanitização (Finding #2) ---
        safe_command = self._sanitize(command[:120])
        safe_error = self._sanitize(error_sig[:MAX_SANITIZED_LEN])

        # Exponential backoff: escalar mensagem refratária
        if self._inhibition_count >= 2 and len(self._failed_approaches) > 1:
            # 2ª+ inibição: lista todos approaches
            approaches_list = "\n".join(
                f"  - {self._sanitize(a['command'][:80])} → erro: {self._sanitize(a['error_signature'][:80])}"
                for a in self._failed_approaches
            )
            escalation_text = _PROMPTS.get("escalation_full_list", "").format(approaches_list=approaches_list)
        else:
            # 1ª inibição: mensagem simples
            escalation_text = _PROMPTS.get("escalation_simple", "")

        self._last_refractory_message = _PROMPTS.get("refractory_template", "").format(
            inhibition_count=self._inhibition_count,
            n_attempts=self.repetition_limit,
            command=safe_command,
            error_signature=safe_error,
            escalation_text=escalation_text,
        )

    # ------------------------------------------------------------------
    # Propriedades e utilitários
    # ------------------------------------------------------------------

    @property
    def inhibition_count(self) -> int:
        """Quantas vezes a inibição foi disparada nesta sessão."""
        return self._inhibition_count

    @property
    def blocked_message(self) -> str | None:
        """Mensagem refratária gerada quando bloqueia execução."""
        msg = self._last_refractory_message
        self._last_refractory_message = None  # Cosumir depois da leitura
        return msg

    @property
    def failed_approaches(self) -> list[dict]:
        """Lista de approaches que falharam nesta sessão."""
        return list(self._failed_approaches)

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Calcula similaridade entre duas strings (0.0 a 1.0)."""
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _extract_error_signature(output: str) -> str:
        """Extrai as últimas N linhas do output como fingerprint do erro."""
        lines = output.strip().splitlines()
        signature_lines = lines[-ERROR_SIGNATURE_LINES:] if lines else []
        return "\n".join(signature_lines)

    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove tokens perigosos e trunca texto antes de injetar no prompt.

        Previne prompt injection via output de comandos (Finding #2).
        """
        return _DANGEROUS_PATTERN.sub("", text).strip()
