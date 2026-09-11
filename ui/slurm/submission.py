#!/usr/bin/env python3
"""Pure validation and document generation for the Slurm preparation wizard."""

import csv
import io
import json
from pathlib import Path
import re
import shlex


WORKFLOWS = {"rnaseq", "chipseq", "integrative", "all"}
RUNTIMES = {"slurm", "slurm,apptainer", "slurm,singularity"}

FIELD_LABELS = {
    "name": "Nome da análise",
    "clone.path": "Caminho do clone",
    "clone.repository": "Repositório oficial",
    "clone.ref": "Tag, branch ou commit",
    "storage.project_root": "Diretório do projeto leve",
    "storage.launch": "Diretório de lançamento",
    "storage.output": "Diretório de resultados",
    "storage.work": "Workdir",
    "runtime.partition": "Partição Slurm",
    "runtime.memory": "Memória do coordenador (GB)",
    "runtime.hours": "Tempo do coordenador (h)",
    "organism.name": "Organismo",
    "organism.reference_id": "Identificador da referência",
    "organism.genome_fasta": "Genoma FASTA",
    "organism.transcriptome_fasta": "Transcriptoma FASTA",
    "organism.annotation": "Anotação GTF ou GFF3",
    "science.effective_genome_size": "Effective genome size",
    "statistics.variable": "Variável principal",
    "statistics.formula": "Fórmula",
    "statistics.alpha": "Alpha",
    "statistics.lfc_threshold": "Limiar absoluto log2FC",
    "statistics.min_replicates": "Mínimo de replicatas",
    "integration.rna_manifest": "Manifest RNA-seq",
    "integration.chip_manifest": "Manifest ChIP-seq",
    "integration.policy_paths.harmonization": "Política de harmonização",
    "integration.policy_paths.interpretation": "Política de interpretação",
    "integration.policy_paths.mark_roles": "Papéis das marcas",
    "integration.policy_paths.prioritization_context": "Contexto de priorização",
    "integration.policy_paths.functional_annotation": "Anotação funcional",
}
SAMPLE_LABELS = {"sample_id":"Sample ID", "fastq_1":"FASTQ R1", "fastq_2":"FASTQ R2",
                 "condition":"Condição", "batch":"Batch", "replicate":"Replicata",
                 "dataset":"Dataset", "run_accession":"Run accession",
                 "mark_or_factor":"Mark / fator", "control_id":"Control ID", "layout":"Layout"}


class PlanError(ValueError):
    def __init__(self, message, field=""):
        super().__init__(message)
        self.field = field


def field_label(field):
    match = re.fullmatch(r"(rnaseq|chipseq)_samples\.(\d+)\.([a-z0-9_]+)", field)
    if match:
        assay, index, key = match.groups()
        return f"{SAMPLE_LABELS.get(key, key)} da amostra {int(index) + 1} de {'RNA-seq' if assay == 'rnaseq' else 'ChIP-seq'}"
    match = re.fullmatch(r"statistics\.contrasts\.(\d+)\.(numerator|denominator)", field)
    if match:
        side = "Numerador" if match.group(2) == "numerator" else "Denominador"
        return f"{side} do contraste {int(match.group(1)) + 1}"
    return FIELD_LABELS.get(field, field)


def required_message(field):
    return f'O campo “{field_label(field)}” é obrigatório.'


def _text(value, field, maximum=2048, required=True):
    if value is None and required:
        raise PlanError(required_message(field), field)
    if not isinstance(value, str):
        raise PlanError("O valor deve ser texto.", field)
    value = value.strip()
    if required and not value:
        raise PlanError(required_message(field), field)
    if len(value) > maximum or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise PlanError("Valor inválido ou muito longo.", field)
    return value


def _path(value, field, required=True):
    value = _text(value, field, required=required)
    if not value and not required:
        return ""
    if not value.startswith("/") or "%" in value or "\t" in value or any(part in (".", "..") for part in value.split("/")):
        raise PlanError("Use um caminho absoluto e normalizado, sem '.', '..' ou '%'.", field)
    return value.rstrip("/") or "/"


def _cell(value, field, required=True):
    value = _text(value, field, 512, required)
    if "\t" in value or "\n" in value or "\r" in value:
        raise PlanError("A célula não pode conter tabulação ou quebra de linha.", field)
    return value


def _number(value, field, minimum, maximum, integer=False):
    if value is None or isinstance(value, str) and not value.strip():
        raise PlanError(required_message(field), field)
    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        raise PlanError("Informe um número válido.", field) from exc
    if not minimum <= number <= maximum:
        raise PlanError(f"Use um valor entre {minimum} e {maximum}.", field)
    return number


def _tsv(columns, rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _groovy(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _groovy_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return _groovy(str(value))


def validate_plan(value):
    if not isinstance(value, dict):
        raise PlanError("Plano de análise inválido.")
    plan = {}
    plan["name"] = _text(value.get("name"), "name", 120)
    workflow = value.get("workflow")
    if workflow not in WORKFLOWS:
        raise PlanError("Escolha um workflow válido.", "workflow")
    plan["workflow"] = workflow
    plan["science"] = _validate_science(value.get("science", {}), workflow)
    clone = value.get("clone")
    plan["clone"] = validate_clone(clone)
    storage = value.get("storage")
    if not isinstance(storage, dict):
        raise PlanError("Informe os diretórios da análise.", "storage")
    plan["storage"] = {key: _path(storage.get(key), f"storage.{key}") for key in ("project_root", "launch", "output", "work")}
    contains = lambda parent, child: parent == "/" or child == parent or child.startswith(parent + "/")
    output, work = plan["storage"]["output"], plan["storage"]["work"]
    if contains(output, work) or contains(work, output) or any(contains(path, plan["clone"]["path"]) for path in (output, work)) or any(contains(path, plan["storage"]["launch"]) for path in (output, work)):
        raise PlanError("Saída e work devem ser distintos e não podem conter o clone ou launch.", "storage")
    runtime = value.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("profile") not in RUNTIMES:
        raise PlanError("Escolha um runtime Slurm válido.", "runtime.profile")
    identifier = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}"
    partition = _text(runtime.get("partition"), "runtime.partition", 80)
    account = _text(runtime.get("account", ""), "runtime.account", 80, False)
    if not re.fullmatch(identifier, partition) or account and not re.fullmatch(identifier, account):
        raise PlanError("Partição ou conta inválida.", "runtime.partition")
    plan["runtime"] = {"profile": runtime["profile"], "partition": partition, "account": account,
                       "memory": str(_number(runtime.get("memory"), "runtime.memory", 1, 1024, True)),
                       "hours": str(_number(runtime.get("hours"), "runtime.hours", 1, 720, True))}
    organism = value.get("organism")
    if not isinstance(organism, dict):
        raise PlanError("Informe organismo e referência.", "organism")
    needs_reference = workflow != "integrative"
    plan["organism"] = {"name": _cell(organism.get("name", ""), "organism.name", needs_reference),
                        "reference_id": _cell(organism.get("reference_id", ""), "organism.reference_id", needs_reference),
                        "genome_fasta": _path(organism.get("genome_fasta", ""), "organism.genome_fasta", workflow in ("chipseq", "all") or plan["science"]["quantification"] == "star"),
                        "transcriptome_fasta": _path(organism.get("transcriptome_fasta", ""), "organism.transcriptome_fasta", workflow in ("rnaseq", "all")),
                        "annotation": _path(organism.get("annotation", ""), "organism.annotation", needs_reference),
                        "blacklist": _path(organism.get("blacklist", ""), "organism.blacklist", False)}
    rna_raw = value.get("rnaseq_samples", value.get("samples") if workflow == "rnaseq" else [])
    chip_raw = value.get("chipseq_samples", value.get("samples") if workflow == "chipseq" else [])
    for assay, rows, required in (("rnaseq", rna_raw, workflow in ("rnaseq", "all")), ("chipseq", chip_raw, workflow in ("chipseq", "all"))):
        if not isinstance(rows, list) or len(rows) > 1000 or required and not rows:
            raise PlanError(f"Adicione ao menos uma amostra {assay}.", f"{assay}_samples")
    plan["samples"] = {"rnaseq": _validate_samples(rna_raw, "rnaseq"), "chipseq": _validate_samples(chip_raw, "chipseq")}
    if plan["science"]["idr"] and plan["samples"]["chipseq"]:
        groups = {}
        for row in plan["samples"]["chipseq"]:
            if not row["is_control"]:
                key = (row["mark_or_factor"], row["condition"])
                groups[key] = groups.get(key, 0) + 1
        if not groups or any(count != 2 for count in groups.values()):
            raise PlanError("IDR requer exatamente duas replicatas biológicas por mark e condição.", "science.idr")
    plan["statistics"] = _validate_statistics(value.get("statistics", {}), workflow)
    if workflow != "integrative" and not plan["statistics"]["contrasts"]:
        raise PlanError('Os campos “Numerador” e “Denominador” do contraste são obrigatórios.', "statistics.contrasts.0.numerator")
    minimum = plan["statistics"]["min_replicates"]
    for assay in ("rnaseq", "chipseq"):
        assay_rows = [row for row in plan["samples"][assay] if assay == "rnaseq" or not row.get("is_control")]
        counts = {condition:sum(row["condition"] == condition for row in assay_rows) for condition in {row["condition"] for row in assay_rows}}
        for contrast in plan["statistics"]["contrasts"]:
            if assay_rows and (counts.get(contrast["numerator"], 0) < minimum or counts.get(contrast["denominator"], 0) < minimum):
                raise PlanError(f"O contraste requer ao menos {minimum} replicatas por condição em {assay}.", f"{assay}_samples")
    plan["integration"] = _validate_integration(value.get("integration", {}), workflow)
    return plan


def validate_clone(clone):
    if not isinstance(clone, dict) or clone.get("mode") not in ("existing", "new"):
        raise PlanError("Escolha usar ou criar um clone.", "clone.mode")
    repository = _text(clone.get("repository", "https://github.com/GMiguelAlves/HelixForge.git"), "clone.repository", 2048)
    if clone["mode"] == "new" and repository != "https://github.com/GMiguelAlves/HelixForge.git":
        raise PlanError("Nesta etapa, use o repositório oficial do HelixForge.", "clone.repository")
    ref = _text(clone.get("ref", ""), "clone.ref", 200, clone["mode"] == "new")
    if ref and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", ref):
        raise PlanError("Tag, branch ou commit inválido.", "clone.ref")
    return {"mode": clone["mode"], "path": _path(clone.get("path"), "clone.path"), "repository": repository, "ref": ref}


def input_paths(plan):
    paths = []
    for assay in ("rnaseq", "chipseq"):
        for row in plan["samples"][assay]:
            paths.extend(path for path in (row["fastq_1"], row["fastq_2"]) if path)
    paths.extend(path for path in plan["organism"].values() if isinstance(path, str) and path.startswith("/"))
    paths.extend(path for path in plan["integration"].values() if isinstance(path, str) and path.startswith("/"))
    paths.extend(path for path in plan["integration"]["policy_paths"].values() if path)
    return sorted(set(paths))


def submission_from_plan(plan):
    return {"name": plan["name"], "workflow": plan["workflow"], "repo": plan["clone"]["path"],
            "config": plan["storage"]["project_root"] + "/run.config", "launch": plan["storage"]["launch"],
            "output": plan["storage"]["output"], "work": plan["storage"]["work"],
            "partition": plan["runtime"]["partition"], "runtime": plan["runtime"]["profile"],
            "memory": plan["runtime"]["memory"], "hours": plan["runtime"]["hours"], "account": plan["runtime"]["account"]}


def _validate_samples(samples, workflow):
    output, ids = [], set()
    for index, raw in enumerate(samples):
        prefix = f"{workflow}_samples.{index}"
        if not isinstance(raw, dict):
            raise PlanError("Amostra inválida.", prefix)
        sample_id = _cell(raw.get("sample_id"), f"{prefix}.sample_id")
        if sample_id in ids:
            raise PlanError("Os identificadores de amostra devem ser únicos.", f"{prefix}.sample_id")
        ids.add(sample_id)
        row = {"sample_id": sample_id, "fastq_1": _path(raw.get("fastq_1"), f"{prefix}.fastq_1"),
               "fastq_2": _path(raw.get("fastq_2", ""), f"{prefix}.fastq_2", workflow == "rnaseq" or raw.get("layout", "paired") == "paired"),
               "condition": _cell(raw.get("condition"), f"{prefix}.condition"),
               "batch": _cell(raw.get("batch", "batch1"), f"{prefix}.batch"),
               "replicate": _cell(str(raw.get("replicate", "1")), f"{prefix}.replicate")}
        if workflow in ("rnaseq", "all"):
            row.update(dataset=_cell(raw.get("dataset", "dataset1"), f"{prefix}.dataset"),
                       run_accession=_cell(raw.get("run_accession", sample_id), f"{prefix}.run_accession"))
        if workflow in ("chipseq", "all"):
            layout = raw.get("layout", "paired")
            if layout not in ("single", "paired"):
                raise PlanError("Layout deve ser single ou paired.", f"{prefix}.layout")
            is_control = raw.get("is_control") is True
            row.update(layout=layout, assay="input" if is_control else "ChIP-seq",
                       mark_or_factor=_cell(raw.get("mark_or_factor", "input" if is_control else ""), f"{prefix}.mark_or_factor"),
                       control_id=_cell(raw.get("control_id", ""), f"{prefix}.control_id", False),
                       is_control=is_control, organism="", genome_id="")
        output.append(row)
    if workflow in ("chipseq", "all"):
        controls = {row["sample_id"] for row in output if row["is_control"]}
        for index, row in enumerate(output):
            if not row["is_control"] and row["control_id"] not in controls:
                raise PlanError("Cada amostra IP deve apontar para um controle existente.", f"{workflow}_samples.{index}.control_id")
    return output


def _validate_statistics(raw, workflow):
    raw = raw if isinstance(raw, dict) else {}
    variable = _cell(raw.get("variable", "condition"), "statistics.variable")
    covariates = raw.get("covariates", ["batch"])
    if not isinstance(covariates, list) or len(covariates) > 20:
        raise PlanError("Covariáveis inválidas.", "statistics.covariates")
    covariates = [_cell(item, "statistics.covariates") for item in covariates]
    formula = _cell(raw.get("formula", "~ " + " + ".join([*covariates, variable])), "statistics.formula")
    if not formula.startswith("~") or variable not in formula or "batch" in covariates and "batch" not in formula:
        raise PlanError("A fórmula deve conter a variável principal e as covariáveis informadas.", "statistics.formula")
    contrasts = raw.get("contrasts", [])
    if not isinstance(contrasts, list) or len(contrasts) > 100:
        raise PlanError("Contrastes inválidos.", "statistics.contrasts")
    clean = []
    for index, item in enumerate(contrasts):
        if not isinstance(item, dict):
            raise PlanError("Contraste inválido.", f"statistics.contrasts.{index}")
        numerator = _cell(item.get("numerator"), f"statistics.contrasts.{index}.numerator")
        denominator = _cell(item.get("denominator"), f"statistics.contrasts.{index}.denominator")
        clean.append({"id": _cell(item.get("id", f"{numerator}_vs_{denominator}"), f"statistics.contrasts.{index}.id"),
                      "factor": variable, "numerator": numerator, "denominator": denominator,
                      "description": _cell(item.get("description", f"{numerator} versus {denominator}"), f"statistics.contrasts.{index}.description")})
    return {"variable": variable, "covariates": covariates, "formula": formula, "contrasts": clean,
            "alpha": _number(raw.get("alpha", 0.05), "statistics.alpha", 0.000001, 0.5),
            "lfc_threshold": _number(raw.get("lfc_threshold", 1.0), "statistics.lfc_threshold", 0, 100),
            "min_replicates": _number(raw.get("min_replicates", 2), "statistics.min_replicates", 1, 100, True),
            "genes": [_cell(item, "statistics.genes") for item in raw.get("genes", [])] if isinstance(raw.get("genes", []), list) else []}


def _validate_science(raw, workflow):
    raw = raw if isinstance(raw, dict) else {}
    quantification = raw.get("quantification", "salmon")
    if quantification not in ("salmon", "star"):
        raise PlanError("Escolha Salmon ou o provider experimental STAR.", "science.quantification")
    peak_type = raw.get("peak_type", "auto")
    if peak_type not in ("auto", "narrow", "broad"):
        raise PlanError("Escolha um tipo de pico válido.", "science.peak_type")
    effective = _text(str(raw.get("effective_genome_size", "")).strip(), "science.effective_genome_size", 32, False)
    if workflow in ("chipseq", "all"):
        effective = str(_number(effective, "science.effective_genome_size", 1, 10**12, True))
    consensus = raw.get("consensus_method", "replicate_support")
    if consensus not in ("union", "intersection", "replicate_support"):
        raise PlanError("Escolha uma estratégia de consenso válida.", "science.consensus_method")
    idr = raw.get("idr") is True
    if idr and peak_type != "narrow":
        raise PlanError("IDR requer picos narrow.", "science.idr")
    return {"quantification":quantification, "peak_type":peak_type,
            "effective_genome_size":effective, "consensus_method":consensus, "idr":idr}


def _validate_integration(raw, workflow):
    raw = raw if isinstance(raw, dict) else {}
    required = workflow == "integrative"
    policy_mode = raw.get("policy_mode", "templates" if raw.get("use_default_policies", True) is not False else "repository")
    if policy_mode not in ("templates", "repository", "custom"):
        raise PlanError("Escolha como fornecer as políticas integrativas.", "integration.policy_mode")
    names = ("harmonization", "interpretation", "mark_roles", "prioritization_context", "functional_annotation")
    supplied = raw.get("policy_paths", {})
    if not isinstance(supplied, dict):
        raise PlanError("Caminhos de políticas inválidos.", "integration.policy_paths")
    return {"rna_manifest": _path(raw.get("rna_manifest", ""), "integration.rna_manifest", required),
            "chip_manifest": _path(raw.get("chip_manifest", ""), "integration.chip_manifest", required),
            "policy_mode":policy_mode,
            "policy_paths":{name:_path(supplied.get(name, ""), f"integration.policy_paths.{name}", policy_mode == "custom") for name in names}}


def generate_documents(value):
    plan = validate_plan(value)
    root, repo, workflow = plan["storage"]["project_root"], plan["clone"]["path"], plan["workflow"]
    documents = []
    def add(path, content, kind):
        documents.append({"path": f"{root}/{path}", "relative_path": path, "content": content, "kind": kind})
    run_params = {"workflow": workflow, "outdir": plan["storage"]["output"]}
    if workflow in ("rnaseq", "all"):
        metadata_path = f"{root}/config/rnaseq_metadata.tsv"
        de_path = f"{root}/specifications/de_spec.json"
        settings_path = f"{root}/config/rnaseq_user_settings.sh"
        wrapper_path = f"{root}/config/rnaseq_pipeline_config.sh"
        rows = [{**row} for row in plan["samples"]["rnaseq"]]
        add("config/rnaseq_metadata.tsv", _tsv(("dataset", "sample_id", "run_accession", "fastq_1", "fastq_2", "condition", "batch", "replicate"), rows), "metadata")
        stats = plan["statistics"]
        de = {"schema_version":"1.0", "analysis_id":"primary", "scope":"all_projects", "correction":"raw", "provider":"deseq2", "test":"wald",
              "target_dir":f"{plan['storage']['output']}/rnaseq/differential_expression/primary",
              "design":{"variable":stats["variable"], "covariates":stats["covariates"], "formula":stats["formula"]}, "contrasts":stats["contrasts"],
              "filter":{"method":"none"}, "parameters":{"alpha":stats["alpha"], "lfc_threshold":stats["lfc_threshold"], "min_replicates":stats["min_replicates"], "non_integer_counts":"round"}}
        add("specifications/de_spec.json", _json(de), "specification")
        exports = {"PIPELINE_NAME":plan["name"], "ORGANISM_NAME":plan["organism"]["name"], "REFERENCE_ID":plan["organism"]["reference_id"], "SCRATCH_ROOT":plan["storage"]["work"],
                   "REF_GENOME_FA":plan["organism"]["genome_fasta"], "REF_TRANSCRIPTS_FA":plan["organism"]["transcriptome_fasta"], "REF_GTF":plan["organism"]["annotation"],
                   "METADATA_FINAL":metadata_path, "METADATA_FINAL_NEW":metadata_path, "QUANT_METHOD":plan["science"]["quantification"], "FASTQ_LAYOUT":"paired",
                   "PIPELINE_EXECUTOR":"slurm", "SLURM_PARTITION":plan["runtime"]["partition"], "SLURM_ACCOUNT":plan["runtime"]["account"],
                   "MEMORY":plan["runtime"]["memory"] + "G", "SLURM_TIME":plan["runtime"]["hours"] + ":00:00", "RUN_GENE_REPORT":"1" if stats["genes"] else "0"}
        add("config/rnaseq_user_settings.sh", _shell_exports(exports), "settings")
        add("config/rnaseq_pipeline_config.sh", _wrapper(settings_path, f"{repo}/pipelines/rnaseq/config/pipeline_config.sh"), "wrapper")
        run_params.update(rnaseq_config=wrapper_path, rnaseq_de_spec=de_path)
        if stats["genes"]:
            run_params["rnaseq_report_enabled"] = True
            run_params["rnaseq_report_genes"] = ",".join(stats["genes"])
    if workflow in ("chipseq", "all"):
        metadata_path = f"{root}/config/chipseq_metadata.tsv"
        db_path = f"{root}/specifications/differential_binding.json"
        settings_path = f"{root}/config/chipseq_user_settings.sh"
        wrapper_path = f"{root}/config/chipseq_pipeline_config.sh"
        rows = [{**row, "organism":plan["organism"]["name"], "genome_id":plan["organism"]["reference_id"]} for row in plan["samples"]["chipseq"]]
        columns = ("sample_id", "fastq_1", "fastq_2", "layout", "assay", "mark_or_factor", "condition", "replicate", "batch", "control_id", "is_control", "organism", "genome_id")
        add("config/chipseq_metadata.tsv", _tsv(columns, rows), "metadata")
        stats = plan["statistics"]
        db = {"schema_version":"1.0", "provider":"deseq2", "test":"wald", "peak_universe":{"method":"union"},
              "counting":{"provider":"featurecounts", "unit":"fragments", "strandedness":0, "min_mapq":0, "overlap_policy":"any", "allow_multi_overlap":False, "allow_multimapping":False, "fractional":False, "require_both_ends_mapped":True, "exclude_chimeric":True},
              "design":{"formula":stats["formula"], "variable":stats["variable"], "covariates":stats["covariates"]}, "contrasts":stats["contrasts"],
              "filter":{"method":"minimum_count", "min_count":10, "min_samples":2}, "normalization":"deseq2_median_of_ratios",
              "parameters":{"alpha":stats["alpha"], "lfc_threshold":stats["lfc_threshold"], "min_replicates":stats["min_replicates"]}}
        add("specifications/differential_binding.json", _json(db), "specification")
        exports = {"PIPELINE_NAME":plan["name"], "ORGANISM_NAME":plan["organism"]["name"], "METADATA_FILE":metadata_path,
                   "GENOME_FASTA":plan["organism"]["genome_fasta"], "ANNOTATION_FILE":plan["organism"]["annotation"],
                   "BLACKLIST_BED":plan["organism"]["blacklist"], "OUTPUT_DIR":plan["storage"]["output"], "WORK_ROOT":plan["storage"]["work"],
                   "PIPELINE_EXECUTOR":"slurm", "SLURM_PARTITION":plan["runtime"]["partition"], "SLURM_ACCOUNT":plan["runtime"]["account"],
                   "MEMORY":plan["runtime"]["memory"] + "G", "SLURM_TIME":plan["runtime"]["hours"] + ":00:00",
                   "READ_LAYOUT":"metadata", "ALIGNER":"bowtie2", "PEAK_TYPE":plan["science"]["peak_type"],
                   "MACS_GENOME_SIZE":plan["science"]["effective_genome_size"]}
        add("config/chipseq_user_settings.sh", _shell_exports(exports), "settings")
        add("config/chipseq_pipeline_config.sh", _wrapper(settings_path, f"{repo}/pipelines/chipseq/config/pipeline_config.sh"), "wrapper")
        run_params.update(chipseq_config=wrapper_path, chipseq_db_spec=db_path,
                          chipseq_peak_type=plan["science"]["peak_type"],
                          chipseq_effective_genome_size=int(plan["science"]["effective_genome_size"]),
                          chipseq_consensus_method="idr" if plan["science"]["idr"] else plan["science"]["consensus_method"])
        if plan["science"]["idr"]:
            run_params.update(chipseq_idr_threshold=0.05, chipseq_idr_rank_metric="signal_value")
    if workflow == "integrative":
        run_params.update(rna_manifest=plan["integration"]["rna_manifest"], chip_manifest=plan["integration"]["chip_manifest"])
    if workflow in ("integrative", "all") and plan["integration"]["policy_mode"] == "templates":
        policy_files = _default_policies()
        for path, content in policy_files.items():
            add(path, content, "policy")
        run_params.update(integrative_harmonization_policy=f"{root}/policies/harmonization_policy.json",
                          integrative_interpretation_policy=f"{root}/policies/interpretation_policy.json",
                          integrative_mark_roles=f"{root}/policies/mark_roles.tsv",
                          integrative_prioritization_context=f"{root}/policies/prioritization_context.tsv",
                          integrative_functional_annotation=f"{root}/policies/functional_annotation.tsv")
    elif workflow in ("integrative", "all") and plan["integration"]["policy_mode"] == "custom":
        custom = plan["integration"]["policy_paths"]
        run_params.update(integrative_harmonization_policy=custom["harmonization"],
                          integrative_interpretation_policy=custom["interpretation"],
                          integrative_mark_roles=custom["mark_roles"],
                          integrative_prioritization_context=custom["prioritization_context"],
                          integrative_functional_annotation=custom["functional_annotation"])
    config_lines = ["params {"] + [f"    {key} = {_groovy_value(value)}" for key, value in run_params.items()] + ["}", ""]
    add("run.config", "\n".join(config_lines), "nextflow")
    return {"plan": plan, "documents": documents}


def _shell_exports(values):
    lines = ["#!/usr/bin/env bash", "# Generated by the HelixForge preparation wizard."]
    lines += [f"export {key}={shlex.quote(str(value))}" for key, value in values.items() if value != ""]
    return "\n".join(lines) + "\n"


def _wrapper(settings, canonical):
    return "#!/usr/bin/env bash\n# Generated wrapper; the canonical pipeline configuration remains inside the clone.\n" + f"export USER_SETTINGS_FILE={shlex.quote(settings)}\nsource {shlex.quote(canonical)}\n"


def _default_policies():
    root = Path(__file__).resolve().parents[2] / "assets" / "integration"
    mapping = {"policies/harmonization_policy.json":"harmonization_policy.v1.json",
               "policies/interpretation_policy.json":"interpretation_policy.v1.json",
               "policies/mark_roles.tsv":"mark_roles.v1.tsv",
               "policies/prioritization_context.tsv":"prioritization_context.template.tsv",
               "policies/functional_annotation.tsv":"functional_annotation.template.tsv"}
    return {destination:(root / source).read_text(encoding="utf-8") for destination, source in mapping.items()}
