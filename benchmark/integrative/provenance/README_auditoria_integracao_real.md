# Auditoria da integração biológica real GSE133183

Este arquivo acompanha a evidência compacta da execução real de integração do
HelixForge no cluster Slurm. O conjunto permite confirmar quais contratos foram
consumidos, quais processos foram executados, quais versões e checksums foram
registrados e como os critérios científicos congelados foram avaliados.

O arquivo inclui:

- manifesto terminal da integração e validação dos manifests de entrada;
- manifests e auditorias dos adaptadores de evidência diferencial e multi-mark;
- log do driver, trace, relatório de execução, timeline e DAG do Nextflow;
- avaliação `IB1`–`IB8`, candidatos, exemplos preregistrados e desempenho;
- checksums dos arquivos incluídos.

O arquivo não contém FASTQs, referências, workdirs, caches nem as tabelas
científicas grandes. Esses dados continuam no espaço controlado do benchmark
enquanto forem necessários. Alguns logs podem registrar caminhos específicos
do servidor; por isso, este ZIP permanece na home privada e não deve ser
publicado diretamente no repositório.

Classificação registrada: `PASS_WITH_LIMITATIONS`. Os gates técnicos passaram;
a ausência de regiões H3K27me3 significativas e a indisponibilidade de testes
de enriquecimento direcional permanecem documentadas como limitações.
