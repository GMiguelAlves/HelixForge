# Installation

## Supported environment

The v1 release candidate certifies a deliberately narrow runtime baseline.

| Component | Status | Notes |
|---|---|---|
| Linux x86_64 | Supported | Primary execution platform |
| WSL2 | Supported for development | Used for local checks; native Windows is unsupported |
| Java 21 | Supported | Full validated baseline |
| Nextflow 25.10.7 | Supported | Exact certified version for v1 RC |
| Newer Nextflow/Java | Experimental | May work, but is not the release baseline |
| Docker profile | Supported | Recommended local container runtime |
| Slurm profile | Supported with site configuration | Validated with a maximum of five concurrent submissions |
| Apptainer/Singularity | Experimental | Declared, but the validation cluster lacked a supported runtime with registry and mount access |
| Conda profile | Experimental | Module environments exist; no complete clean RC smoke is certified |

Git is required. Python and R do not need to be installed on the host when the
selected provider runs in its pinned container.

## Install Nextflow

```bash
git clone https://github.com/GMiguelAlves/HelixForge.git
cd HelixForge
curl -fsSL https://get.nextflow.io | NXF_VER=25.10.7 bash
chmod +x nextflow
```

Java 21 must already be available through `java`. Validate the environment:

```bash
NEXTFLOW="$PWD/nextflow" bin/helixforge-doctor
```

Use `--require-container` when a real containerized analysis is expected:

```bash
NEXTFLOW="$PWD/nextflow" bin/helixforge-doctor --require-container
```

## Profiles

- `local`: local executor; tools must be available or supplied by module
  containers when a container engine is enabled separately.
- `test`: deterministic small fixtures and conservative local resources.
- `docker`: enables Docker and module-declared, pinned images.
- `slurm`: delegates every scientific process to Slurm. Site queues, storage,
  registry access and account policy remain administrator-specific.
- `apptainer`/`singularity`: preparatory profiles, currently experimental.
- `conda`: preparatory profile, currently experimental.

Do not run scientific processing on a Slurm head node. Keep the project and
Nextflow cache on persistent storage and heavy data/work directories on storage
approved by the site. HelixForge processes never call `sbatch` themselves.

## Updating

Use a release tag when one exists. Until the RC tag is authorized, clone the
reviewed branch or commit explicitly. Do not assume that `master` is immutable.

## Troubleshooting

1. Run `bin/helixforge-doctor` and record its output.
2. Confirm Java 21 and Nextflow 25.10.7.
3. Confirm the chosen container runtime can read the input mounts and pull the
   pinned registry images.
4. Inspect `.nextflow.log`, `trace.txt`, and the failing task work directory.
5. On Slurm, inspect the allocation with `sacct`/`scontrol`; do not reproduce a
   compute task interactively on the head node.
