#!/usr/bin/env bash

set -u

printf 'hostname\t%s\n' "$(hostname)"
printf 'date\t%s\n' "$(date --iso-8601=seconds)"

for runtime in docker apptainer singularity podman enroot ch-run shifter; do
    if command -v "$runtime" >/dev/null 2>&1; then
        printf 'runtime\t%s\t%s\n' "$runtime" "$(command -v "$runtime")"
    else
        printf 'runtime\t%s\tunavailable\n' "$runtime"
    fi
done

if command -v module >/dev/null 2>&1; then
    printf 'modules\tavailable\n'
else
    printf 'modules\tunavailable\n'
fi

if [[ -r /dev/fuse ]]; then
    printf 'fuse\tavailable\n'
else
    printf 'fuse\tunavailable\n'
fi

if command -v unshare >/dev/null 2>&1 && unshare --user --map-root-user true; then
    printf 'unprivileged_user_namespace\tavailable\n'
else
    printf 'unprivileged_user_namespace\tunavailable\n'
fi

for dependency in curl rpm2cpio cpio; do
    if command -v "$dependency" >/dev/null 2>&1; then
        printf 'installer_dependency\t%s\tavailable\n' "$dependency"
    else
        printf 'installer_dependency\t%s\tunavailable\n' "$dependency"
    fi
done
