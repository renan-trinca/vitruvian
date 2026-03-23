"""Testes para o módulo Anti-Loop (Sistema Cerebelar).

Cobre os 5 componentes:
  1. Action Fingerprinting (com error_signature)
  2. Regra de Inibição
  3. Período Refratário (prompt override)
  4. Exponential Backoff com Mutação
  5. Circuit Breaker
"""

import pytest

from vitruvian.exceptions import CircuitBreakerError
from vitruvian.modules.anti_loop import AntiLoopModule

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _simulate_failed_action(mod: AntiLoopModule, command: str, output: str = "Error: something failed") -> None:
    """Registra uma ação que falhou no histórico do módulo."""
    mod.post_action({"command": command}, {"returncode": 1, "output": output})


def _simulate_successful_action(mod: AntiLoopModule, command: str) -> None:
    """Registra uma ação que passou no histórico do módulo."""
    mod.post_action({"command": command}, {"returncode": 0, "output": "OK"})


def _make_message_with_action(command: str) -> dict:
    """Cria uma mensagem de resposta do LLM com uma ação."""
    return {
        "role": "assistant",
        "content": "Tentando...",
        "extra": {"actions": [{"command": command}]},
    }


# ──────────────────────────────────────────────
# 1. Fingerprinting e Regra de Inibição
# ──────────────────────────────────────────────

class TestFingerprinting:

    def test_allows_first_action(self):
        """Primeira ação sempre deve passar — sem histórico para comparar."""
        mod = AntiLoopModule()
        msg = _make_message_with_action("python -m pytest tests/")
        assert mod.post_query(msg) is not None

    def test_allows_different_actions(self):
        """Ações diferentes não devem acionar inibição."""
        mod = AntiLoopModule()
        _simulate_failed_action(mod, "python -m pytest tests/")
        _simulate_failed_action(mod, "cat README.md")

        msg = _make_message_with_action("ls -la")
        assert mod.post_query(msg) is not None

    def test_allows_similar_actions_that_succeed(self):
        """Ações similares que PASSAM não devem acionar inibição."""
        mod = AntiLoopModule()
        for _ in range(3):
            _simulate_successful_action(mod, "python -m pytest tests/test_main.py")

        msg = _make_message_with_action("python -m pytest tests/test_main.py")
        assert mod.post_query(msg) is not None

    def test_blocks_degenerative_loop(self):
        """N ações similares consecutivas que falharam com mesmo erro → BLOQUEIO."""
        mod = AntiLoopModule(repetition_limit=3)
        error_output = "FAILED tests/test_main.py::test_foo\nAssertionError: 1 != 2\nERROR"

        _simulate_failed_action(mod, "pytest tests/test_main.py -v", error_output)
        _simulate_failed_action(mod, "pytest tests/test_main.py -v  ", error_output)

        msg = _make_message_with_action("pytest tests/test_main.py -v")
        assert mod.post_query(msg) is None
        assert mod.inhibition_count == 1

    def test_same_error_signature_triggers_inhibition(self):
        """Ações similares com MESMA error_signature → bloqueio."""
        mod = AntiLoopModule(repetition_limit=2)
        same_error = "line 42\nTypeError: cannot add int and str\nFAILED"

        _simulate_failed_action(mod, "python run.py", same_error)

        msg = _make_message_with_action("python run.py")
        assert mod.post_query(msg) is None

    def test_different_error_signatures_no_inhibition(self):
        """Ações similares mas com erros DIFERENTES → continua (não é loop)."""
        mod = AntiLoopModule(repetition_limit=3)

        # Duas falhas com erros DIFERENTES
        _simulate_failed_action(mod, "python run.py", "Error A\nTypeError\nline 10")
        _simulate_failed_action(mod, "python run.py", "Error B\nValueError\nline 99")

        # Terceira tentativa: não deve bloquear porque os erros são diferentes
        msg = _make_message_with_action("python run.py")
        result = mod.post_query(msg)
        assert result is not None, "Erros diferentes não devem disparar inibição"


class TestReset:

    def test_reset_clears_state(self):
        """Reset deve limpar todo o estado do módulo."""
        mod = AntiLoopModule(repetition_limit=2)
        _simulate_failed_action(mod, "make build")

        msg = _make_message_with_action("make build")
        assert mod.post_query(msg) is None
        assert mod.inhibition_count == 1

        mod.reset()

        assert mod.inhibition_count == 0
        assert mod.blocked_message is None
        assert mod.failed_approaches == []
        # Após reset, mesma ação deve passar
        assert mod.post_query(msg) is not None


# ──────────────────────────────────────────────
# 3. Período Refratário
# ──────────────────────────────────────────────

class TestRefractoryPeriod:

    def test_blocked_message_lists_failed_command(self):
        """Mensagem refratária deve mencionar o comando que falhou."""
        mod = AntiLoopModule(repetition_limit=2)
        _simulate_failed_action(mod, "make build", "error: undefined reference\nld returned 1")

        msg = _make_message_with_action("make build")
        mod.post_query(msg)

        bmsg = mod.blocked_message
        assert bmsg is not None
        assert "make build" in bmsg
        assert "fundamentalmente distinta" in bmsg


# ──────────────────────────────────────────────
# 4. Exponential Backoff
# ──────────────────────────────────────────────

class TestExponentialBackoff:

    def test_escalating_backoff(self):
        """1ª inibição = simples, 2ª = lista todos approaches."""
        mod = AntiLoopModule(repetition_limit=2, max_inhibitions=5)

        # 1ª inibição
        _simulate_failed_action(mod, "make build", "error 1\nfail\nstop")
        mod.post_query(_make_message_with_action("make build"))
        first_msg = mod.blocked_message
        assert "Approaches já tentados" not in first_msg

        # 2ª inibição (com approach diferente)
        _simulate_failed_action(mod, "cargo test", "error 2\nfail\nstop")
        mod.post_query(_make_message_with_action("cargo test"))
        second_msg = mod.blocked_message
        assert "Approaches já tentados" in second_msg
        assert "make build" in second_msg
        assert "cargo test" in second_msg


# ──────────────────────────────────────────────
# 5. Circuit Breaker
# ──────────────────────────────────────────────

class TestCircuitBreaker:

    def test_circuit_breaker_trips_after_max_inhibitions(self):
        """3ª inibição → CircuitBreakerError."""
        mod = AntiLoopModule(repetition_limit=2, max_inhibitions=3)

        # Inibição 1
        _simulate_failed_action(mod, "cmd1", "err\nfail\nstop")
        mod.post_query(_make_message_with_action("cmd1"))

        # Inibição 2
        _simulate_failed_action(mod, "cmd2", "err\nfail\nstop")
        mod.post_query(_make_message_with_action("cmd2"))

        # Inibição 3 → circuit breaker
        _simulate_failed_action(mod, "cmd3", "err\nfail\nstop")
        with pytest.raises(CircuitBreakerError) as exc_info:
            mod.post_query(_make_message_with_action("cmd3"))

        assert exc_info.value.inhibition_count == 3
        assert len(exc_info.value.failed_approaches) == 3

    def test_circuit_breaker_agent_exits_cleanly(self):
        """Integração: agent para com status CircuitBreaker."""
        from vitruvian.agents.vitruvian_agent import VitruvianAgent

        anti_loop = AntiLoopModule(repetition_limit=2, max_inhibitions=2)

        class MockModel:
            def format_message(self, role, content, extra=None):
                return {"role": role, "content": content, "extra": extra or {}}

            def query(self, messages):
                # Sempre retorna o mesmo comando para disparar loop
                return {
                    "role": "assistant",
                    "content": "Tentando...",
                    "extra": {"actions": [{"command": "make build"}]},
                }

            def format_observation_messages(self, message, outputs, template_vars):
                return [{"role": "user", "content": str(outputs)}]

            def get_template_vars(self):
                return {}

            def serialize(self):
                return {}

        class MockEnv:
            def execute(self, action):
                return {"output": "error\nfail\nstop", "returncode": 1}

            def get_template_vars(self):
                return {}

            def serialize(self):
                return {}

        agent = VitruvianAgent(
            MockModel(),
            MockEnv(),
            modules=[anti_loop],
            system_template="test",
            instance_template="test",
            step_limit=20,
        )

        result = agent.run("test task")
        assert result.get("exit_status") == "CircuitBreaker"


# ──────────────────────────────────────────────
# Audit Fixes: Validation, Sanitization, History
# ──────────────────────────────────────────────


class TestInputValidation:
    """Finding #5: repetition_limit=1 e params inválidos devem levantar ValueError."""

    def test_invalid_repetition_limit_zero(self):
        with pytest.raises(ValueError, match="repetition_limit"):
            AntiLoopModule(repetition_limit=0)

    def test_invalid_repetition_limit_one(self):
        with pytest.raises(ValueError, match="repetition_limit"):
            AntiLoopModule(repetition_limit=1)

    def test_invalid_max_inhibitions_zero(self):
        with pytest.raises(ValueError, match="max_inhibitions"):
            AntiLoopModule(max_inhibitions=0)

    def test_invalid_threshold_negative(self):
        with pytest.raises(ValueError, match="similarity_threshold"):
            AntiLoopModule(similarity_threshold=-0.1)

    def test_invalid_threshold_above_one(self):
        with pytest.raises(ValueError, match="similarity_threshold"):
            AntiLoopModule(similarity_threshold=1.5)

    def test_valid_edge_cases(self):
        """Valores-limite válidos não devem levantar erro."""
        AntiLoopModule(repetition_limit=2, max_inhibitions=1, similarity_threshold=0.0)
        AntiLoopModule(repetition_limit=2, max_inhibitions=1, similarity_threshold=1.0)


class TestSanitization:
    """Finding #2: Tokens perigosos devem ser removidos de mensagens refratárias."""

    def test_dangerous_tokens_stripped_from_refractory(self):
        mod = AntiLoopModule(repetition_limit=2)
        dangerous_output = "```python\nimport os; os.system('rm -rf /')\n```"
        _simulate_failed_action(mod, "python run.py", dangerous_output)

        msg = _make_message_with_action("python run.py")
        mod.post_query(msg)

        bmsg = mod.blocked_message
        assert bmsg is not None
        assert "```" not in bmsg


class TestHistorySync:
    """Finding #4: post_query que retorna dict diferente deve sincronizar histórico."""

    def test_post_query_replacement_synced(self):
        from vitruvian.agents.vitruvian_agent import VitruvianAgent
        from vitruvian.modules.base import Module

        class TransformModule(Module):
            """Módulo que transforma a resposta do modelo."""

            def post_query(self, message: dict) -> dict:
                return {**message, "content": "TRANSFORMED"}

            def reset(self):
                pass

        class MockModel:
            def format_message(self, role, content, extra=None):
                return {"role": role, "content": content, "extra": extra or {}}

            def query(self, messages):
                return {
                    "role": "assistant",
                    "content": "Original",
                    "extra": {"actions": [{"command": "echo test"}]},
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
            modules=[TransformModule("transform")],
            system_template="test",
            instance_template="test",
            step_limit=1,
        )

        agent.messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"},
        ]
        agent.step()

        # O histórico deve conter "TRANSFORMED", não "Original"
        assistant_msgs = [m for m in agent.messages if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "TRANSFORMED"
