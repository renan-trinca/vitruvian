"""
Vitruvian Module Interface

Todos os módulos bio-inspirados (Anti-Loop, Proofreading, Embodiment)
devem implementar esta interface para se conectar ao VitruvianAgent.
"""

from __future__ import annotations

import logging
import yaml
from pathlib import Path
from abc import ABC, abstractmethod

_PROMPTS_FILE = Path(__file__).parent.parent / "config" / "prompts.yaml"
_PROMPTS_CACHE = None

def get_prompts(module_name: str) -> dict:
    """Carrega strings escalonadas em cache de config/prompts.yaml"""
    global _PROMPTS_CACHE
    if _PROMPTS_CACHE is None:
        if _PROMPTS_FILE.exists():
            with open(_PROMPTS_FILE, encoding="utf-8") as f:
                _PROMPTS_CACHE = yaml.safe_load(f) or {}
        else:
            _PROMPTS_CACHE = {}
    return _PROMPTS_CACHE.get(module_name, {})


class Module(ABC):
    """Interface base para módulos bio-inspirados do Vitruvian.

    Cada módulo opera em um ponto específico do ciclo do agente:
    - pre_query:   antes de enviar mensagens ao LLM (ex: Embodiment injeta contexto)
    - post_query:  depois de receber resposta do LLM, antes de executar (ex: Proofreading Camada 1)
    - pre_action:  antes de executar cada ação (ex: Anti-Loop verifica repetição)
    - post_action: depois de executar cada ação (ex: Proofreading Camada 3)
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = logging.getLogger(f"vitruvian.{name}")
        self.enabled = True

    def pre_query(self, messages: list[dict]) -> list[dict]:
        """Hook chamado ANTES de enviar mensagens ao modelo.

        Pode modificar as mensagens (ex: injetar contexto do projeto).
        Retorna as mensagens (modificadas ou não).
        """
        return messages

    def post_query(self, message: dict) -> dict | None:
        """Hook chamado DEPOIS de receber resposta do modelo, ANTES de executar.

        Pode inspecionar/modificar a resposta.
        Retorna None para bloquear a execução (período refratário).
        Retorna o message (modificado ou não) para continuar.
        """
        return message

    def pre_action(self, action: dict) -> dict:
        """Hook chamado ANTES de executar uma ação no ambiente."""
        return action

    def post_action(self, action: dict, result: dict) -> dict:
        """Hook chamado DEPOIS de executar uma ação no ambiente."""
        return result

    @property
    def blocked_message(self) -> str | None:
        return None

    @abstractmethod
    def reset(self) -> None:
        """Reseta o estado interno do módulo para uma nova sessão."""
        ...

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__} ({status})>"
