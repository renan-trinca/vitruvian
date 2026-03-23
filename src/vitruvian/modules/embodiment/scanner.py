"""Project Scanner e Schema Builder para o módulo Embodiment."""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

logger = logging.getLogger("vitruvian.embodiment.scanner")


@dataclass
class Document:
    """Um documento (pattern, regra ou convention) indexável."""
    id: str
    content: str
    source: str
    tokens: list[str]


class ProjectScanner:
    """Escaneia repositório em busca de padrões e convenções."""

    def __init__(self, root: Path):
        self.root = root

    def scan(self) -> list[Document]:
        """Varre o projeto para extrair knowledge items."""
        docs = []

        # 1. Convenções explícitas
        docs.extend(self._scan_markdowns())

        # 2. Configs e Tech Stack
        docs.extend(self._scan_configs())

        # 3. Git History (últimos 50 commits)
        docs.extend(self._scan_git_history())

        return docs

    def _scan_markdowns(self) -> list[Document]:
        docs = []
        target_files = ["CONVENTIONS.md", "ARCHITECTURE.md", "README.md", "CONTRIBUTING.md"]
        for filename in target_files:
            p = self.root / filename
            if p.exists():
                try:
                    content = p.read_text()
                    docs.append(
                        Document(
                            id=f"doc_{filename.lower()}",
                            content=content[:2000],  # limite
                            source=filename,
                            tokens=self._tokenize(content),
                        )
                    )
                except OSError as e:
                    logger.warning("Falha ao ler %s: %s", filename, e)
        return docs

    def _scan_configs(self) -> list[Document]:
        docs = []

        # package.json scripts (revelam commands úteis do ecossistema local)
        pkg = self.root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                scripts = data.get("scripts", {})
                if scripts:
                    content = "NPM Scripts disponíveis no projeto:\n"
                    for k, v in scripts.items():
                        content += f"- npm run {k}: {v}\n"
                    docs.append(Document(
                        id="config_npm_scripts",
                        content=content,
                        source="package.json",
                        tokens=self._tokenize(content),
                    ))
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Falha ao analisar package.json no scanner: %s", e)

        # TODO: Adicionar tsconfig, ruff, etc
        return docs

    def _scan_git_history(self) -> list[Document]:
        """Extrai lições de estilo e co-ocorrência dos últimos 50 commits."""
        docs = []
        try:
            # git log exibindo a mensagem do commit e quais arquivos mudaram
            proc = subprocess.run(
                ["git", "log", "-n", "30", "--name-status", "--oneline"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout:
                # Vamos criar um doc massivo representando o histórico recente,
                # para que buscas por ações recentes tragam contexto de arquivos.
                content = "Git History Recente (arquivos frequentemente tocados):\n"

                # Apenas as primeiras 50 linhas para não explodir
                lines = proc.stdout.splitlines()[:50]
                content += "\n".join(lines)

                docs.append(Document(
                    id="git_history_recent",
                    content=content,
                    source="git log",
                    tokens=self._tokenize(content),
                ))
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning("Falha ao extrair git history: %s", e)

        return docs

    def _tokenize(self, text: str) -> list[str]:
        """Tokenização simples para BM25 fallback."""
        text = text.lower()
        # Remove pontuação básica apenas no início/fim das palavras, preservando hífens
        import re
        tokens = re.findall(r'\b\w+\b', text)
        return [w for w in tokens if len(w) > 2]


class SchemaBuilder:
    """Indexa e provê busca rápida via BM25."""

    def __init__(self, docs: list[Document]):
        self.docs = docs
        self.bm25 = None

        if self.docs:
            corpus = [doc.tokens for doc in self.docs]
            self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_n: int = 2) -> list[Document]:
        """Retorna os top N documentos relevantes para a query."""
        if not self.docs or not self.bm25:
            return []

        # Busca real BM25
        import re
        tokens = re.findall(r'\b\w+\b', query.lower())
        tokenized_query = [w for w in tokens if len(w) > 2]

        # Obter scores
        scores = self.bm25.get_scores(tokenized_query)
        scored = list(zip(self.docs, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        # Num corpus minúsculo (testes), BM25 pode retornar 0
        # Retorna o top N mesmo se score for baixo, contanto que exista overlap lexical real
        # ou se for fallback
        final_docs = []
        for doc, score in scored:
            if score > 0 or any(t in doc.tokens for t in tokenized_query):
                final_docs.append(doc)

        return final_docs[:top_n]
