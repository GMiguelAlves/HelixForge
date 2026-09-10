# Slurm execution monitor

Run `python ui/slurm/server.py` with Python 3.10+ and open the printed localhost URL.
On Windows, run inside WSL when the SSH alias or shared socket belongs to WSL.
The remote host needs Python 3 and the existing SSH authentication setup. The UI
only reads files and the current user's queue; it does not submit or cancel jobs.

Register an existing execution using its configurable absolute output directory.
The history and SSH configuration remain in browser local storage. Results are
read on demand and are not saved in browser storage. Refreshes keep the existing
30-second cache and one-query-at-a-time policy.

## Results

The existing summary, process filters, 25-task pages and task logs are preserved.
The **Resultados** section adds a searchable inventory, 20-file pages, text
windows, a final-log-window action, static HTML previews and SVG figures. The
summary attributes status strings to their individual terminal manifests; it
does not treat artifact presence or completed tasks as scientific acceptance.
Missing or malformed manifests do not hide other results.

Supported roots are a normal output directory, a launch directory with `results/`,
or an extracted audit directory with `execution/`, `manifests/`, `evaluation/`
and `failed_attempts/`. Trace precedence is:

1. `pipeline_info/execution_trace.tsv`
2. `results/pipeline_info/execution_trace.tsv`
3. `execution/trace.tsv`
4. `trace.tsv`

Previous-attempt traces stay separate from the main trace. Discovery includes
published RNA-seq, ChIP-seq and integration trees, reports, DAGs, timelines,
manifests and text artifacts. It does not follow manifest paths outside the
registered root or scan task work/cache directories. For the Nextflow log,
register the launch/audit directory containing it. Empty pipeline logs are valid;
prefer Nextflow logs, trace records, manifests and terminal artifacts.

## Bounds and isolation

- Text is read by byte offset in windows of at most 64 KiB, including large TSVs
  and old logs. Windows can split lines or UTF-8 characters; replacement decoding
  is used. Browser find searches the displayed window, not the entire remote file.
  Refreshes and changing files can shift byte positions; this is not an immutable
  snapshot. Tables are displayed as text, without loading or parsing them in full.
- HTML/SVG previews are limited to 4 MiB. Larger files remain readable as text.
  HTML is reduced to static allowlisted markup on the backend, then displayed in
  an iframe with an empty sandbox and restrictive CSP. Scripts, forms, navigation,
  embedded documents and URL attributes are removed. CSS has no network access.
  SVG is displayed only as an image, never as an active document.
- JavaScript-driven Nextflow charts/timelines/DAGs, inline SVG in HTML and linked
  resources are unavailable in static previews. Standalone SVGs can be inspected
  separately. Copy-path actions support opening originals through the user's
  existing file access; the UI does not offer executable HTML downloads.
- Inventory stops at 1,000 artifacts, 5,000 visited entries or depth 8 and marks
  partial results. Trace limits remain 2 MiB / 2,000 records; oversize traces give
  an explicit error. Manifest status summaries inspect up to 20 small manifests
  (64 KiB each). No status is inferred from previous-attempt manifests.
- Result paths reject absolute paths, traversal and ambiguous separators. File
  opens use directory descriptors, `O_NOFOLLOW`, regular-file and ownership
  checks. Symlink results are deliberately excluded. Existing task-log access
  remains restricted to the selected trace task and three command-log names.
- The localhost API retains its Host, Origin and session-token checks. Preview
  isolation requires inline styles and data images in the parent CSP; scripts
  remain restricted to local static application files.

## Validation

Run `python -m unittest discover -s tests/slurm_ui -v` on Linux and Windows and
`node --check` for each `ui/slurm/static/*.js` file. There is no asset build or
separate lint tool; the Python server serves the source files directly. Linux
tests exercise special files, ownership and descriptor-based reads; Windows
runs the HTTP and command-generation contracts.

Synthetic fixtures cover traversal, symlink directories, FIFOs, partial manifests,
an HTML injection payload, inventory limits and bounded reads of a sparse 300 MiB
table. Manual browser QA covers registration, result filters, HTML isolation and
SVG rendering. A private audit copy was also inspected locally: 12 completed
trace tasks, 33 artifacts and successful bounded log/report reads. That evidence
remains ignored and is neither required by tests nor included in this repository.
