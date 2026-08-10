# Execução

Esta página cobre a operação disponível no repositório atual. Os scripts de
compatibilidade ainda leem seus `pipeline_config.sh`; a migração não exige que
esses arquivos sejam convertidos para parâmetros Nextflow.

## Pré-requisitos e instalação

- Linux ou ambiente Linux compatível com Bash;
- Java compatível com Nextflow;
- Nextflow 24.10.0 ou posterior;
- runtime requerido pelo perfil escolhido;
- acesso aos dados, referências e configurações legadas correspondentes.

Clone o repositório, entre na raiz e confirme o Nextflow:

```bash
git clone https://github.com/GMiguelAlves/HelixForge.git
cd HelixForge
nextflow -version
```

Os configs padrão ficam em
`pipelines/rnaseq/legacy/config/pipeline_config.sh`,
`pipelines/chipseq/legacy/config/pipeline_config.sh` e
`pipelines/integrative/legacy/config/pipeline_config.sh`. Use os arquivos e
convenções já previstos pelos pipelines; não versione segredos ou caminhos
privados.

## Perfis

| Perfil | Executor/runtime | Estado atual |
|---|---|---|
| `local` | executor local, até quatro tarefas | utilizável com ferramentas disponíveis no ambiente/processo |
| `slurm` | executor Slurm | exige config do site para partition, account, QoS e scratch |
| `docker` | executor local + Docker | preparação; imagens são definidas por processo e algumas ainda são `null` |
| `singularity` | executor local + Singularity | preparação; requer containers/config do site |
| `apptainer` | executor local + Apptainer | preparação; requer containers/config do site |
| `conda` | executor local + Conda | preparação; adapters legados ainda podem ativar ambientes próprios |
| `test` | executor local, recursos mínimos | destinado a fixtures e `-stub-run`, não a análise científica |

Perfis de preparação não garantem que todo o DAG possa ser executado naquele
runtime. Consulte os containers realmente fixados em `nextflow.config` antes
de escolher um modo.

## Primeira execução local

RNA-seq com configuração e especificação explícitas:

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_config /path/to/rnaseq/pipeline_config.sh \
  --rnaseq_library_protocol full_length \
  --rnaseq_counts_from_abundance lengthScaledTPM \
  --rnaseq_de_spec /path/to/rnaseq_de_spec.json
```

Para selecionar apenas um estágio, acrescente, por exemplo,
`--rnaseq_run_mode qc` ou `--rnaseq_run_mode alignment`.

Um stub barato do grafo completo usa:

```bash
nextflow run . -profile test -stub-run --workflow all
```

Um stub da fundação ChIP-seq usa:

```bash
nextflow run . -profile test -stub-run --workflow chipseq \
  --chipseq_run_mode post_alignment
```

Modos ChIP-seq posteriores possuem inputs obrigatórios próprios. Por exemplo,
Peak Calling requer tipo de pico e tamanho efetivo do genoma; annotation,
tracks e report requerem os manifests/inventários descritos nas páginas
técnicas e nos exemplos em `assets/`.

## Containers e Conda

Selecione `-profile docker`, `-profile singularity`, `-profile apptainer` ou
`-profile conda` apenas quando o runtime estiver instalado e os módulos do modo
escolhido possuírem ambiente configurado. Não há uma imagem global implícita.
Alguns providers ChIP-seq aguardam imagens combinadas validadas, portanto um
perfil de container pode falhar antes da validação científica final.

## Slurm

O profile Slurm faz o Nextflow submeter cada processo. Módulos não devem chamar
`sbatch` ou `srun` internamente. Informações locais do cluster ficam em arquivo
separado, fornecido com `-c`:

```bash
nextflow run . -profile slurm -c /path/to/site.config \
  --workflow rnaseq \
  --rnaseq_config /path/to/rnaseq/pipeline_config.sh
```

O `site.config` deve declarar, conforme a política do cluster, partition/queue,
account, QoS e scratch. Recursos científicos continuam associados aos labels e
processos do repositório.

## Retomada, outputs e logs

Use `-resume` com o mesmo `work/` para reaproveitar tarefas cujo cache continua
válido:

```bash
nextflow run . -profile local -resume --workflow rnaseq \
  --rnaseq_run_mode qc \
  --rnaseq_config /path/to/rnaseq/pipeline_config.sh
```

Por padrão, outputs são publicados em `results/` e o cache fica em `work/`.
`--outdir` altera o diretório de resultados. Cada execução também produz:

- `pipeline_info/execution_timeline.html`;
- `pipeline_info/execution_trace.tsv`;
- `pipeline_info/execution_report.html`;
- `pipeline_info/pipeline_dag.html`.

Logs e metadata específicos aparecem nos outputs de cada processo; o log do
driver Nextflow permanece em `.nextflow.log` na raiz de execução.

Referências: [guia Nextflow](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/nextflow.md),
[`nextflow.config`](https://github.com/GMiguelAlves/HelixForge/blob/master/nextflow.config),
[`nextflow_schema.json`](https://github.com/GMiguelAlves/HelixForge/blob/master/nextflow_schema.json) e
[perfis](https://github.com/GMiguelAlves/HelixForge/tree/master/profiles).

Próximo: [Layout e testes](Repository-Layout-and-Testing.md) ·
[Guia de desenvolvimento](Development-Guide.md)
