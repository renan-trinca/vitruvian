"""Exceções do Vitruvian."""

from __future__ import annotations


class CircuitBreakerError(Exception):
    """Levantada quando o Anti-Loop esgota todas as tentativas.

    O agente deve capturar esta exceção e converter em saída limpa
    com exit_status="CircuitBreaker".
    """

    def __init__(
        self,
        module_name: str,
        inhibition_count: int,
        failed_approaches: list[dict],
    ) -> None:
        self.module_name = module_name
        self.inhibition_count = inhibition_count
        self.failed_approaches = failed_approaches
        super().__init__(
            f"Circuit breaker tripped by {module_name}: "
            f"{inhibition_count} loops detectados, "
            f"{len(failed_approaches)} approaches falharam"
        )
