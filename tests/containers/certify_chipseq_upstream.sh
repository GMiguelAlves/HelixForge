#!/usr/bin/env bash

set -euo pipefail

role=${1:?container role is required}
image=${2:?container image is required}
case_root=${3:-$(mktemp -d "${TMPDIR:-/tmp}/helixforge-${role}.XXXXXX")}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

mkdir -p "$case_root"

case "$role" in
    macs3)
        cat > "$case_root/treatment.bed" <<'EOF'
chr1	100	130	read1	60	+
chr1	105	135	read2	60	+
chr1	110	140	read3	60	+
chr1	500	530	read4	60	+
chr1	505	535	read5	60	+
chr1	510	540	read6	60	+
EOF
        docker run --rm -v "$case_root:/case" "$image" bash -euo pipefail -c '
            mkdir -p /case/output
            macs3 callpeak -t /case/treatment.bed -f BED -g 1000 -n reduced \
                --outdir /case/output --nomodel --extsize 50 --keep-dup all -q 0.5 \
                > /case/macs3.stdout.log 2> /case/macs3.stderr.log
            test -s /case/output/reduced_peaks.narrowPeak
            macs3 --version > /case/versions.txt
        '
        ;;
    annotation)
        docker run --rm -v "$repo_root:/repo:ro" -w /repo "$image" \
            python3 -m unittest tests.native_chipseq_peak_annotation.test_peak_annotation \
            > "$case_root/unittest.log" 2>&1
        docker run --rm "$image" python3 --version > "$case_root/versions.txt" 2>&1
        ;;
    report)
        docker run --rm -v "$repo_root:/repo:ro" -w /repo "$image" \
            python3 -m unittest tests.native_chipseq_report.test_report \
            > "$case_root/unittest.log" 2>&1
        docker run --rm "$image" python3 --version > "$case_root/versions.txt" 2>&1
        ;;
    *)
        echo "unknown role: $role" >&2
        exit 2
        ;;
esac

docker image inspect --format='{{index .RepoDigests 0}}' "$image" > "$case_root/image-digest.txt"
printf 'role\tresult\n%s\tPASS\n' "$role" > "$case_root/certification.tsv"
printf '[OK] %s upstream certification: %s\n' "$role" "$case_root"
