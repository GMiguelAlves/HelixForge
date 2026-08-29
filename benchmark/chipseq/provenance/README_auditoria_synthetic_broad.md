# Auditoria do benchmark ChIP-seq synthetic broad

Este arquivo descreve as evidências compactas da execução controlada do
benchmark de domínios amplos do HelixForge no cluster Slurm.

O pacote preserva:

- desenho congelado, emenda anterior à execução, truth, parâmetros e checksums;
- proveniência das construções e testes do simulador ChIPs, inclusive tentativas
  que revelaram incompatibilidade de arquitetura do binário;
- logs, trace, relatório, timeline e DAG da execução HelixForge;
- domínios por replicata, consenso por suporte de replicatas e métricas de FRiP;
- resultados da implementação independente iniciada nos mesmos FASTQs;
- métricas contra o ground truth, cobertura, figuras e desempenho descritivo;
- tentativas de diagnóstico e logs Slurm necessários para explicar a execução.

O pacote não contém FASTQs, BAMs, índices, BigWigs, ambientes Conda, cache nem
diretórios `work/`. Esses itens são grandes e reproduzíveis a partir dos seeds,
parâmetros e checksums registrados. A ausência deles é intencional.

Resultado resumido: o HelixForge e a implementação independente produziram
resultados idênticos para ambas as replicatas e para o consenso. Todos os
release gates passaram. A classificação é `PASS_WITH_LIMITATIONS`, porque a
fragmentação do consenso (62,8%) ficou acima da faixa esperada congelada de
30%, sem qualquer ajuste posterior dos critérios.

Consulte `evaluation/`, `figures/` e `performance/` para os resultados e
`checksums.sha256` para verificar a integridade do pacote.
