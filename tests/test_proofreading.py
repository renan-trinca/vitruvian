"""Testes para o módulo Proofreading (Motor Exonuclease).

Cobre as 2 camadas:
  Camada 1: Tech Stack Validator (pre_query + post_query)
  Camada 3: Mismatch Repair (post_action + anti-patterns)
"""

import json

import pytest

from vitruvian.modules.proofreading.mismatch_repair import MismatchRepairModule
from vitruvian.modules.proofreading.tech_stack_validator import TechStackValidatorModule

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def python_project(tmp_path):
    """Cria um projeto Python fake com requirements.txt e pyproject.toml."""
    (tmp_path / "requirements.txt").write_text("flask>=2.0\nrequests\npytest\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test"\ndependencies = ["click>=8.0"]\n\n'
        "[tool.ruff]\nline-length = 120\n\n"
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"
    )
    return tmp_path


@pytest.fixture
def js_project(tmp_path):
    """Cria um projeto JS fake com package.json."""
    pkg = {
        "name": "test-app",
        "dependencies": {"react": "^18.0", "axios": "^1.0"},
        "devDependencies": {"eslint": "^8.0"},
        "scripts": {"test": "jest"},
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    (tmp_path / ".eslintrc.json").write_text("{}")
    (tmp_path / "tsconfig.json").write_text("{}")
    return tmp_path


@pytest.fixture
def empty_project(tmp_path):
    """Projeto vazio sem manifests."""
    return tmp_path


# ──────────────────────────────────────────────
# Camada 1: Tech Stack Validator
# ──────────────────────────────────────────────

class TestTechStackDetection:

    def test_detects_requirements_txt(self, python_project):
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        assert "flask" in mod.known_deps
        assert "requests" in mod.known_deps
        assert "pytest" in mod.known_deps

    def test_detects_pyproject_toml_deps(self, python_project):
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        assert "click" in mod.known_deps

    def test_detects_package_json(self, js_project):
        mod = TechStackValidatorModule(project_root=js_project)
        mod.reset()
        mod._scan_project()
        assert "react" in mod.known_deps
        assert "axios" in mod.known_deps
        assert "eslint" in mod.known_deps

    def test_detects_config_rules(self, js_project):
        mod = TechStackValidatorModule(project_root=js_project)
        mod.reset()
        mod._scan_project()
        assert any("eslintrc" in r for r in mod.style_rules)
        assert any("tsconfig" in r for r in mod.style_rules)

    def test_detects_ruff_config(self, python_project):
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        assert any("line-length=120" in r for r in mod.style_rules)


class TestTechStackPreQuery:

    def test_injects_deps_in_pre_query(self, python_project):
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        messages = [{"role": "system", "content": "You are an agent."}]
        result = mod.pre_query(messages)
        # Deve ter injetado uma mensagem a mais
        assert len(result) == 2
        injected = result[1]
        assert injected["role"] == "system"
        assert "flask" in injected["content"]
        assert "requests" in injected["content"]

    def test_no_manifest_no_injection(self, empty_project):
        mod = TechStackValidatorModule(project_root=empty_project)
        mod.reset()
        messages = [{"role": "system", "content": "You are an agent."}]
        result = mod.pre_query(messages)
        assert len(result) == 1  # Nenhuma injeção

    def test_handles_malformed_manifest(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("|||invalid|||")
        (tmp_path / "package.json").write_text("{invalid json")
        mod = TechStackValidatorModule(project_root=tmp_path)
        mod.reset()
        # Não deve crash
        mod._scan_project()


class TestTechStackPostQuery:

    def test_redirects_unknown_lib_in_post_query(self, python_project):
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        message = {
            "role": "assistant",
            "content": "Vou instalar django...",
            "extra": {"actions": [{"command": "pip install django"}]},
        }
        result = mod.post_query(message)
        assert result is None
        bmsg = mod.blocked_message
        assert bmsg is not None
        assert "django" in bmsg

    def test_allows_known_lib(self, python_project):
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        message = {
            "role": "assistant",
            "content": "Instalando flask...",
            "extra": {"actions": [{"command": "pip install flask"}]},
        }
        result = mod.post_query(message)
        assert result is not None  # Não bloqueou

    def test_reset_rescans_project(self, python_project):
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        assert "flask" in mod.known_deps

        mod.reset()
        assert len(mod.known_deps) == 0
        assert not mod._scan_done


# ──────────────────────────────────────────────
# Camada 3: Mismatch Repair
# ──────────────────────────────────────────────

class TestMismatchRepairDetection:

    def test_detects_pytest_runner(self, python_project):
        mod = MismatchRepairModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        assert mod.test_command is not None
        assert "pytest" in mod.test_command

    def test_detects_npm_test_runner(self, js_project):
        mod = MismatchRepairModule(project_root=js_project)
        mod.reset()
        mod._scan_project()
        assert mod.test_command == "npm test"

    def test_no_runner_in_empty_project(self, empty_project):
        mod = MismatchRepairModule(project_root=empty_project)
        mod.reset()
        mod._scan_project()
        assert mod.test_command is None

    def test_reset_redetects_runner(self, python_project):
        mod = MismatchRepairModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        assert mod.test_command is not None

        mod.reset()
        assert mod.test_command is None
        assert not mod._scan_done


class TestMismatchRepairPostAction:

    def test_skips_tests_for_read_actions(self, python_project):
        """Ações de leitura NÃO disparam testes."""
        mod = MismatchRepairModule(project_root=python_project)
        mod.reset()
        action = {"command": "cat README.md"}
        result = {"output": "# README", "returncode": 0}
        output = mod.post_action(action, result)
        assert "proofreading_warnings" not in output.get("extra", {})

    def test_runs_tests_after_write_action(self, python_project):
        """Ações de escrita DISPARAM testes."""
        mod = MismatchRepairModule(project_root=python_project, test_command="echo PASS")
        mod.reset()
        action = {"command": "cat > main.py << 'EOF'\nprint('hello')\nEOF"}
        result = {"output": "ok", "returncode": 0}
        output = mod.post_action(action, result)
        assert "test_result" in output.get("extra", {})
        assert output["extra"]["test_result"]["returncode"] == 0

    def test_anti_pattern_warning_injected(self, tmp_path):
        """Anti-pattern match gera warning."""
        ap_path = tmp_path / ".vitruvian" / "anti_patterns.json"
        ap_path.parent.mkdir(parents=True)
        ap_path.write_text(json.dumps([
            {"regex": "verify=False", "reason": "SSL bypass detectado"}
        ]))
        mod = MismatchRepairModule(
            project_root=tmp_path, anti_patterns_path=ap_path
        )
        mod.reset()
        action = {"command": "cat > fetch.py << 'EOF'\nrequests.get(url, verify=False)\nEOF"}
        result = {"output": "ok", "returncode": 0}
        output = mod.post_action(action, result)
        warnings = output.get("extra", {}).get("proofreading_warnings", [])
        assert len(warnings) >= 1
        assert "SSL bypass" in warnings[0]

    def test_no_anti_patterns_file_ok(self, empty_project):
        """Sem registry de anti-patterns → funciona normalmente."""
        mod = MismatchRepairModule(project_root=empty_project)
        mod.reset()
        action = {"command": "echo 'hello' > test.txt"}
        result = {"output": "ok", "returncode": 0}
        output = mod.post_action(action, result)
        assert output is not None


# ──────────────────────────────────────────────
# Audit Round 2: Regression Tests
# ──────────────────────────────────────────────

class TestAuditRound2Regressions:

    def test_redirect_reaches_agent(self, python_project):
        """Finding #2: blocked_message deve ser injetado pelo agent."""
        from vitruvian.agents.vitruvian_agent import VitruvianAgent

        validator = TechStackValidatorModule(project_root=python_project)

        class MockModel:
            def format_message(self, role, content, extra=None):
                return {"role": role, "content": content, "extra": extra or {}}

            def query(self, messages):
                return {
                    "role": "assistant",
                    "content": "Instalando django...",
                    "extra": {"actions": [{"command": "pip install django"}]},
                }

            def format_observation_messages(self, message, outputs, template_vars):
                return [{"role": "user", "content": str(outputs)}]

            def get_template_vars(self):
                return {}

            def serialize(self):
                return {}

        class MockEnv:
            def execute(self, action):
                return {"output": "ok", "returncode": 0}

            def get_template_vars(self):
                return {}

            def serialize(self):
                return {}

        agent = VitruvianAgent(
            MockModel(),
            MockEnv(),
            modules=[validator],
            system_template="test",
            instance_template="test",
            step_limit=1,
        )
        agent.messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"},
        ]
        agent.step()

        # O blocked_message deve ter sido injetado no histórico
        system_msgs = [
            m for m in agent.messages
            if m.get("role") == "system" and "VITRUVIAN INTERNAL" in m.get("content", "")
        ]
        assert len(system_msgs) >= 1
        assert "django" in system_msgs[-1]["content"]

    def test_invalid_regex_skipped(self, tmp_path):
        """Finding #4: regex malformado não crasheia, é ignorado."""
        ap_path = tmp_path / "anti_patterns.json"
        ap_path.write_text(json.dumps([
            {"regex": "([a-z", "reason": "broken regex"},
            {"regex": "verify=False", "reason": "SSL bypass"},
        ]))
        mod = MismatchRepairModule(
            project_root=tmp_path, anti_patterns_path=ap_path
        )
        mod.reset()
        mod._scan_project()
        # Apenas o pattern válido deve ter sido carregado
        assert len(mod.anti_patterns) == 1

    def test_pre_query_idempotent(self, python_project):
        """Finding #5: 3 chamadas consecutivas = mesma quantidade de mensagens."""
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        messages = [{"role": "system", "content": "You are an agent."}]

        result1 = mod.pre_query(messages)
        result2 = mod.pre_query(result1)
        result3 = mod.pre_query(result2)

        assert len(result1) == len(result2) == len(result3) == 2

    def test_pip_install_with_flags(self, python_project):
        """Finding #6: pip install -U django deve ser detectado."""
        mod = TechStackValidatorModule(project_root=python_project)
        mod.reset()
        mod._scan_project()
        message = {
            "role": "assistant",
            "content": "Upgrade...",
            "extra": {"actions": [{"command": "pip install -U django"}]},
        }
        result = mod.post_query(message)
        assert result is None
        bmsg = mod.blocked_message
        assert bmsg is not None
        assert "django" in bmsg

class TestAuditRound3Regressions:
    def test_tech_stack_normalizes_version_markers(self, tmp_path):
        """Regression para Finding #3: TechStackValidator bloqueando dependências com versões."""
        mod = TechStackValidatorModule(project_root=tmp_path)
        mod._known_deps = {"requests", "react", "@types/node"}

        # Não deve bloquear requests>=2.0
        msg = {
            "role": "assistant",
            "extra": {"actions": [{"command": "pip install requests>=2.0"}]}
        }
        res = mod.post_query(msg)
        assert res is not None

        # Não deve bloquear requests[extras]
        msg2 = {
            "role": "assistant",
            "extra": {"actions": [{"command": "pip install requests[socks]"}]}
        }
        assert mod.post_query(msg2) is not None

        # Não deve bloquear react@18
        msg3 = {
            "role": "assistant",
            "extra": {"actions": [{"command": "npm install react@18"}]}
        }
        assert mod.post_query(msg3) is not None

        # Não deve bloquear @types/node@latest
        msg4 = {
            "role": "assistant",
            "extra": {"actions": [{"command": "npm install @types/node@16"}]}
        }
        assert mod.post_query(msg4) is not None

    def test_mismatch_repair_detects_expanded_write_actions(self, tmp_path):
        """Regression para Finding #4: MismatchRepair não pegando comandos básicos de escrita."""
        mod = MismatchRepairModule(project_root=tmp_path)

        assert mod._is_write_action("touch file.txt")
        assert mod._is_write_action("mkdir -p newdir")
        assert mod._is_write_action("curl -sL url -o file")
        assert mod._is_write_action("python -c \"open('x','w').write('1')\"")
        assert mod._is_write_action("python3 -c \"with open('y', 'a') as f: f.write('oi')\"")

        assert not mod._is_write_action("ls -la")
        assert not mod._is_write_action("cat file.txt")
