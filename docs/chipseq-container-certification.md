# Certificação dos containers ChIP-seq

## Resultado

Em 20 de agosto de 2026, os runtimes que ainda impediam o perfil de containers
do ChIP-seq foram construídos ou fixados por digest e exercitados com dados
reduzidos reais no GitHub Actions. A execução `32368534261` concluiu os sete
jobs sem falhas e preservou um artefato de auditoria por runtime.

As imagens próprias são construídas a partir de ambientes Micromamba limpos.
Elas não modificam o prefixo Conda de uma imagem Biocontainers preexistente.

| Runtime | Conteúdo certificado | Digest OCI |
|---|---|---|
| `helixforge-chipseq-alignment:1.0.0` | Bowtie2 2.5.4 e samtools 1.20 | `sha256:9c4e4169e498f72e9c9f123f2f5eb05a18bc2fabd5a3446beeac10df1514928e` |
| `helixforge-chipseq-intervals:1.0.0` | Python 3.12.4, samtools 1.20 e BEDTools 2.31.1 | `sha256:9b22ad6dec37c77b38d4faf4b7b0aa0b7e172428d71bf4e1017f10fb2cebe479` |
| `helixforge-chipseq-counts:1.0.0` | Python 3.12.4 e featureCounts 2.0.6 | `sha256:082005876efa7167b8b3f6fb477c78c8d60aed787f83eb3b2ca76b37c761fbf7` |
| `helixforge-chipseq-tracks:1.0.0` | Python 3.11.9, deepTools 3.5.5, samtools 1.20 e pyBigWig 0.3.23 | `sha256:eb8a447d7f467a2fb9e1c1d9561a73e22cf16c72e2308a7bbf683c242e2bb843` |
| MACS3 BioContainer | MACS3 3.0.4 | `sha256:15596c03f7a52c8aa27dc5feb181a6a5a12d2ad7cbcff4980021446c6a9451cb` |
| Python annotation | Python 3.12.10 slim | `sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db` |
| Python report | Python 3.11.9 slim Bookworm | `sha256:8fb099199b9f2d70342674bd9dbccd3ed03a258f26bbd1d556822c6dfc60c317` |

## Testes funcionais

- Bowtie2 construiu um índice, alinhou um FASTQ e produziu BAM indexado e
  validado por samtools.
- samtools e BEDTools converteram e intersectaram alinhamentos reais reduzidos.
- featureCounts contou uma feature SAF e retornou a contagem esperada.
- deepTools produziu um BigWig, posteriormente aberto e validado por pyBigWig.
- MACS3 executou `callpeak` e produziu um `narrowPeak` não vazio.
- annotation executou a cadeia leve de contexto, provider, estatísticas e
  agregação.
- report executou os testes de contrato, agregação semântica e HTML.

Os Dockerfiles também validam as versões durante o build. A CI publica SBOM e
proveniência, faz pull da imagem publicada antes do teste e registra o digest
observado.

Uma consulta anônima posterior ao GHCR retornou HTTP 200 para as quatro imagens
próprias e confirmou os mesmos digests. O uso em Docker/Apptainer não depende do
token de publicação do GitHub Actions.

## Docker e Apptainer

Docker está certificado para cada runtime acima. Os parâmetros Apptainer usam
as mesmas imagens por referências `docker://...@sha256:...`, sem uma segunda
distribuição divergente.

O cluster institucional não expõe Docker, Apptainer ou Singularity. Portanto,
a resolução e execução dessas referências por Apptainer ainda não foram
testadas naquele ambiente. Nenhum runtime foi instalado no head node e nenhum
processamento científico foi executado diretamente nele.

## Limite da evidência

Esta rodada certifica a composição e a funcionalidade de cada imagem. O DAG
ChIP-seq completo já passou no Slurm com runtimes Conda controlados, mas ainda
não foi repetido de ponta a ponta com o perfil Docker ou Apptainer. A regressão
biológica revisada permanece planejada para depois da aposentadoria do legado.

## Tentativa de validação no Slurm após Debian 13

Em 20 de agosto de 2026, dois probes mínimos foram submetidos ao Slurm após a
atualização do cluster para Debian 13. Nenhum comando científico foi executado
no head node.

| Job | Nó | Resultado |
|---|---|---|
| `14748` | `srv-slurm-node-04` | Docker, Apptainer, Singularity, Podman, Enroot, Charliecloud e Shifter indisponíveis; sistema de módulos ausente. |
| `14749` | `srv-slurm-node-04` | `/dev/fuse` acessível e `unshare --user --map-root-user` funcional; `curl` e `cpio` disponíveis, mas `rpm2cpio` ausente. |

O caminho `full` não foi iniciado porque não existe runtime capaz de executar
as imagens OCI nos nós. A instalação relocável não privilegiada do Apptainer é
tecnicamente plausível, mas exigiria introduzir e manter dependências próprias
fora da infraestrutura certificada pelos administradores. Essa instalação não
foi realizada em um cluster compartilhado.

Estado da etapa: **concluída com limitação operacional externa**, sem falha
científica do HelixForge. A ausência de um Apptainer administrado no head/nós,
com acesso aos registries GHCR/Quay e aos mounts `/home` e `/scratch`, não é um
release gate. Se essa infraestrutura for disponibilizada futuramente, repetir
o probe versionado em `tests/slurm/probe_container_runtimes.sh`, testar um pull
por digest e executar o fixture completo com `-profile slurm,apptainer` e
`executor.queueSize=5` como certificação operacional adicional.
