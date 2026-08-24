# Revisão científica do RNA-seq nativo

Data da revisão: 2026-08-09.

## 1. Estado atual

O fluxo nativo cobre QC, STAR, Salmon, Import e expressão diferencial. Download,
preparação inicial de metadata e relatório final ainda possuem compatibilidade
com o legado. O pipeline é modular e não contém nomes de cromossomos, genes,
estágios, sexos ou identificadores exclusivos de *Schistosoma mansoni*.

Esta revisão fortaleceu as fronteiras de entrada e tornou decisões científicas
explícitas. Ela não constitui validação de produção com dados reais.

## 2. Componentes revisados

| Componente | Revisão |
|---|---|
| QC | Ordenação de runs, metadata, paired-end, parâmetros de trimming e outputs FastQC/MultiQC |
| STAR | Referência/annotation, índice, argumentos, GeneCounts, strandedness, multimapping, MAPQ e recursos |
| Salmon | Transcriptoma, índice, k-mer, library type, `validateMappings`, outputs e ausência de decoys |
| Import | Identidade e ordem de samples, `tx2gene`, versões de IDs, colisões e valores inválidos |
| DESeq2 | Design, contrasts, replicação, counts fracionários, filtro, Wald e batch |
| Provenance | Checksums, versões, parâmetros, manifests, commit e relatórios Nextflow |

## 3. Problemas encontrados

| Severidade | Problema | Classificação |
|---|---|---|
| Crítica | Design declarado na documentação não era consumido e contrasts podiam ser criados automaticamente | científica/arquitetural |
| Crítica | Valores de fatores ausentes eram convertidos para `unknown` e categorias eram reescritas | científica |
| Crítica | Counts negativos eram truncados e valores STAR inválidos viravam zero | científica |
| Crítica | Counts Salmon com `countsFromAbundance=no` eram passados ao DESeq2 sem o offset de comprimento do tximport | científica |
| Alta | IDs eram desversionados e prefixos removidos silenciosamente, com possível colisão | científica |
| Alta | `tx2gene` aceitava somente uma estrutura de GTF e descartava relações incompletas | generalização |
| Alta | Metadata duplicada podia ser ignorada durante a criação da sample table | integridade |
| Alta | Batch correction legado era executado antes do caminho DE nativo | metodológica |
| Média | Filtro `rowSums > 10` e arredondamento eram implícitos | científica |
| Média | Salmon fixava `A` e `validateMappings` no adapter | configuração |
| Média | `STAR_EXTRA_ARGS` podia substituir argumentos pertencentes à API | reprodutibilidade |
| Limitação | QC nativo atual é paired-end | funcional |
| Limitação | Índice Salmon atual usa transcriptoma sem decoys/gentrome | metodológica a validar |

## 4. Problemas corrigidos

- Metadata agora falha cedo para campos obrigatórios vazios, `run_accession`
  duplicado, amostra duplicada e `file_prefix` inconsistente.
- Sample IDs e valores categóricos são preservados literalmente; somente IDs de
  arquivos internos são sanitizados.
- Import STAR preserva gene IDs por padrão, valida inteiros não negativos e
  detecta colisões após qualquer normalização solicitada.
- `TX2GENE_BUILD` aceita registros `transcript`/`mRNA`, atributos GTF
  `transcript_id`/`gene_id` e GFF `ID`/`Parent`. Mapeamentos ausentes ou
  transcript-to-multiple-gene falham explicitamente.
- TXIMPORT valida cobertura de `tx2gene`, duplicatas e colisões após as regras
  de versão/barra escolhidas.
- DE exige `design`, fórmula ordenada, pelo menos um contrast, política de
  filtro e política para counts fracionários. Negativos falham.
- DE Salmon aceita counts corrigidos sem offset (`scaledTPM` ou
  `lengthScaledTPM`) para bibliotecas full-length, ou counts originais sem
  correção para protocolo 3′ declarado. Counts originais full-length sem offset
  são rejeitados.
- Nenhum caminho top-level aplica correção de matriz antes do DE. O fallback
  legado recebe diretamente a saída de quantificação; os scripts de correção
  permanecem disponíveis apenas para comparação exploratória manual.
- Salmon expõe `salmon_lib_type` e `salmon_validate_mappings`; k-mer é validado
  como inteiro ímpar entre 1 e 31 e transcript IDs duplicados falham no índice.
- Argumentos STAR controlados pela Alignment API não podem ser sobrescritos por
  `STAR_EXTRA_ARGS`.

## 5. Melhorias metodológicas introduzidas

A principal mudança é a substituição de inferência silenciosa por contratos
explícitos. O usuário escolhe design, contrasts, filtro, arredondamento e
normalização de IDs. `filter.method=none` é válido; `total_count` exige operador
e threshold. Nenhum threshold universal novo foi introduzido.

Counts estimados do tximport podem ser fracionários. DESeq2 requer counts
inteiros na construção usada atualmente, portanto o contrato exige escolher
`non_integer_counts=round` ou `error`; a escolha fica registrada no model spec.

Para bibliotecas full-length, a implementação matricial usa a estratégia
tximport de counts derivados de abundância sem offset. A estratégia alternativa
— counts originais mais offset por comprimento via
`DESeqDataSetFromTximport` — fica para a próxima versão. Para 3′ tagged RNA-seq,
o usuário declara `three_prime` e usa `countsFromAbundance=no`, pois correção
por comprimento introduziria viés nesse protocolo.

Batch deve entrar como covariável, por exemplo `~ batch + condition`, quando o
desenho e a ausência de confundimento permitirem. Matriz corrigida por ComBat
não é usada automaticamente para inferência diferencial.

## 6. Diferenças em relação ao legado

As diferenças intencionais são: preservação de IDs como padrão; falha em vez de
coerção de dados inválidos; contrasts obrigatórios; filtro obrigatório e
declarado; e ausência de batch correction automática em qualquer caminho
inferencial top-level. Para
reproduzir uma regra antiga de IDs ou filtro, ela deve ser solicitada
explicitamente e aparecer na provenance.

O baseline histórico está arquivado na tag `rnaseq-legacy-v1.0.0` e pode ser
materializado pelos testes de regressão. `rnaseq_native_de=false` não é mais um
provider executável. Matrizes exploratórias de batch não são entradas
reconhecidas pela Differential Expression API.

## 7. Decisões científicas

- STAR continua produzindo BAM ordenado e `GeneCounts`. Os defaults de
  multimapping e MAPQ não foram alterados sem comparação controlada.
- A coluna STAR usada na Import API continua explicitamente selecionada por
  `STAR_GENECOUNT_COLUMN`; ela deve corresponder à orientação da biblioteca.
- Salmon mantém library type `A` e `validateMappings=true` como valores iniciais
  configuráveis, pois mudar a estratégia sem dataset de validação seria uma
  alteração científica arbitrária.
- Decoys/gentrome e selective alignment não foram ativados automaticamente. A
  comparação futura deve usar a mesma referência, annotation, metadata e
  contrasts, avaliando mapeamento, abundância e DE.
- Wald é o único teste implementado. LRT deve ser uma extensão explícita com
  fórmula completa e reduzida, não uma aproximação do Wald.
- O design nativo atual aceita fatores categóricos aditivos. Covariáveis
  contínuas, interações e designs nested ainda não são suportados.

## 8. Limitações atuais

- Não houve execução real de FastQC, STAR, Salmon, tximport ou DESeq2 nesta
  revisão; somente parsing de R, validações Python, lint e stub-run.
- GFF3 foi suportado arquiteturalmente, mas ainda requer teste funcional com
  arquivos de provedores diferentes.
- Não existe validação completa de concordância entre seqnames do FASTA e do
  GTF/GFF antes do STAR.
- O QC nativo não possui fluxo single-end completo.
- A sample metadata inicial ainda é descoberta pelo adapter legado; por isso a
  metadata deve virar um input Nextflow rastreado em uma versão futura.
- Provenance é distribuída entre manifests, `execution.json`, trace/report e
  Git; ainda não existe um manifesto final único com a versão do Nextflow.
- Os recursos HPC continuam conservadores e não foram benchmarkados.

## 9. Melhorias futuras

1. Criar `REFERENCE_VALIDATE` para FASTA, GTF/GFF, transcriptoma, seqnames e
   cobertura transcript-to-gene.
2. Tornar metadata um input nativo rastreado por conteúdo e adicionar schema.
3. Testar baseline Salmon versus gentrome/decoys em dataset reduzido e real.
4. Adicionar single-end ao QC e validar strandedness contra FastQC/Salmon.
5. Implementar LRT, shrinkage de log2FC e provedores edgeR/limma-voom atrás da
   mesma API.
6. Manter uma regressão científica reduzida: dimensões, correlações de counts,
   direção dos efeitos e concordância de genes significativos.
7. Implementar `DESeqDataSetFromTximport` para oferecer counts originais mais
   offset em bibliotecas full-length.

## 10. O que não foi alterado e por quê

Não foram alterados algoritmos de trimming, parâmetros default de alinhamento
STAR, método de quantificação Salmon, normalização interna do DESeq2, cálculo de
padj, ferramentas, versões de contêiner ou layouts de resultados. Essas mudanças
exigem dados reais, hipótese científica e comparação controlada. Também não
foram adicionados decoys, ComBat, LRT, filtros universais ou benchmark de
produção.

## Evidência de validação desta revisão

- `nextflow lint .`: 62 arquivos sem erro; um warning preexistente no wrapper
  legado por uso de `projectDir` dentro do processo.
- Stub-run completo do workflow RNA-seq: concluído com Nextflow 26.04.2.
- Testes Python: metadata, sample table, colisão STAR e DE preflight passaram.
- Parsing dos três scripts R modificados: passou.
- Testes com ferramentas científicas reais, regressão legado × nativo e
  benchmark: permanecem programados para o ciclo de validação biológica.

## Recomendação objetiva

**RNA-seq pronto para avançar para ChIP-seq? Sim, para iniciar a arquitetura e
migração do ChIP-seq reutilizando os contratos. Não, ainda, para declarar o
RNA-seq validado para produção/publicação.** Antes dessa declaração é necessário
um teste funcional real reduzido de ponta a ponta e a regressão científica
mínima descrita acima.

## Referências metodológicas primárias

- [Salmon: indexação, library type e selective alignment](https://salmon.readthedocs.io/en/stable/salmon.html)
- [STAR manual](https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf)
- [tximport: importação e downstream DGE](https://bioconductor.org/packages/release/bioc/vignettes/tximport/inst/doc/tximport.html)
- [DESeq2 vignette](https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html)
