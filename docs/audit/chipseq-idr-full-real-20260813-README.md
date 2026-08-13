# Evidência da validação ChIP-seq com IDR

Este pacote contém evidências leves da execução completa e reduzida do caminho
ChIP-seq nativo do HelixForge no Slurm institucional em 13 de agosto de 2026.

O caso `chipseq-production-idr-real-07` executou QC, Bowtie2, processamento BAM,
MACS3, FRiP/Peak QC, IDR 2.0.4.2, Differential Binding, anotação, tracks e o
relatório final. O arquivo `validation.json` registrou `status=pass` para 12
grupos de verificações. O trace contém 105 processos, sem falhas, com no máximo
cinco jobs simultâneos.

O pacote preserva o JSON de validação, trace, DAG/timeline/report operacionais,
logs de execução e validação, manifests e estatísticas do IDR e os artefatos do
relatório final. Ele não contém FASTQs, BAMs, workdirs nem ambientes Conda.

O dataset é sintético e reduzido. Esta evidência valida execução, contratos,
proveniência e integração; não substitui a regressão com dataset biológico
revisado planejada após a aposentadoria do pipeline legado.
