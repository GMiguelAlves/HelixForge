#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?benchmark repository root is required}
scratch_root=${2:?benchmark scratch root is required}
audit_root=${3:?audit destination in home is required}
archive_name=${4:-helixforge-rnaseq-stage9b1-audit-20260826.zip}

test -n "${SLURM_JOB_ID:-}"
expected_scratch=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825
expected_audit=/home/ra236875@bio.ib.unicamp.br/helixforge-rnaseq-benchmark-audits/20260825-9b1
[[ "$(realpath "$scratch_root")" == "$expected_scratch" ]]
mkdir -p "$audit_root"
[[ "$(realpath "$audit_root")" == "$expected_audit" ]]
test -d "$repo_root/benchmark/rnaseq"

archive="$audit_root/$archive_name"
checksum="$archive.sha256"
test ! -e "$archive"
test ! -e "$checksum"

stage=$(mktemp -d "$scratch_root/audit-stage.XXXXXX")
[[ "$stage" == "$expected_scratch"/audit-stage.* ]]
trap '[[ -n "${stage:-}" && "$stage" == /scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/audit-stage.* ]] && rm -rf -- "$stage"' EXIT
bundle="$stage/helixforge-rnaseq-stage9b1-audit"
mkdir -p "$bundle"/{benchmark,dataset,executions,independent,metrics,validation,provenance,slurm}

cp -a "$repo_root/benchmark/rnaseq/." "$bundle/benchmark/"
cp -a "$scratch_root/dataset/polyester-ground-truth-v1/simulation_manifest.json" "$bundle/dataset/"
cp -a "$scratch_root/dataset/polyester-ground-truth-v1/dataset_validation.json" "$bundle/dataset/"
cp -a "$scratch_root/dataset/polyester-ground-truth-v1/generation_execution.json" "$bundle/dataset/"
cp -a "$scratch_root/dataset/polyester-ground-truth-v1/truth" "$bundle/dataset/"
cp -a "$scratch_root/dataset/polyester-ground-truth-v1/conversion_manifests" "$bundle/dataset/"
cp -a "$scratch_root/dataset/reference" "$bundle/dataset/"

for case_name in synthetic-primary-run3 synthetic-clean-repeat-v2; do
    source_case="$scratch_root/cases/$case_name"
    target_case="$bundle/executions/$case_name"
    mkdir -p "$target_case"
    cp -a "$source_case/execution_identity.json" "$target_case/"
    cp -a "$source_case/pipeline_config.sh" "$target_case/"
    cp -a "$source_case/analysis_spec.json" "$target_case/"
    cp -a "$source_case/logs" "$target_case/"
    cp -a "$source_case/results" "$target_case/"
done

cp -a "$scratch_root/metrics/." "$bundle/metrics/"
cp -a "$scratch_root/validation/." "$bundle/validation/"
cp -a "$scratch_root/provenance/." "$bundle/provenance/"

find "$scratch_root/independent" -type f \
    \( -name '*.json' -o -name '*.yml' -o -name '*.yaml' -o -name '*.txt' \
       -o -name '*.tsv' -o -name '*.log' -o -name '*.out' -o -name '*.err' \) \
    -size -10M -print0 | while IFS= read -r -d '' source_file; do
        relative=${source_file#"$scratch_root/independent/"}
        mkdir -p "$bundle/independent/$(dirname "$relative")"
        cp -a "$source_file" "$bundle/independent/$relative"
    done

sacct -j 15165,15202,15419,15420,15421,15422,15423,15424,15425,15426,15427,15431,15432,15433,15434,15435,15436,15437,15438,15497,15575,15576,15577,15578,15579,15580,15581,15584,15585 \
    --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,MaxRSS,NodeList \
    > "$bundle/slurm/job_accounting.txt"

printf '%s\n' \
    '# Auditoria do benchmark RNA-seq sintético — HelixForge' \
    '' \
    'Este arquivo reúne as evidências compactas da Etapa 9B.1 executada no Slurm.' \
    'Inclui o protocolo e scripts do benchmark, identidade das duas execuções' \
    'completas, resultados publicados, traces e relatórios do Nextflow, tabelas' \
    'de verdade sintética, métricas, comparações independentes, logs e proveniência.' \
    '' \
    'Os FASTQs brutos e os diretórios `work/` não estão neste ZIP por serem grandes.' \
    'Seus checksums e metadados permanecem no `simulation_manifest.json`; o dataset' \
    'congelado foi mantido temporariamente no scratch para as próximas revisões.' \
    '' \
    'Sujeito validado: HelixForge v1.0.0-rc.1' \
    'Commit: fc38ada8f592bb57a13467965a718ce0df7fb6ce' \
    "Job de empacotamento Slurm: $SLURM_JOB_ID" \
    > "$bundle/README_PT.md"

python3 - "$bundle" <<'PY'
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
lines = []
for path in sorted(p for p in root.rglob('*') if p.is_file()):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    lines.append(f"{digest.hexdigest()}  {path.relative_to(root).as_posix()}")
(root / 'MANIFEST_SHA256.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
PY

python3 - "$bundle" "$archive" <<'PY'
import pathlib
import sys
import zipfile

source = pathlib.Path(sys.argv[1])
archive = pathlib.Path(sys.argv[2])
with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
    for path in sorted(p for p in source.rglob('*') if p.is_file()):
        output.write(path, pathlib.Path(source.name, path.relative_to(source)))
with zipfile.ZipFile(archive) as check:
    failure = check.testzip()
    if failure:
        raise SystemExit(f"corrupt archive member: {failure}")
PY

sha256sum "$archive" > "$checksum"
cat "$checksum"
