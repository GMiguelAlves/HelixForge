# Modos de workflow

O workflow de topo é selecionado por `--workflow rnaseq|chipseq|integrative|all`.
RNA-seq e ChIP-seq possuem parâmetros próprios de estágio.

## RNA-seq

`--rnaseq_run_mode` aceita os modos e aliases abaixo.

| Modo | Execução efetiva | Saída de estágio | Fallback/limite |
|---|---|---|---|
| `qc` | referência/adapters necessários + QC nativo | FASTQs tratados/mesclados, FastQC e MultiQC | `rnaseq_native_qc=false` usa o QC legado completo. |
| `alignment` | QC + STAR index/alinhamento | BAM/BAI, GeneCounts, logs e manifest | provider STAR é obrigatório; desligá-lo nesse modo falha. |
| `quant` / `quantification` | QC + Salmon index/quantificação | `quant.sf`, JSONs, `aux_info`, logs e manifest | provider Salmon é obrigatório; desligá-lo nesse modo falha. |
| `import` | provider configurado + Import API | counts, abundance, metadata e manifest | `rnaseq_native_import=false` não possui fallback suportado. |
| `de` / `differential_expression` | Import + preflight + DESeq2 model/contrasts/aggregate | tabelas, modelo, gráficos e manifest | `rnaseq_native_de=false` seleciona o DEG legado. |
| `full` | caminho RNA completo até DE | estado final do ramo configurado | ainda contém adapters/wrappers nas fronteiras documentadas. |

`--rnaseq_analysis_mode config|alignment|quantification|both` controla quais
providers analíticos podem receber os FASTQs mesclados. Modos de estágio
`alignment` e `quantification` forçam somente seu provider. Em `both`, STAR e
Salmon são independentes; a Import API consome o método selecionado pela
configuração autoritativa.

## ChIP-seq

| Modo | Execução/entrada | Artefatos principais | Fallback/estado |
|---|---|---|---|
| `qc` | metadata + FastQC/MultiQC | relatórios de reads brutos | foundation desligada cai na compatibilidade legada. |
| `alignment` | QC + Bowtie2 index/alinhamento | BAM/BAI alinhado e métricas | foundation desligada usa o grafo legado. |
| `post_alignment` | alinhamento + seleção/duplicatas/blacklist/QC | final BAM/BAI + manifests | exige BAM processing nativo; pode continuar para picos legados por flag explícita. |
| `peaks` | final BAM + controle + MACS3 | peak set por réplica, métricas e manifest | `chipseq_native_peak_calling=false` chama o passo legado de picos. |
| `peak_qc` | picos + FRiP + estatísticas | QC por réplica e agregado | com `chipseq_native_peak_qc=false`, termina depois de Peak Calling. |
| `consensus` | Peak QC + provider escolhido | intervalos union/intersection/replicate-support | quando o conjunto nativo de flags não está habilitado, usa consensus legado. |
| `idr` | exatamente duas réplicas narrowPeak premerged + parâmetros explícitos | manifest/status sem peak set | provider estatístico `not_implemented`; não há fallback equivalente. |
| `differential_binding` | consensus + final BAMs + spec | counts, modelo, contrasts e agregado | flag nativa false seleciona `differential` legado. |
| `annotation` | peak/consensus manifest + FASTA/reference manifest + GTF/GFF | annotated peaks, associações e estatísticas | flag false seleciona `annotate` legado. Não reroda picos. |
| `tracks` | inventário de final BAMs + referência | BigWigs individuais/agregados e inventário | flag false seleciona tracks legado. Não reroda BAM processing. |
| `report` | inventário explícito de manifests/componentes | HTML, JSON, manifest e provenance | flag false seleciona relatório legado. Não reroda produtores. |
| `full` | configuração ChIP-seq existente | grafo completo legado | deliberadamente legado até validação final. |

`annotation`, `tracks` e `report` são consumidores standalone de artefatos já
existentes. Seus parâmetros de inventário são obrigatórios no caminho nativo.

## Integrative e all

- `integrative`: executa o subworkflow de integração legado usando
  `--integrative_config`.
- `all`: inicia RNA-seq e ChIP-seq, coleta seus status e então inicia
  Integrative. Não entrega seus artefatos por uma API semântica conjunta.

Referências: [workflows](https://github.com/GMiguelAlves/HelixForge/tree/master/workflows),
[`nextflow_schema.json`](https://github.com/GMiguelAlves/HelixForge/blob/master/nextflow_schema.json) e
[execução Nextflow](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/nextflow.md).
