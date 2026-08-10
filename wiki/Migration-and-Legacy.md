# Migração e legado

O HelixForge migra de orquestradores Bash/R/Python para processos Nextflow DSL2
incrementalmente. A arquitetura nativa é o destino; o legado permanece como
baseline histórico, fallback onde suportado e material para regressão.

## Estado atual

| Área | Estado resumido |
|---|---|
| RNA-seq QC | nativo; download/metadata/planning ainda usam adapters |
| RNA-seq alignment | STAR nativo sob a Alignment API |
| RNA-seq quantification | Salmon nativo sob a Quantification API |
| RNA-seq import | providers Salmon/STAR nativos |
| RNA-seq DE | DESeq2 Wald nativo; batch/report preservam fronteiras legadas |
| ChIP-seq foundation | metadata, QC, Bowtie2 e BAM processing nativos por modos |
| ChIP-seq peaks/QC | MACS3, FRiP e estatísticas nativos |
| ChIP-seq consensus | union, intersection e replicate support nativos |
| ChIP-seq IDR | validação e provenance presentes; cálculo `not_implemented` |
| ChIP-seq downstream | differential binding, annotation, tracks e report nativos como modos explícitos |
| ChIP-seq `full` | grafo legado |
| Integrative | legado |
| Workflow `all` | coordena conclusão; não implementa uma API integrativa semântica |

## Fallback não é uniforme

Flags `native_* = false` selecionam fallback somente onde o workflow o
implementa. Exemplos:

- RNA QC false chama o QC legado;
- RNA DE false chama DEG legado;
- RNA Import false não possui fallback suportado;
- modos ChIP-seq podem chamar passos legados específicos ou o grafo legado,
  dependendo do estágio;
- IDR não possui fallback equivalente;
- `full` ChIP-seq é explicitamente legado.

Confira [Modos de workflow](Workflow-Modes.md) antes de desligar uma flag. Não
presuma simetria entre estágios.

## Código preservado

Os arquivos em `pipelines/rnaseq/legacy/`, `pipelines/chipseq/legacy/` e
`pipelines/integrative/legacy/` continuam executáveis e não devem ser
reescritos durante a migração. Adapters podem consumir sua configuração e
chamar seus scripts sem transferir a submissão de jobs para dentro dos módulos
nativos.

Remoção definitiva, equivalência científica e benchmark final só serão
decididos depois da execução do
[plano de validação final](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/final-validation-plan.md).

## Divergências documentais conhecidas

- documentos antigos usam “validation” para testes isolados ou regressões de
  módulo; isso não representa a validação científica consolidada;
- alguns textos RNA-seq anteriores ainda descrevem Import ou DE como wrappers,
  enquanto o código atual possui providers nativos;
- “DAG funcional ChIP-seq completo” descreve a disponibilidade dos modos
  nativos, não o comportamento do modo `full`;
- containers de alguns providers ChIP-seq continuam sem imagem fixada e sua
  validação de runtime foi adiada explicitamente.

Quando houver conflito, use esta ordem: workflow/código atual, contrato atual e
documentação arquitetural mais recente. Registre a divergência; não invente uma
reconciliação.

Referências: [auditoria de consolidação](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/architecture-consolidation-audit.md),
[limitações](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/limitations.md),
[análise legada ChIP-seq](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/chipseq-legacy-analysis.md) e
[mapeamento de scripts](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/script-mapping.md).

Voltar: [Home](Home.md) · [Arquitetura](Architecture-Overview.md)
