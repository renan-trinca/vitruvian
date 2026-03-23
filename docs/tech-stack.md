# Vitruvian — Tech Stack

## Runtime

| Componente | Tecnologia | Versão |
|---|---|---|
| Linguagem | Python | 3.14 (venv local) |
| Base do agente | mini-swe-agent | 2.2.7 |
| LLM interface | litellm | 1.82.6 |
| Config/Models | pydantic | 2.x |
| Templates | jinja2 | 3.x |

## Ferramentas de qualidade

| Ferramenta | Propósito |
|---|---|
| **ruff** | Linting + formatting (substitui flake8, isort, black) |
| **pytest** | Testes unitários e de integração |

## Estrutura de diretórios

```
vitruvian/
├── product.md              # Visão do produto
├── tech-stack.md           # Este arquivo
├── plan.md                 # Roadmap imediato
├── vitruvian-execution-plan.md  # Plano de execução detalhado
├── vitruvian-agent-research.md  # Pesquisa original
├── mini-swe-agent/         # Fork base (git clone)
│   └── src/minisweagent/   # Código do mini-swe-agent
├── src/vitruvian/          # Nosso código
│   ├── agents/
│   │   └── vitruvian_agent.py  # Agente principal (herda DefaultAgent)
│   └── modules/            # Módulos bio-inspirados plugáveis
└── tests/
    └── test_vitruvian_setup.py  # Teste de sanidade
```

## Regras de dependência

- **Não adicionar libs sem registrar aqui primeiro**
- Preferir stdlib do Python sempre que possível
- Módulos bio-inspirados devem ser heurísticas determinísticas (sem LLM adicional) quando viável
