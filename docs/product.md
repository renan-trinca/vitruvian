# Vitruvian — Product Definition

## O que é

Agente de código autônomo, fork do `mini-swe-agent` (Princeton/Stanford), com 3 módulos bio-inspirados que resolvem problemas reais que nenhum agente atual resolve bem:

1. **Anti-Loop** — Detecta e interrompe ciclos de retry degenerativos
2. **Proofreading** — Verificação estática pré-geração + testes pré-commit
3. **Embodiment** — Aprende conventions do projeto real via git history e configs

## Estratégia

- **Plataforma proprietária de devtools** (não open-source, não acadêmico)
- Fork base: `mini-swe-agent` v2.2.7 (MIT license)
- Dogfooding first → produto depois

## Público-alvo

Desenvolvedores que usam agentes de código e estão frustrados com:
- Código "quase certo" que demora mais para verificar do que para escrever
- Loops que queimam budget sem resultado
- Agentes que ignoram o tech stack real do projeto

## O que NÃO é

- Não é um IDE
- Não é um wrapper de API
- Não compete em benchmarks acadêmicos como métrica primária
