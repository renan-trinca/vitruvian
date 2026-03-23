"""Testes para o módulo Embodiment (Contexto CA3)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vitruvian.modules.embodiment.embodiment_module import EmbodimentModule
from vitruvian.modules.embodiment.scanner import ProjectScanner, SchemaBuilder


@pytest.fixture
def mock_repo(tmp_path: Path):
    """Cria scaffolds de um repositório para testar o Embodiment."""
    # 1. Configs
    pkg = {
        "scripts": {
            "dev": "vite",
            "build": "tsc && vite build",
            "db:push": "drizzle-kit push",
        }
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg))

    # 2. Conventions explícitas
    (tmp_path / "CONVENTIONS.md").write_text(
        "Use sempre camelCase para funções e PascalCase para componentes.\n"
        "Prefira `fetch` nativo no lugar de `axios`."
    )

    return tmp_path


class TestProjectScanner:
    def test_scans_markdowns(self, mock_repo):
        scanner = ProjectScanner(mock_repo)
        docs = scanner._scan_markdowns()
        assert len(docs) == 1
        assert docs[0].id == "doc_conventions.md"
        assert "camelCase" in docs[0].content

    def test_scans_configs(self, mock_repo):
        scanner = ProjectScanner(mock_repo)
        docs = scanner._scan_configs()
        assert len(docs) == 1
        assert "drizzle-kit push" in docs[0].content

    @patch("subprocess.run")
    def test_scans_git_history(self, mock_run, mock_repo):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "a1b2c3d Fix bug in auth\n M src/auth.ts\n"
        mock_run.return_value = mock_result

        scanner = ProjectScanner(mock_repo)
        docs = scanner._scan_git_history()
        assert len(docs) == 1
        assert "src/auth.ts" in docs[0].content


class TestSchemaBuilder:
    def test_bm25_search_prioritizes_relevance(self, mock_repo):
        scanner = ProjectScanner(mock_repo)
        docs = scanner.scan()
        builder = SchemaBuilder(docs)

        # "fetch" e "axios" estão no CONVENTIONS.md
        results1 = builder.search("Como faço um request API? Uso axios?", top_n=1)
        assert len(results1) == 1
        assert results1[0].id == "doc_conventions.md"

        # "drizzle" e "build" estão no package.json
        results2 = builder.search("Como eu faço build e rodo o drizzle?", top_n=1)
        assert len(results2) == 1
        assert results2[0].id == "config_npm_scripts"


class TestEmbodimentModule:
    def test_pre_query_injects_embodiment_context(self, mock_repo):
        mod = EmbodimentModule(project_root=mock_repo)
        messages = [
            {"role": "system", "content": "You are a coding agent."},
            {"role": "user", "content": "Crie uma nova query no banco de dados com drizzle."},
        ]

        result = mod.pre_query(messages)

        # Inseriu logo após a system message original
        assert len(result) == 3
        injected = result[1]

        assert injected["role"] == "user"
        assert "VITRUVIAN CONTEXT" in injected["content"]
        assert "drizzle" in injected["content"]
        assert injected["extra"]["vitruvian_tag"] == "vitruvian_embodiment_context"

    def test_pre_query_idempotent_injection(self, mock_repo):
        """Verifica se injeção substitui em vez de adicionar infinitamente."""
        mod = EmbodimentModule(project_root=mock_repo)
        messages = [
            {"role": "user", "content": "Crie um botão usando axios."},
        ]

        # Call 1
        m1 = mod.pre_query(messages)
        assert len(m1) == 2

        # Call 2 (simulando mesmo round)
        m2 = mod.pre_query(m1)
        assert len(m2) == 2  # Não estourou pra 3
        assert m2[0]["extra"]["vitruvian_tag"] == "vitruvian_embodiment_context"

    def test_no_docs_found_no_injection(self, tmp_path):
        """Projeto totalmente em branco = nenhuma injeção."""
        mod = EmbodimentModule(project_root=tmp_path)
        messages = [{"role": "user", "content": "hello"}]
        result = mod.pre_query(messages)
        assert len(result) == 1
        assert result == messages
