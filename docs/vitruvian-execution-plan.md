# Vitruvian — Plano de Execução (12 Semanas)

> Fork bio-inspirado do SWE-agent com 3 módulos de alto impacto.
> Baseado na pesquisa consolidada em `vitruvian-agent-research.md`.

---

## Tese

Agentes de código atuais compartilham 3 falhas estruturais que nenhum player resolveu satisfatoriamente:

1. **Loops degenerativos** — retry infinito da mesma abordagem falha (OpenHands Issues #8630, #5997)
2. **Código "quase certo"** — 53% dos devs citam como problema #1; METR RCT 2025 mostrou que IA *desacelerou* devs experientes em 19%
3. **Cegueira contextual** — agentes geram código funcional mas alien ao projeto (framework errado, naming errado, patterns genéricos)

A biologia oferece soluções concretas para cada um. Não como metáfora — como design patterns implementáveis.

---

## Decisão: O que construir (e o que NÃO construir)

### Construir

| # | Módulo | Inspiração Biológica | Impacto | Risco |
|---|--------|---------------------|---------|-------|
| 1 | **Anti-Loop** (Cerebelar) | Inibição lateral + período refratário | Altíssimo — elimina burn de budget | Baixo — heurística determinística |
| 2 | **Proofreading** (Exonuclease) | DNA Pol III verificação 3'→5' | Alto — ataca o problema #1 dos devs | Médio — latência vs cobertura |
| 3 | **Embodiment** (CA3 Hipocampal) | Pattern completion + schema theory | Alto — elimina retrabalho por cegueira | Baixo — técnicas conhecidas |

### NÃO construir (e por quê)

| Módulo | Razão |
|--------|-------|
| Memória Hipocampal | Complexo demais para o time. Claude Code já endereça com `CLAUDE.md`. Esperar o mercado. |
| Filtro de Escopo | Feature útil, não produto. Contribuir como PR upstream. |
| Sistema Imunológico | Campo especializado. Usar Snyk/Semgrep. Não reinventar. |
| Roteador Metabólico | Commodity. LiteLLM + Ollama já resolvem. Não construir o que se configura. |

---

## Base técnica

**Fork: SWE-agent mini** (Princeton/Stanford)

- ~100 linhas de Python puro
- MIT license — zero amarras
- Hackable by design — declarado pelos autores
- ~65% SWE-bench Verified (com Claude Sonnet)
- Menor superfície de código = menor risco de breaking changes

**Se o protótipo validar:** migração futura para OpenHands CodeAct 2.1 (sandbox Docker, function calling extensível).

---

## Módulo 1: Anti-Loop (Sprints 1–2)

**Problema:** Agentes entram em ciclos de retry idêntico. OpenHands Issue #5997 documenta 89+ prompts iterativos sem convergência.

**Mecanismo biológico:** O cerebelo calcula erro motor continuamente. Se um padrão repetitivo não reduz o gradiente de erro, interneurônios inibitórios desligam à força a rota sináptica, forçando nova estratégia. O período refratário neuronal (~1-2ms) impede loops de feedback positivo.

**Implementação:**

```
1. Action Fingerprinting
   - Hash de cada ação (tool call + args + diff gerado)
   - Similaridade de cosseno entre diff(N) e diff(N-1)
   - Correlação com exit codes do compilador/test runner

2. Regra de Inibição
   - Se 3 edições sequenciais têm >90% de semelhança léxica
     E todas falham no mesmo teste
   → Dispara "Sinal de Inibição Lateral"

3. Período Refratário
   - Limpa fila de intenção do agente
   - Bloqueia acesso temporário ao arquivo-alvo
   - Injeta system prompt override:
     "Comportamento degenerativo detectado.
      O caminho via [função X] provou-se fútil e foi bloqueado.
      Proponha abordagem fundamentalmente distinta."

4. Circuit Breaker
   - Se file editing falha 5x total na sessão → pausa e escala para humano
```

**Complexidade:** Baixa — heurística determinística em thread paralela. Não depende de LLM.

**Métrica de sucesso:** Retry cycles por tarefa: de ~8-12 → ≤2 (redução ≥80%).

**Estimativa:** 2 semanas, 1 dev.

---

## Módulo 2: Proofreading Estático (Sprints 3–6)

**Problema:** 53% dos devs relatam código "quase certo" como problema #1 (SonarSource 2026). METR RCT mostrou que o tempo gasto em limpeza e depuração superou os ganhos da IA.

**Mecanismo biológico:** DNA Polimerase III atinge taxa de erro de 1 em 10⁹ usando camadas empilhadas: seleção inicial → proofreading exonucleolítico 3'→5' → mismatch repair pós-replicação. Cada camada é independente e tem custo/latência diferente.

**Implementação (2 camadas — Camada 2 do research foi cortada):**

```
Camada 1 — Seleção (custo: zero, latência: <100ms)
├── Antes de gerar, verifica alinhamento com tech stack
├── Lê package.json / requirements.txt / go.mod
├── Se o modelo tenta usar lib não presente → rejeita e redireciona
└── Consulta .eslintrc / tsconfig para constraints de tipo

Camada 3 — Mismatch Repair (custo: médio, latência: 10-30s)
├── Pré-commit gate
├── Executa testes existentes do projeto
├── Gera testes de edge case específicos para as mudanças
└── Mantém registro de anti-patterns conhecidos do projeto
    └── Código que dá match → rejeitado antes de ser apresentado
```

> [!IMPORTANT]
> A Camada 2 do research original (modelo secundário verificando cada bloco via AST reversa) foi **cortada**. O risco de latência (+1-3s por bloco × 50 blocos = 1-2 min extras por sessão) não justifica o ganho marginal nesta fase. Pode ser reintroduzida se a Camada 1 + 3 provarem insuficientes.

**Métrica de sucesso:** First-pass correctness: de ~40% → ≥55% (aumento de 30%+).

**Estimativa:** 4 semanas, 1-2 devs.

---

## Módulo 3: Embodiment Contextual (Sprints 7–9)

**Problema:** Agentes geram código funcional mas culturalmente alien ao projeto. Usa Redux quando o projeto usa Zustand. camelCase quando o projeto usa snake_case. Bootstrap quando o projeto usa Tailwind.

**Mecanismo biológico:** A região CA3 do hipocampo faz pattern completion — recebe uma dica fragmentária e dispara retroativamente todas as redes associadas, reconstruindo o contexto mental completo sem computação adicional. Schema theory: o cérebro assimila novas informações em frameworks mentais existentes.

**Implementação:**

```
1. Project Scan (na inicialização)
   ├── package.json / requirements.txt / go.mod → stack
   ├── .eslintrc / .prettierrc / tsconfig → style rules
   ├── Estrutura de diretórios → architecture patterns
   └── Git log (últimos 50 commits) → conventions reais

2. Schema Building
   ├── Vetoriza componentes-chave em grafo interconectado
   ├── Identifica: framework UI, state management, test framework,
   │   API patterns, naming convention, file structure convention
   └── Armazena como "schema do projeto" em vector store local

3. Pattern Completion (em cada request)
   ├── Quando dev faz pedido curto ("cria modal de login")
   ├── Motor faz busca vetorial no schema local
   ├── Infla contexto invisível com:
   │   ├── Framework correto (Tailwind, não Bootstrap)
   │   ├── Components adjacentes reais do projeto
   │   ├── Naming convention real (camelCase vs snake_case)
   │   └── Patterns de imports e exports do projeto
   └── Injeta no system prompt antes da geração

4. Convention Learning
   └── Aprende de git history real, não de defaults genéricos
```

**Métrica de sucesso:** Código com framework/convention errado: de ~30% → ≤10% (redução de 70%).

**Estimativa:** 3 semanas, 1 dev.

---

## Cronograma

```
Semana  1-2   ██████████░░░░░░░░░░░░░░  Sprint 1-2: Anti-Loop
Semana  3-6   ░░░░██████████████░░░░░░  Sprint 3-6: Proofreading
Semana  7-9   ░░░░░░░░░░░░██████████░░  Sprint 7-9: Embodiment
Semana 10-12  ░░░░░░░░░░░░░░░░██████░░  Sprint 10-12: Beta + Métricas
```

| Fase | Semanas | Entregável |
|------|---------|------------|
| **Setup** | 0 (pré-sprint) | Fork SWE-agent mini, CI/CD, ambiente de testes |
| **Sprint 1–2** | 1–2 | Módulo Anti-Loop funcional + testes |
| **Sprint 3–6** | 3–6 | Proofreading Camada 1 + Camada 3 + testes |
| **Sprint 7–9** | 7–9 | Embodiment com convention learning + testes |
| **Sprint 10–12** | 10–12 | Beta privado (20 devs) + medição de métricas |
| **Status Atual** | ✅ | **Versão 1.0 Candidate atingida (Audit Round 5 completo em Sprint 10)** |

**Time:** 2 devs (ideal: 1 sênior Python + 1 mid com experiência em tooling/AST).

---

## Métricas de sucesso

| Métrica | Baseline | Target | Como medir |
|---------|----------|--------|------------|
| Retry cycles / tarefa | ~8-12 | ≤2 | Counter no módulo Anti-Loop |
| First-pass correctness | ~40% | ≥55% | % de blocos que passam nos testes na primeira tentativa |
| Código com convention errada | ~30% | ≤10% | Review manual dos beta testers |
| NPS beta testers | N/A | ≥50 | Survey pós-beta |
| Latência adicionada por proofreading | 0s | <2s/bloco | Timer no pipeline |

> [!WARNING]
> SWE-bench Verified **não** é métrica primária. O benchmark não captura memória entre sessões, loops em projetos reais, ou integração com tech stack. Melhoria esperada: 53% → ~55% (margem de erro). As métricas acima são as que importam.

---

## Kill Criteria (Semana 12)

O projeto é **cancelado** se, ao final da semana 12:

1. Beta testers **não** reportarem melhoria perceptível em first-pass correctness
2. Retry cycles **não** caírem pelo menos 50%
3. Latência do proofreading exceder 5 segundos por bloco
4. Custo de manutenção do fork for insustentável (merge conflicts constantes)

**Plano de contingência:** Contribuir os módulos Anti-Loop e Proofreading como PRs upstream para OpenHands, ao invés de manter fork próprio. O trabalho não se perde — muda de veículo.

---

## Horizonte de expansão (pós-validação)

Se o beta validar, os 4 módulos descartados podem ser reintroduzidos por ordem de valor:

1. **Memória Hipocampal** — Só se Claude/Cursor não resolverem até lá
2. **Filtro de Escopo** — Como complemento natural do Proofreading
3. **Imunológico** — Se houver demanda enterprise
4. **Roteador Metabólico** — Só se modelo local atingir qualidade suficiente

Migração de base: **SWE-agent mini → OpenHands CodeAct 2.1** ocorre nesta fase, não antes.

---

## Estratégia de Produto definida

> [!IMPORTANT]
> **Decisão tomada:** O Vitruvian será construído como um **agente próprio / plataforma de devtools proprietária**.
>
> **Direcionamento:**
> - **Foco:** Resolver dores reais do fluxo de desenvolvimento interno (dogfooding) e evoluir para um produto/plataforma.
> - **Licença:** Cuidado redobrado com dependências. O fork de base (SWE-agent mini) é **MIT**, o que permite essa abordagem comercial/proprietária sem amarras.
> - **Design:** Módulos devem ser construídos com arquitetura plugável, facilitando a portabilidade para outros "corpos" (como OpenHands) no futuro, mas com o "cérebro" (módulos bio-inspirados) sendo o diferencial competitivo do Vitruvian.


---

*Última atualização: 22 de março de 2026*
*Documento de pesquisa completo: [vitruvian-agent-research.md](file:///Users/renantrinca/Projects/vitruvian/vitruvian-agent-research.md)*
