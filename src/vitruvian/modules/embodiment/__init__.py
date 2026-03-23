"""
Camada de Embodiment Contextual (CA3 Pattern Completion)

Biologia: A fração CA3 do hipocampo faz pattern completion. Recebe uma dica
fragmentária e dispara retroativamente todas as redes associadas, reconstruindo
o contexto mental completo sem nova computação analítica.

Software: Escaneia o projeto (arquivos de config, histórico do git) e cria um
schema. Quando o LLM recebe um prompt curto, o motor injeta padrões de projeto
locais (framework correto, regras de estilo observadas) via RAG lightweight (BM25).
"""

from __future__ import annotations

from vitruvian.modules.embodiment.embodiment_module import EmbodimentModule
from vitruvian.modules.embodiment.scanner import ProjectScanner, SchemaBuilder

__all__ = [
    "EmbodimentModule",
    "ProjectScanner",
    "SchemaBuilder",
]
