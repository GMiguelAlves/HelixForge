#!/usr/bin/env python3
"""Fixed remote helper for clone inspection and atomic analysis preparation."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


MARKER = "HELIXFORGE_PREPARATION_V1:"


def reply(value, status=0):
    print(MARKER + json.dumps(value, ensure_ascii=False), flush=True)
    raise SystemExit(status)


def fail(message, code="invalid"):
    reply({"error": message, "code": code}, 2)


def path(value):
    if not isinstance(value, str) or not value.startswith("/") or len(value) > 2048 or "%" in value or any(ord(char) < 32 for char in value) or any(part in (".", "..") for part in value.split("/")):
        fail("Caminho remoto inválido.")
    return Path(value)


def run(args, timeout=20):
    try:
        return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        fail("A verificação remota não pôde ser concluída.", "unavailable")


def inspect_clone(clone):
    target = path(clone["path"])
    if target.is_symlink():
        fail("O caminho do clone não pode ser um link simbólico.", "symlink")
    if clone["mode"] == "new":
        if target.exists() or target.is_symlink():
            fail("O destino do novo clone já existe.", "exists")
        parent = target.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
            fail("O diretório pai do clone não permite escrita.", "permission")
        if not shutil.which("git"):
            fail("Git não está disponível no servidor.", "environment")
        raw_commit = bool(re.fullmatch(r"[0-9a-fA-F]{40}", clone["ref"]))
        checked = run(["git", "ls-remote", clone["repository"], *( [] if raw_commit else [clone["ref"]])], 30)
        found = any(line.split("\t", 1)[0].lower() == clone["ref"].lower() for line in checked.stdout.splitlines()) if raw_commit else bool(checked.stdout.strip())
        if checked.returncode or not found:
            fail("A tag, branch ou commit não foi encontrada no repositório oficial.", "missing")
        return {"state":"ready_to_clone", "path":str(target), "repository":clone["repository"], "ref":clone["ref"], "command":"git clone --branch " + clone["ref"] + " --single-branch " + clone["repository"] + " " + str(target)}
    try:
        stat = target.stat()
    except OSError:
        fail("O clone do HelixForge não foi encontrado.", "missing")
    if not target.is_dir() or stat.st_uid != os.getuid():
        fail("O clone deve ser um diretório pertencente ao usuário autenticado.", "permission")
    for required in ("main.nf", "nextflow.config", ".git"):
        item = target / required
        if item.is_symlink() or not item.exists():
            fail("O diretório não é um clone HelixForge válido: falta " + required + ".", "missing")
    commit = run(["git", "-C", str(target), "rev-parse", "HEAD"])
    branch = run(["git", "-C", str(target), "branch", "--show-current"])
    status = run(["git", "-C", str(target), "status", "--porcelain", "--untracked-files=no"])
    if commit.returncode or branch.returncode or status.returncode:
        fail("Não foi possível identificar a versão do clone.", "invalid")
    return {"state":"available", "path":str(target), "commit":commit.stdout.strip(),
            "ref":branch.stdout.strip() or "detached", "dirty":bool(status.stdout.strip())}


def create_clone(clone):
    inspect_clone(clone)
    target = path(clone["path"])
    ref = clone["ref"]
    raw_commit = bool(re.fullmatch(r"[0-9a-fA-F]{40}", ref))
    args = ["git", "clone", *( [] if raw_commit else ["--single-branch", "--branch", ref]), clone["repository"], str(target)]
    completed = run(args, 180)
    if completed.returncode:
        fail("A clonagem falhou: " + completed.stderr.strip()[:500], "rejected")
    if raw_commit:
        checked = run(["git", "-C", str(target), "checkout", "--detach", ref], 30)
        if checked.returncode:
            fail("O commit foi validado, mas não pôde ser selecionado no clone.", "rejected")
    clone = dict(clone)
    clone["mode"] = "existing"
    return inspect_clone(clone)


def preflight(request):
    clone = inspect_clone({**request["clone"], "mode":"existing"})
    inputs = request.get("inputs")
    documents = request.get("documents")
    if not isinstance(inputs, list) or not isinstance(documents, list) or len(inputs) > 4000 or len(documents) > 32:
        fail("Inventário de preparação inválido.")
    for raw in inputs:
        item = path(raw)
        if item.is_symlink() or not item.is_file() or not os.access(item, os.R_OK):
            fail("Entrada ausente, ilegível ou link simbólico: " + str(item), "missing")
    integration = request.get("integration") or {}
    if integration:
        manifests = []
        for key in ("rna_manifest", "chip_manifest"):
            manifest = path(integration.get(key))
            artifacts = manifest.parent / "integration_artifacts"
            if artifacts.is_symlink() or not artifacts.is_dir() or not os.access(artifacts, os.R_OK | os.X_OK):
                fail("O diretório integration_artifacts irmão não está disponível para " + str(manifest) + ".", "missing")
            try:
                if manifest.stat().st_size > 4 * 1024 * 1024:
                    fail("Manifest integrativo maior que 4 MiB.", "invalid")
                with manifest.open(encoding="utf-8") as handle:
                    manifests.append(json.load(handle))
            except (OSError, ValueError):
                fail("Manifest integrativo inválido: " + str(manifest), "invalid")
        expected_types = ("rnaseq_run_manifest", "chipseq_run_manifest")
        consumable = {"complete", "complete_empty", "stub"}
        for document, expected in zip(manifests, expected_types):
            required = {"schema_version", "integration_api_version", "type", "id", "status", "run", "reference", "artifacts"}
            if (not isinstance(document, dict) or required - set(document)
                    or document.get("schema_version") != "1.0" or document.get("integration_api_version") != "1.0"
                    or document.get("type") != expected or document.get("status") not in consumable
                    or not isinstance(document.get("reference"), dict) or not isinstance(document.get("artifacts"), list)):
                fail("O manifest não atende ao contrato integrativo " + expected + ".", "incompatible")
            identifiers = [item.get("artifact_id") for item in document["artifacts"] if isinstance(item, dict)]
            if len(identifiers) != len(document["artifacts"]) or len(identifiers) != len(set(identifiers)):
                fail("O manifest contém artefatos inválidos ou duplicados.", "incompatible")
            reference_id = document["reference"].get("reference_id")
            if any(item.get("reference_id") != reference_id for item in document["artifacts"]):
                fail("Um artefato não corresponde à referência declarada no manifest.", "incompatible")
        left, right = (item["reference"] for item in manifests)
        exact = ("reference_id", "genome_id", "annotation_id")
        folded = ("organism", "assembly")
        if (any(left.get(field) != right.get(field) for field in exact)
                or any(str(left.get(field) or "").casefold() != str(right.get(field) or "").casefold() for field in folded)):
            fail("Os manifests RNA-seq e ChIP-seq não têm organismo, referência, anotação e genome/build compatíveis.", "incompatible")
    root = path(request["project_root"])
    if root.exists() or root.is_symlink():
        fail("O diretório do projeto já existe; esta versão não sobrescreve preparações.", "exists")
    parent = root.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        fail("O diretório pai do projeto não permite escrita.", "permission")
    storage = request.get("storage")
    if not isinstance(storage, dict):
        fail("Diretórios da análise ausentes.")
    launch = path(storage.get("launch"))
    if launch.is_symlink() or not launch.is_dir() or not os.access(launch, os.W_OK | os.X_OK):
        fail("O diretório de lançamento não existe ou não permite escrita.", "permission")
    for key, label in (("output", "saída"), ("work", "trabalho")):
        target = path(storage.get(key))
        if target.exists() or target.is_symlink():
            fail("O diretório de " + label + " já existe; escolha um caminho novo.", "exists")
        candidate = target.parent
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        if not candidate.is_dir() or not os.access(candidate, os.W_OK | os.X_OK):
            fail("O caminho de " + label + " não pode ser criado.", "permission")
    for document in documents:
        destination = path(document["path"])
        if destination != root and root not in destination.parents:
            fail("Documento fora do diretório do projeto.")
        if destination.exists() or destination.is_symlink():
            fail("Um documento de destino já existe: " + str(destination), "exists")
    for command in ("java", "nextflow", "sbatch"):
        if not shutil.which(command):
            fail(command + " não está disponível no PATH remoto.", "environment")
    partition = request.get("runtime", {}).get("partition")
    if not shutil.which("scontrol"):
        fail("scontrol não está disponível para validar a partição.", "environment")
    partition_check = run(["scontrol", "show", "partition", partition])
    if partition_check.returncode or not partition_check.stdout.strip():
        fail("A partição Slurm informada não foi encontrada.", "missing")
    account = request.get("runtime", {}).get("account") or ""
    account_state = "não informada"
    if account:
        account_state = "será confirmada pelo sbatch"
        if shutil.which("sacctmgr"):
            user = run(["id", "-un"])
            association = run(["sacctmgr", "-n", "-P", "show", "assoc", "where", "user=" + user.stdout.strip(), "account=" + account, "format=Account"])
            if association.returncode == 0:
                accounts = {line.split("|", 1)[0].strip() for line in association.stdout.splitlines()}
                if account not in accounts:
                    fail("A conta Slurm não está associada ao usuário autenticado.", "permission")
                account_state = "associação confirmada"
    java = run(["java", "-version"])
    java_text = java.stderr + java.stdout
    if java.returncode or not re.search(r'version\s+"21(?:[._"]|$)', java_text):
        fail("Java 21 é obrigatório.", "version")
    nextflow = run(["nextflow", "-version"])
    if nextflow.returncode or "25.10.7" not in nextflow.stdout + nextflow.stderr:
        fail("Nextflow 25.10.7 é obrigatório.", "version")
    profile = request.get("runtime", {}).get("profile")
    if "apptainer" in profile and not shutil.which("apptainer"):
        fail("Apptainer não está disponível no servidor.", "environment")
    if "singularity" in profile and not shutil.which("singularity"):
        fail("Singularity não está disponível no servidor.", "environment")
    return {"state":"ready", "clone":clone, "inputs":len(inputs), "documents":len(documents),
            "java":"21", "nextflow":"25.10.7", "sbatch":True, "partition":partition,
            "account":account_state, "launch":str(launch), "storage":"destinos novos e graváveis",
            "integration_compatible":bool(integration)}


def write_documents(request):
    preflight(request)
    root = path(request["project_root"])
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".helixforge-preparation-", dir=root.parent))
    try:
        for document in request["documents"]:
            relative = Path(document["relative_path"])
            if relative.is_absolute() or ".." in relative.parts or not isinstance(document.get("content"), str):
                fail("Documento de preparação inválido.")
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".tmp")
            with temporary.open("x", encoding="utf-8", newline="") as handle:
                handle.write(document["content"])
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        os.replace(stage, root)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"state":"written", "project_root":str(root), "documents":[document["path"] for document in request["documents"]]}


def main():
    try:
        request = json.load(sys.stdin)
        action = request.get("action") if isinstance(request, dict) else None
        if action == "inspect_clone":
            reply(inspect_clone(request["clone"]))
        if action == "create_clone":
            reply(create_clone(request["clone"]))
        if action == "preflight":
            reply(preflight(request))
        if action == "write":
            reply(write_documents(request))
        fail("Ação remota inválida.")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        fail("Solicitação remota inválida.")


if __name__ == "__main__":
    main()
