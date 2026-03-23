# Vitruvian Agent 🧬

Vitruvian is an advanced, biologically-inspired wrapper for autonomous coding agents (currently extending `SWE-agent-mini`). It addresses the core limitations of modern AI coding agents—infinite loops, context hallucination, and destructive code mutations—by implementing defensive subsystems modeled after human biology.

## The Problem
Autonomous agents frequently suffer from:
1. **Infinite Loops (Agent Thrashing)**: Repeatedly running the same failing command without real mutation.
2. **Context Hallucination**: Using React conventions in a Vue project, or `pip install` in a Node project.
3. **Silent Mutations**: Breaking tests down the line because the agent couldn't verify the scope of its changes.

## The Biological Solution

Vitruvian wraps the agent's query cycle with 3 independent biological modules:

### 1. 🧠 Módulo Cerebelar (Anti-Loop)
**Inibição Lateral & Período Refratário**
Prevents exactly the same command from being executed if the previous error signature matches perfectly. 
- Escalates penalties on subsequent loops (Backoff with Mutation).
- Acts as a final **Circuit Breaker**, pausing the agent and deferring to a human if it gets stuck.

### 2. 🧬 Módulo Exonuclease (Proofreading)
**Tech Stack Validator & Mismatch Repair**
Intervenes at the system level before the prompt even reaches the LLM, and verifies changes retroactively:
- **Gatekeeper**: Normalizes and blocks dependencies not present in `package.json` or `pyproject.toml`.
- **Idempotency Scanner**: Engages test suite rules instantly when a file is modified interactively (`touch`, `curl`, `python -c`).

### 3. 🗺️ Módulo CA3 Hipocampal (Embodiment)
**Pattern Completion**
Gives the agent a "feel" for the repository without expensive context-window burns.
- Context is dynamically injected as a regular User Prompt (RAG style) exclusively when relevant terms are detected via BM25 sparse retrieval.

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/vitruvian.git
cd vitruvian

# 2. Setup the SWE-agent-mini submodule
cd mini-swe-agent
python3 -m venv venv
source venv/bin/activate
pip install -e .
cd ..

# 3. Install Vitruvian
pip install -e ".[dev]"
```

## Quick Start (E2E Telemetry)

We provide a specialized CLI to run Vitruvian wrapped around litellm models.

```bash
# Ensure the mini-swe-agent env is active
source mini-swe-agent/venv/bin/activate

# Run Vitruvian CLI on a target directory using the globally installed entrypoint
vitruvian --dir ./my_project --task "Implement error handling in the API"
```

### Telemetry & Debugging
The CLI intercepts the standard LLM event loop and produces distinctly formatted warnings whenever the biological layers intervene:

```text
🛡️ [VITRUVIAN INTERVENTION] INIBIÇÃO #1: Loop degenerativo detectado. Comando: python script.py...
🧠 [VITRUVIAN CONTEXT] Embodiment schema injetado (Git History)
```

### Configuration (Prompts & Escalations)
Vitruvian externalizes all its biological prompts and escalation strings to a dedicated YAML file.
You can find and modify these prompts safely at `src/vitruvian/config/prompts.yaml`.

```yaml
anti_loop:
  refractory_template: |
    ⚠️ Comportamento degenerativo detectado...
```

## Testing

Vitruvian includes 50+ deterministic tests enforcing idempotency, error signatures, schema builders, and prompt injection safety.

```bash
source mini-swe-agent/venv/bin/activate
pytest tests/ -v
```
