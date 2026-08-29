# Auditoria do benchmark ChIP-seq synthetic narrow

Este arquivo contém evidências compactas da primeira execução controlada do
benchmark *narrow-peak* do HelixForge no cluster Slurm.

O pacote preserva:

- desenho congelado, truth sintético, checksums e parâmetros;
- proveniência da construção e do teste do simulador ChIPs;
- logs, trace, relatório, timeline e DAG da execução HelixForge;
- picos por replicata, resultado IDR e métricas de FRiP;
- resultados equivalentes da implementação independente;
- métricas contra o ground truth, figuras e desempenho descritivo;
- logs dos jobs Slurm utilizados na execução e na avaliação.

O pacote não contém FASTQs, BAMs, índices, cache ou diretórios `work/`. Esses
arquivos são grandes e reproduzíveis a partir dos parâmetros, sementes e
checksums registrados. A ausência deles é intencional.

Resultado resumido: o caminho HelixForge e a referência independente geraram
o mesmo conjunto IDR por SHA-256. A classificação do braço é
`PASS_WITH_LIMITATIONS`, pois todos os release gates passaram, mas o recall da
classe STRONG no IDR ficou abaixo da faixa esperada congelada.

Consulte `evaluation/` para as tabelas e figuras e `checksums.sha256` para a
integridade dos arquivos deste pacote.
