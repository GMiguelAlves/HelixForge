# Auditoria do benchmark RNA-seq GSE52778

Este ZIP preserva a evidência necessária para revisar a execução biológica
completa do HelixForge no conjunto público GSE52778.

O pacote contém:

- resultados publicados pelo HelixForge;
- métricas, figuras e validações finais;
- logs do Nextflow e das recuperações controladas;
- identidades de execução, manifests, versões e checksums;
- resultados e proveniência da análise independente;
- evidência das tentativas que falharam e das correções aplicadas;
- tabelas e imagens finais de expressão diferencial e gene report.

Os FASTQs públicos, a referência genômica completa, ambientes de software e o
diretório `work` do Nextflow não estão incluídos. Eles são grandes, podem ser
reconstruídos a partir dos manifests/checksums e não são necessários para
confirmar os resultados finais. O arquivo `ARQUIVOS_SHA256.tsv` lista tamanho e
SHA-256 de cada item guardado no ZIP.

Conclusão registrada: `PASS_WITH_LIMITATIONS`. A execução independente do
Salmon usou oito threads, enquanto o HelixForge usou quatro. A tolerância
numérica estrita falhou, mas identidades, correlações, rankings, conjuntos de
genes diferencialmente expressos e expectativas biológicas permaneceram
altamente concordantes. A falha estrita foi preservada no pacote.

O resultado final também registra uma recuperação controlada do relatório de
genes após a correção do tratamento de IDs Ensembl versionados. As matrizes
científicas e o resultado do DESeq2 não foram recalculados nessa recuperação.

