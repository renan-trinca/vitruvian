"""Módulo de Embodiment via Pattern Completion."""

import logging
from pathlib import Path

from vitruvian.modules.base import Module, get_prompts
from vitruvian.modules.embodiment.scanner import ProjectScanner, SchemaBuilder

logger = logging.getLogger("vitruvian.embodiment")

_EMBODIMENT_TAG = "vitruvian_embodiment_context"
_PROMPTS = get_prompts("embodiment")


class EmbodimentModule(Module):
    """(Camada CA3) Injeta padrões do projeto para evitar código alienígena."""

    def __init__(self, *, project_root: Path | str) -> None:
        super().__init__(name="embodiment")
        self.project_root = Path(project_root)
        self.scanner = ProjectScanner(self.project_root)
        self.schema: SchemaBuilder | None = None
        self._scan_done = False

    def pre_query(self, messages: list[dict]) -> list[dict]:
        """Intercepta o prompt e tenta correlacionar com padrões do projeto."""
        if not self._scan_done:
            self._init_schema()

        if not self.schema or not self.schema.docs:
            return messages

        # Qual a intenção do LLM ou do user?
        # Para um agente, o último Assistant ou User message diz o que vamos fazer
        query = self._extract_intent(messages)
        if not query:
            return messages

        # Busca os Top 2 docs mais relevantes no repo para aquela intenção
        top_docs = self.schema.search(query, top_n=2)
        if not top_docs:
            return messages

        # Formata os matches encontrados
        blocks = []
        for doc in top_docs:
            blocks.append(f"--- Fonte: {doc.source} ---\n{doc.content.strip()}")

        context_msg = {
            "role": "user",
            "content": _PROMPTS.get("template", "").format(context="\n\n".join(blocks)),
            "extra": {"vitruvian_tag": _EMBODIMENT_TAG},
        }

        # Idempotente: Substitui se já houver um context anterior
        for i, msg in enumerate(messages):
            if msg.get("extra", {}).get("vitruvian_tag") == _EMBODIMENT_TAG:
                messages[i] = context_msg
                return messages

        # Inserção inicial: logo após a system prompt principal se houver
        insert_idx = 1 if messages and messages[0].get("role") == "system" else 0
        return [*messages[:insert_idx], context_msg, *messages[insert_idx:]]

    def post_query(self, message: dict) -> dict | None:
        return message

    def reset(self) -> None:
        self.schema = None
        self._scan_done = False

    def _init_schema(self) -> None:
        """Faz a extração de dados e constrói o índice BM25 na memória."""
        self._scan_done = True
        docs = self.scanner.scan()
        if docs:
            self.schema = SchemaBuilder(docs)
            logger.info("Embodiment schema construído com %d docs", len(docs))
        else:
            logger.info("Embodiment schema vazio (nenhum padrão extraído)")

    def _extract_intent(self, messages: list[dict]) -> str:
        """Extrai o último pedido / step description para usar como query no RAG."""
        for msg in reversed(messages):
            role = msg.get("role", "")
            if role in ("user", "assistant"):
                text = msg.get("content", "")
                if isinstance(text, str) and len(text) > 5:
                    return text
        return ""
