#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830"
readonly REPO="/home/ra236875@bio.ib.unicamp.br/helixforge-benchmark-chipseq-real-narrow"
readonly AUDIT_DIR="/home/ra236875@bio.ib.unicamp.br/helixforge-audit/real-narrow"
readonly ARCHIVE="$AUDIT_DIR/HelixForge_real_narrow_K562_CTCF_20260830.tar.gz"

[[ "$(realpath -- "$ROOT")" == "$ROOT" ]]
[[ -d "$ROOT" ]]
[[ -d "$REPO/.git" ]]
mkdir -p -- "$AUDIT_DIR"
stage="$(mktemp -d "$ROOT/.audit-stage.XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT

mkdir -p "$stage/evidence" "$stage/repository"
cat > "$stage/README_PT.md" <<'EOF'
# Auditoria do benchmark Real Narrow do HelixForge

Este arquivo reúne as evidências compactas do benchmark biológico K562 CTCF
executado no Slurm em 30 de agosto de 2026. A classificação final foi
PASS_WITH_LIMITATIONS. O caminho HelixForge concluiu 37/37 tarefas e a
implementação independente produziu peaks semanticamente idênticos e resultado
IDR byte a byte idêntico.

O critério RN3 não foi calculado. O preflight final demonstrou capacidade
insuficiente para o controle congelado por cromossomo, largura exata e número
exato de bases GC. Nenhum quarto modelo de nulo foi tentado. O p nominal de uma
tentativa anterior está preservado apenas como evidência invalidada.

O pacote contém métricas, logs, relatórios Nextflow, peaks compactos, resultados
IDR, tentativas invalidadas do gerador nulo, preflight final, proveniência e o
recorte correspondente do repositório. FASTQs, BAMs, bedGraphs, referências
genômicas, índices, ambientes Conda e workdirs foram excluídos por tamanho e
podem ser reconstruídos a partir dos acessos, checksums e código preservados.
EOF

cp -a "$ROOT/evaluation" "$stage/evidence/"
cp -a "$ROOT/null_v3_capacity" "$stage/evidence/"
cp -a "$ROOT/null_validation" "$stage/evidence/"
cp -a "$ROOT/preflight" "$stage/evidence/"
cp -a "$ROOT/slurm_logs" "$stage/evidence/"
cp -a "$ROOT/downloads/provenance" "$stage/evidence/download_provenance"

mkdir -p "$stage/evidence/helixforge" "$stage/evidence/independent/peaks"
for item in benchmark_commit.txt protocol_commit.txt scientific_target.txt trace.tsv report.html timeline.html dag.html input logs; do
    cp -a "$ROOT/helixforge/$item" "$stage/evidence/helixforge/"
done
cp -a "$ROOT/helixforge/results/chipseq/peak_qc" "$stage/evidence/helixforge/"
cp -a "$ROOT/helixforge/results/chipseq/consensus" "$stage/evidence/helixforge/"
cp -a "$ROOT/independent/commands" "$stage/evidence/independent/"
cp -a "$ROOT/independent/provenance" "$stage/evidence/independent/"
cp -a "$ROOT/independent/idr" "$stage/evidence/independent/"

while IFS= read -r -d '' source; do
    relative="${source#"$ROOT/independent/"}"
    mkdir -p "$stage/evidence/independent/$(dirname "$relative")"
    cp -a "$source" "$stage/evidence/independent/$relative"
done < <(find "$ROOT/independent/peaks" -type f ! -name '*.bdg' -print0)

git -C "$REPO" archive --format=tar HEAD \
    benchmark/chipseq/configs/real_narrow_execution.json \
    benchmark/chipseq/protocol \
    benchmark/chipseq/reports/real_narrow_benchmark.md \
    benchmark/chipseq/results/real_narrow \
    benchmark/chipseq/scripts \
    tests/benchmark_chipseq/test_real_narrow_benchmark.py \
    | tar -xf - -C "$stage/repository"
git -C "$REPO" rev-parse HEAD > "$stage/repository_commit.txt"
git -C "$REPO" status --porcelain > "$stage/repository_status.txt"

find "$stage" -type f ! -name checksums.sha256 -print0 \
    | sort -z \
    | xargs -0 sha256sum \
    | sed "s#  $stage/#  #" > "$stage/checksums.sha256"

rm -f -- "$ARCHIVE" "$ARCHIVE.sha256"
tar -czf "$ARCHIVE" -C "$stage" .
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
tar -tzf "$ARCHIVE" >/dev/null
printf 'ARCHIVE=%s\n' "$ARCHIVE"
du -h "$ARCHIVE"
cat "$ARCHIVE.sha256"
