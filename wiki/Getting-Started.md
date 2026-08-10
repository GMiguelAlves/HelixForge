# Primeiros passos

## Pré-requisitos

- Nextflow `>=24.10.0`, conforme `nextflow.config`;
- Bash, usado como shell dos processos;
- Java compatível com a versão escolhida do Nextflow;
- ferramentas científicas no `PATH`, ou um perfil de ambiente compatível com
  os módulos que serão executados;
- arquivos de configuração dos workflows selecionados.

Clone o repositório e entre no diretório:

```bash
git clone https://github.com/GMiguelAlves/HelixForge.git
cd HelixForge
nextflow -version
```

## Configuração

Os caminhos padrão são:

```text
pipelines/rnaseq/legacy/config/pipeline_config.sh
pipelines/chipseq/legacy/config/pipeline_config.sh
pipelines/integrative/legacy/config/pipeline_config.sh
```

Esses arquivos continuam sendo fontes autoritativas para parâmetros ainda não
migrados. Outro arquivo pode ser selecionado explicitamente:

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_config /caminho/pipeline_config.sh \
  --rnaseq_run_mode qc
```

Os parâmetros nativos estão definidos em
[`nextflow.config`](https://github.com/GMiguelAlves/HelixForge/blob/master/nextflow.config)
e inventariados em
[`nextflow_schema.json`](https://github.com/GMiguelAlves/HelixForge/blob/master/nextflow_schema.json).

## Primeira execução leve

O perfil `test` reduz recursos e fornece parâmetros de fixture. `-stub-run`
compila o grafo e cria saídas simuladas sem executar ferramentas científicas:

```bash
nextflow run . -profile test -stub-run --workflow all
```

Para inspecionar somente uma camada nativa de ChIP-seq:

```bash
nextflow run . -profile test -stub-run --workflow chipseq \
  --chipseq_run_mode post_alignment
```

Para uma execução RNA-seq configurada pelo estudo:

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_config /caminho/pipeline_config.sh \
  --rnaseq_library_protocol full_length \
  --rnaseq_counts_from_abundance lengthScaledTPM \
  --rnaseq_de_spec /caminho/rnaseq_de_spec.json
```

Copie e adapte
[`assets/rnaseq_de_spec.example.json`](https://github.com/GMiguelAlves/HelixForge/blob/master/assets/rnaseq_de_spec.example.json)
quando a execução chegar a DE.

## Saídas iniciais

Por padrão, resultados ficam em `results/`. Artefatos operacionais do Nextflow
ficam em `results/pipeline_info/`:

- `execution_timeline.html`;
- `execution_trace.tsv`;
- `execution_report.html`;
- `pipeline_dag.html`.

Use `-resume` para reutilizar tarefas cujo código, parâmetros e entradas
continuam compatíveis com a chave de cache:

```bash
nextflow run . -profile local --workflow rnaseq -resume
```

Consulte [Execução](Execution.md) antes de usar containers, Conda ou Slurm.
