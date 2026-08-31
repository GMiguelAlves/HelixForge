#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830"
readonly AUDIT_DIR="/home/ra236875@bio.ib.unicamp.br/helixforge-audit/real-broad"
readonly ARCHIVE="$AUDIT_DIR/HelixForge_real_broad_K562_H3K27me3_20260831.tar.gz"
readonly SNAPSHOT="$AUDIT_DIR/repository_snapshot"

[[ -n "${SLURM_JOB_ID:-}" ]] || { echo "Audit packaging must run under Slurm." >&2; exit 2; }
[[ "$(realpath -- "$ROOT")" == "$ROOT" ]]
[[ -d "$ROOT/evaluation" ]]
[[ -s "$SNAPSHOT/repository_snapshot.tar" ]]
mkdir -p -- "$AUDIT_DIR"
stage="$(mktemp -d "$ROOT/.audit-stage.XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT

mkdir -p "$stage/evidence" "$stage/repository"
cat > "$stage/README_PT.md" <<'EOF'
# Auditoria do benchmark Real Broad do HelixForge

Este pacote reúne as evidências compactas do benchmark biológico K562
H3K27me3 executado no Slurm em 31 de agosto de 2026. A classificação final foi
PASS_WITH_LIMITATIONS. O HelixForge concluiu 37/37 tarefas e a implementação
independente produziu peaks e consenso com coordenadas exatamente iguais.

RB1, RB2 e RB3 passaram. A correlação real entre réplicas superou a rotação
congelada, e o consenso sobrepôs os peaks replicados ENCODE mais do que todas
as 100 rotações. As limitações dizem respeito à profundidade e ao comprimento
das bibliotecas históricas, à assimetria entre réplicas e à ausência de um
leitor BigWig no runtime congelado para uma métrica descritiva de RB5.

O pacote contém métricas, rotações, relatório, figuras, logs, relatórios
Nextflow, peaks compactos, consenso, proveniência, comandos independentes e o
recorte correspondente do repositório. FASTQs, BAMs, bedGraphs, referência
genômica, índices, ambientes Conda e workdirs foram excluídos por tamanho e
podem ser reconstruídos a partir dos acessos, checksums e código preservados.
EOF

cp -a "$ROOT/evaluation" "$stage/evidence/"
cp -a "$ROOT/preflight" "$stage/evidence/"
cp -a "$ROOT/metadata" "$stage/evidence/"
cp -a "$ROOT/logs" "$stage/evidence/slurm_logs"
cp -a "$ROOT/downloads/provenance" "$stage/evidence/download_provenance"
cp -a "$ROOT/reference/reference_manifest.json" "$stage/evidence/"

mkdir -p "$stage/evidence/helixforge" "$stage/evidence/independent"
for item in benchmark_commit.txt protocol_commit.txt scientific_target.txt trace.tsv report.html timeline.html dag.html input logs; do
    [[ -e "$ROOT/helixforge/$item" ]] && cp -a "$ROOT/helixforge/$item" "$stage/evidence/helixforge/"
done
cp -a "$ROOT/helixforge/results/chipseq/peak_qc" "$stage/evidence/helixforge/"
cp -a "$ROOT/helixforge/results/chipseq/consensus" "$stage/evidence/helixforge/"
mkdir -p "$stage/evidence/helixforge/080-peak-calling"
while IFS= read -r -d '' source; do
    relative="${source#"$ROOT/helixforge/results/080-peak-calling/"}"
    mkdir -p "$stage/evidence/helixforge/080-peak-calling/$(dirname "$relative")"
    cp -a "$source" "$stage/evidence/helixforge/080-peak-calling/$relative"
done < <(find "$ROOT/helixforge/results/080-peak-calling" -type f ! -name '*.bdg' -print0)

for item in commands provenance consensus qc; do
    cp -a "$ROOT/independent/$item" "$stage/evidence/independent/"
done
mkdir -p "$stage/evidence/independent/peaks"
while IFS= read -r -d '' source; do
    relative="${source#"$ROOT/independent/peaks/"}"
    mkdir -p "$stage/evidence/independent/peaks/$(dirname "$relative")"
    cp -a "$source" "$stage/evidence/independent/peaks/$relative"
done < <(find "$ROOT/independent/peaks" -type f ! -name '*.bdg' -print0)

(
    cd "$SNAPSHOT"
    sha256sum -c repository_snapshot.tar.sha256
)
tar -xf "$SNAPSHOT/repository_snapshot.tar" -C "$stage/repository"
cp -a "$SNAPSHOT/repository_commit.txt" "$SNAPSHOT/repository_status.txt" \
    "$SNAPSHOT/repository_snapshot.tar.sha256" "$stage/"

find "$stage" -type f ! -name checksums.sha256 -print0 \
    | sort -z | xargs -0 sha256sum \
    | sed "s#  $stage/#  #" > "$stage/checksums.sha256"

rm -f -- "$ARCHIVE" "$ARCHIVE.sha256"
tar -czf "$ARCHIVE" -C "$stage" .
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
tar -tzf "$ARCHIVE" >/dev/null
printf 'ARCHIVE=%s\n' "$ARCHIVE"
du -h "$ARCHIVE"
cat "$ARCHIVE.sha256"
