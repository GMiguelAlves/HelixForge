# Layout do repositório e testes

## Componentes

```text
HelixForge/
├── main.nf                 # seleção do workflow de topo
├── nextflow.config         # parâmetros, perfis e relatórios
├── nextflow_schema.json    # schema da interface de linha de comando
├── workflows/              # rnaseq, chipseq, integrative e all
├── subworkflows/local/     # composição das APIs e providers
├── modules/local/          # processos DSL2 e recursos dos módulos
├── conf/                   # configuração comum de processos
├── profiles/               # local, Slurm e runtimes
├── assets/                 # exemplos de specs e inventários
├── pipelines/*/legacy/     # implementações históricas preservadas
├── tests/                  # fixtures e checks por componente
├── docs/                   # especificações técnicas detalhadas
└── wiki/                   # camada navegável desta Wiki
```

`docs/` é a fonte técnica detalhada. A Wiki organiza essa informação para
leitura e aponta para o código, contratos, exemplos e testes correspondentes.

## Estratégia de testes existente

Os componentes possuem combinações diferentes de:

- checks estruturais/arquiteturais;
- `-stub-run` para compilar o grafo sem executar ferramentas científicas;
- testes de validação de entradas e falhas esperadas;
- fixtures mínimas por API/provider;
- regressão e comparação semântica quando o runtime está disponível;
- checks de cache para fronteiras como índice, modelo e contrast.

Os diretórios em `tests/native_*` documentam o escopo de cada conjunto. Nem
todo script de regressão foi executado no mesmo ambiente: alguns encerram com
razão explícita quando Nextflow, container, R/Bioconductor ou ferramentas HPC
não estão disponíveis. Isso não deve ser interpretado como validação científica
global.

## Ao alterar documentação ou código

Escolha o check mais barato que cubra a alteração. Para documentação, verifique
links, paths, parâmetros e Mermaid; não execute datasets reais. Para um módulo,
comece por contrato, syntax/stub e entradas inválidas antes de um teste
funcional mínimo. A validação científica consolidada pertence ao
[plano final](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/final-validation-plan.md).

Referências: [testes](https://github.com/GMiguelAlves/HelixForge/tree/master/tests),
[contrato de módulos](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/module_contracts.md) e
[limitações](https://github.com/GMiguelAlves/HelixForge/blob/master/docs/limitations.md).
