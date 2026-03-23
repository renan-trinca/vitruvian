# Vitruvian — Roadmap Imediato

## ✅ Fase 0: Setup (concluído)
- [x] Clonar mini-swe-agent
- [x] Instalar dependências em venv
- [x] Criar `VitruvianAgent` herdando `DefaultAgent`
- [x] Validar com teste mock

## 🔜 Próximo: Arquitetura de Plugins
- [x] Definir interface `Module` (protocolo/ABC para Anti-Loop, Proofreading, Embodiment)
- [x] Configurar **ruff** para linting/formatting
- [x] Configurar **pytest** com estrutura de testes
- [x] Criar primeiro vertical slice: Anti-Loop detectando 3 ações idênticas em mock

## ✅ Sprint 1-2: Anti-Loop (Módulo Cerebelar) — concluído
- [x] Action Fingerprinting com error_signature
- [x] Regra de Inibição (detecção de repetição com mesmo erro)
- [x] Período Refratário (prompt override forçando nova estratégia)
- [x] Exponential Backoff com Mutação (escalação progressiva)
- [x] Circuit Breaker (CircuitBreakerError → saída limpa)
- [x] 11 testes passando, ruff limpo

## ✅ Sprint 3-6: Proofreading (Motor Exonuclease) — concluído
- [x] Camada 1: Tech Stack Validator (pre_query context + post_query redirect)
- [x] Camada 3: Mismatch Repair (test runner + anti-pattern registry)
- [x] 19 testes novos passando

## ✅ Sprint 7-9: Embodiment (Contexto CA3) — concluído
- [x] Project scanner (configs, git history)
- [x] Schema builder (BM25 lightweight)
- [x] Pattern completion no prompt via pre_query hook
- [x] Testes de coverage full

## ✅ Sprint 10: Beta & End-to-End Integration — concluído
- [x] Criar CLI/Runner principal (`python -m vitruvian.run`)
- [x] Configurar telemetria rica (logs coloridos para as inibições biológicas)
- [x] Teste E2E contra um App real ou repositório "sujo" (provocando repetições)
- [x] Finalizar README.md & Instalação
