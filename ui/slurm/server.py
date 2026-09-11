#!/usr/bin/env python3
"""Local, single-user Slurm UI. Python 3.10+ and an existing SSH setup."""

import argparse
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import importlib.util
import json
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import threading
import time


STATIC = Path(__file__).parent / "static"
PROBE_SPEC = importlib.util.spec_from_file_location('result_probe', Path(__file__).with_name('probe.py'))
PROBE = importlib.util.module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(PROBE)
PREPARATION_SPEC = importlib.util.spec_from_file_location('submission_documents', Path(__file__).with_name('submission.py'))
PREPARATION = importlib.util.module_from_spec(PREPARATION_SPEC)
PREPARATION_SPEC.loader.exec_module(PREPARATION)
SEPARATOR = "\x1f"
MARKER = "HELIXFORGE_SLURM_V1:"
FIELDS = ("id", "name", "state", "elapsed", "time_limit", "nodes", "cpus",
          "memory", "partition", "reason", "submitted", "start")
FORMAT = SEPARATOR.join(("%i", "%j", "%T", "%M", "%l", "%D", "%C",
                         "%m", "%P", "%R", "%V", "%S"))
SUBMISSION_FIELDS = ("name", "workflow", "repo", "config", "launch", "output", "work",
                     "partition", "runtime", "memory", "hours", "account")
# Only fixed code goes to the remote shell. No browser input is interpolated.
# Reset presentation/filter variables so a user's defaults cannot hide jobs.
REMOTE_SCRIPT = r'''
hf_user=$(id -un) || exit 1
command -v squeue >/dev/null 2>&1 || { echo 'HF_SQUEUE_MISSING' >&2; exit 127; }
for hf_var in $(env | sed -n 's/^\(SQUEUE_[A-Za-z0-9_]*\)=.*/\1/p'); do
    unset "$hf_var"
done
unset SLURM_CLUSTERS SLURM_JSON SLURM_YAML
export LC_ALL=C SLURM_BITSTR_LEN=4096 SLURM_TIME_FORMAT=standard
printf 'HELIXFORGE_SLURM_V1:%s\n' "$hf_user"
exec squeue --local --all --array --noheader --states=all --user="$hf_user" --format=FORMAT_PLACEHOLDER
'''.replace("FORMAT_PLACEHOLDER", shlex.quote(FORMAT))

REMOTE_SUBMISSION_SCRIPT = r'''
import json, os, re, shlex, shutil, subprocess, sys

def fail(message, code="invalid"):
    print("HELIXFORGE_SUBMISSION_V1:" + json.dumps({"error": message, "code": code}, ensure_ascii=False))
    raise SystemExit(2)

request = json.load(sys.stdin)
draft = request.get("draft")
action = request.get("action")
fields = ("name", "workflow", "repo", "config", "launch", "output", "work",
          "partition", "runtime", "memory", "hours", "account")
if action not in ("prepare", "submit") or not isinstance(draft, dict) or set(draft) != set(fields):
    fail("Solicitação de submissão inválida.")
if not all(isinstance(draft[key], str) for key in fields):
    fail("Os campos da execução devem ser textos.")
if not draft["name"] or len(draft["name"]) > 120 or any(ord(char) < 32 for char in draft["name"]):
    fail("Informe um nome válido para a execução.")
if draft["workflow"] not in ("rnaseq", "chipseq", "integrative", "all") or draft["runtime"] not in ("slurm", "slurm,apptainer", "slurm,singularity"):
    fail("Workflow ou ambiente inválido.")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", draft["partition"]) or (draft["account"] and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", draft["account"])):
    fail("Partição ou conta inválida.")
for key in ("repo", "config", "launch", "output", "work"):
    value = draft[key]
    if not value.startswith("/") or len(value) > 2048 or any(ord(char) < 32 for char in value) or "%" in value or any(part in (".", "..") for part in value.split("/")):
        fail("Os caminhos devem ser absolutos e normalizados.")
def contains(parent, child):
    return parent == "/" or child == parent or child.startswith(parent.rstrip("/") + "/")
if contains(draft["output"], draft["work"]) or contains(draft["work"], draft["output"]) or contains(draft["output"], draft["repo"]) or contains(draft["work"], draft["repo"]) or contains(draft["output"], draft["launch"]) or contains(draft["work"], draft["launch"]):
    fail("Separe saída e trabalho; eles não podem conter o repositório ou o diretório de lançamento.")
for key, maximum in (("memory", 1024), ("hours", 720)):
    if not re.fullmatch(r"[0-9]+", draft[key]) or not 1 <= int(draft[key]) <= maximum:
        fail("Memória e tempo devem ser números inteiros dentro dos limites.")
for command in ("nextflow", "sbatch", "java"):
    if not shutil.which(command):
        fail(command + " não está disponível no PATH da sessão remota.", "environment")
if not os.path.isfile(os.path.join(draft["repo"], "nextflow.config")):
    fail("O diretório informado não contém nextflow.config.", "missing")
if not os.path.isfile(draft["config"]):
    fail("A configuração Nextflow não foi encontrada.", "missing")
if not os.path.isdir(draft["launch"]) or not os.access(draft["launch"], os.W_OK | os.X_OK):
    fail("O diretório de lançamento não existe ou não permite escrita.", "permission")
for key in ("output", "work"):
    if os.path.lexists(draft[key]):
        fail("O diretório de " + ("saída" if key == "output" else "trabalho") + " já existe; escolha um caminho novo.", "exists")
    parent = os.path.dirname(draft[key])
    while parent and not os.path.exists(parent):
        parent = os.path.dirname(parent)
    if not parent or not os.path.isdir(parent) or not os.access(parent, os.W_OK | os.X_OK):
        fail("O caminho de " + ("saída" if key == "output" else "trabalho") + " não pode ser criado.", "permission")
name = "hf-" + re.sub(r"[^A-Za-z0-9_-]+", "-", draft["name"]).strip("-")[:60]
if name == "hf-":
    name = "helixforge"
nextflow = ["nextflow", "run", draft["repo"], "-profile", draft["runtime"], "-c", draft["config"],
            "-work-dir", draft["work"], "--workflow", draft["workflow"], "--outdir", draft["output"]]
sbatch = ["sbatch", "--parsable", "--job-name", name, "--partition", draft["partition"],
          "--cpus-per-task", "1", "--mem", draft["memory"] + "G", "--time", draft["hours"] + ":00:00",
          "--chdir", draft["launch"], "--output", os.path.join(draft["launch"], "helixforge-%j.log")]
if draft["account"]:
    sbatch += ["--account", draft["account"]]
sbatch += ["--wrap", "exec " + shlex.join(nextflow)]
result = {"ok": True, "user": os.environ.get("USER") or "", "command": shlex.join(sbatch),
          "directory": draft["output"], "launch": draft["launch"]}
if action == "submit":
    completed = subprocess.run(sbatch, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, timeout=30, check=False)
    if completed.returncode:
        fail("O Slurm recusou a submissão: " + completed.stderr.strip()[:500], "rejected")
    job_id = completed.stdout.strip().split(";", 1)[0]
    if not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", job_id):
        fail("O sbatch não retornou um ID de job reconhecível.", "response")
    result["job_id"] = job_id
print("HELIXFORGE_SUBMISSION_V1:" + json.dumps(result, ensure_ascii=False))
'''


class MonitorError(Exception):
    def __init__(self, message, status=502, code="unavailable"):
        super().__init__(message)
        self.status = status
        self.code = code


def connection_config(value):
    if not isinstance(value, dict) or set(value) - {"host", "user", "port", "control_path"}:
        raise MonitorError("Configuração de conexão inválida.", 400)
    host, user, port, control_path = (value.get(key, "") for key in ("host", "user", "port", "control_path"))
    if not all(isinstance(item, str) for item in (host, user, port, control_path)):
        raise MonitorError("Host, usuário e porta devem ser textos.", 400)
    host, user, port = host.strip(), user.strip(), port.strip()
    if not host or len(host) > 253:
        raise MonitorError("Informe um alias SSH ou endereço de servidor.", 400)
    if "%" in host:
        raise MonitorError("Para IPv6 com escopo de interface, use um alias no SSH config.", 400)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", host):
            raise MonitorError("Host inválido. Use o alias SSH ou endereço, sem usuário ou comando.", 400)
    if user and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]{0,127}", user):
        raise MonitorError("Usuário SSH inválido.", 400)
    if port and (not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535):
        raise MonitorError("A porta deve estar entre 1 e 65535.", 400)
    control_path = control_path.strip()
    if control_path and (len(control_path) > 1024 or not control_path.startswith("/")
                         or any(ord(char) < 32 for char in control_path)
                         or "%" in control_path):
        raise MonitorError("Informe o caminho absoluto do socket SSH no Linux/WSL, sem tokens de expansão.", 400)
    return {"host": host, "user": user, "port": str(int(port)) if port else "", "control_path": control_path}


def ssh_arguments(config):
    args = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=10", "-o", "ConnectionAttempts=1",
            "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
            "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no",
            "-o", "RemoteCommand=none", "-o", "PermitLocalCommand=no",
            "-o", "ControlMaster=no", "-o", "ControlPersist=no"]
    if config["port"]:
        args += ["-p", config["port"]]
    if config["user"]:
        args += ["-l", config["user"]]
    if config.get("control_path"):
        args += ["-S", config["control_path"]]
    return args + [config["host"], "sh -c " + shlex.quote(REMOTE_SCRIPT)]


def parse_queue(output):
    # splitlines() also splits on ASCII unit separators; split only on newline.
    lines = output.replace("\r\n", "\n").split("\n")
    markers = [i for i, line in enumerate(lines) if line.startswith(MARKER)]
    if len(markers) != 1:
        raise MonitorError("Resposta SSH inesperada: não foi possível identificar o usuário remoto.")
    start = markers[0]
    user = lines[start][len(MARKER):].strip()
    if not user:
        raise MonitorError("O servidor não informou o usuário autenticado.")
    jobs = []
    for line in lines[start + 1:]:
        if not line.strip():
            continue
        values = line.split(SEPARATOR)
        if len(values) != len(FIELDS):
            raise MonitorError("Formato inesperado do squeue. A lista não pôde ser lida por completo.")
        jobs.append(dict(zip(FIELDS, (value.strip() for value in values))))
    return user, jobs


def query_jobs(config):
    try:
        result = subprocess.run(
            ssh_arguments(config), stdin=subprocess.DEVNULL, capture_output=True,
            encoding="utf-8", errors="replace", timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as exc:
        raise MonitorError("OpenSSH não encontrado. Instale o cliente SSH e disponibilize-o no PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MonitorError("A consulta excedeu 25 segundos. Verifique o túnel e a resposta do servidor.", 504) from exc
    if result.returncode:
        error = result.stderr.lower()
        if "hf_squeue_missing" in error:
            message = "SSH conectado, mas squeue não está no PATH da sessão remota. Ajuste o ambiente não interativo do servidor."
        elif "host key verification failed" in error or "identification has changed" in error:
            message = "A identidade SSH não está confirmada. Verifique o host pelo terminal usando o mesmo destino e porta."
        elif "permission denied" in error or "authentication" in error:
            message = "Falha na autenticação SSH. Use uma chave disponível no agente ou uma conexão SSH compartilhada já autenticada."
        elif "refused" in error:
            message = "Conexão recusada. Confira o host, a porta e se o túnel está ativo."
        elif "could not resolve" in error:
            message = "Servidor ou alias SSH não encontrado. Confira a configuração do SSH neste computador."
        else:
            message = "A consulta SSH/Slurm falhou. Verifique a conexão e se squeue funciona na sessão remota."
        raise MonitorError(message)
    user, jobs = parse_queue(result.stdout)
    return {"user": user, "jobs": jobs, "checked_at": datetime.now(timezone.utc).isoformat()}


def submission_draft(value):
    if not isinstance(value, dict) or set(value) != set(SUBMISSION_FIELDS):
        raise MonitorError("Dados da execução inválidos.", 400, "invalid")
    if not all(isinstance(value[field], str) for field in SUBMISSION_FIELDS):
        raise MonitorError("Os campos da execução devem ser textos.", 400, "invalid")
    draft = {field: value[field].strip() for field in SUBMISSION_FIELDS}
    if not draft["name"] or len(draft["name"]) > 120 or any(ord(char) < 32 for char in draft["name"]):
        raise MonitorError("Informe um nome válido para a execução.", 400, "invalid")
    if draft["workflow"] not in ("rnaseq", "chipseq", "integrative", "all"):
        raise MonitorError("Escolha um workflow válido.", 400, "invalid")
    if draft["runtime"] not in ("slurm", "slurm,apptainer", "slurm,singularity"):
        raise MonitorError("Escolha um ambiente válido.", 400, "invalid")
    for field in ("repo", "config", "launch", "output", "work"):
        path = draft[field]
        if (not path.startswith("/") or len(path) > 2048 or "%" in path
                or any(ord(char) < 32 for char in path)
                or any(part in (".", "..") for part in path.split("/"))):
            raise MonitorError("Use caminhos absolutos e normalizados, sem '.', '..' ou '%'.", 400, "invalid")
        draft[field] = path.rstrip("/") or "/"
    contains = lambda parent, child: parent == "/" or child == parent or child.startswith(parent + "/")
    if (contains(draft["output"], draft["work"]) or contains(draft["work"], draft["output"])
            or contains(draft["output"], draft["repo"]) or contains(draft["work"], draft["repo"])
            or contains(draft["output"], draft["launch"]) or contains(draft["work"], draft["launch"])):
        raise MonitorError("Separe saída e trabalho; eles não podem conter o repositório ou o diretório de lançamento.", 400, "invalid")
    for field, maximum in (("memory", 1024), ("hours", 720)):
        if not re.fullmatch(r"[0-9]+", draft[field]) or not 1 <= int(draft[field]) <= maximum:
            raise MonitorError("Memória e tempo devem ser números inteiros dentro dos limites.", 400, "invalid")
        draft[field] = str(int(draft[field]))
    identifier = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}"
    if not re.fullmatch(identifier, draft["partition"]) or (draft["account"] and not re.fullmatch(identifier, draft["account"])):
        raise MonitorError("Partição ou conta inválida.", 400, "invalid")
    return draft


def remote_submission(config, draft, action):
    encoded = base64.b64encode(REMOTE_SUBMISSION_SCRIPT.encode()).decode()
    command = "import base64;exec(base64.b64decode(" + repr(encoded) + "))"
    args = ssh_arguments(config)[:-1] + ["python3 -c " + shlex.quote(command)]
    try:
        result = subprocess.run(args, input=json.dumps({"action": action, "draft": draft}), capture_output=True,
                                encoding="utf-8", errors="replace", timeout=40,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError as exc:
        raise MonitorError("OpenSSH não encontrado.") from exc
    except subprocess.TimeoutExpired as exc:
        message = ("A submissão não respondeu. Consulte a fila antes de tentar novamente; o job pode ter sido aceito."
                   if action == "submit" else "A validação remota excedeu o tempo limite.")
        raise MonitorError(message, 504, "uncertain" if action == "submit" else "unavailable") from exc
    lines = [line for line in result.stdout.split("\n") if line.startswith("HELIXFORGE_SUBMISSION_V1:")]
    if len(lines) != 1:
        raise MonitorError("A resposta remota da submissão é inválida.", code="response")
    try:
        data = json.loads(lines[0].split(":", 1)[1])
    except ValueError as exc:
        raise MonitorError("A resposta remota da submissão é inválida.", code="response") from exc
    if "error" in data:
        raise MonitorError(data["error"], 400 if data.get("code") in ("invalid", "missing", "exists") else 502,
                           data.get("code", "rejected"))
    if result.returncode:
        raise MonitorError("A sessão remota terminou antes de confirmar a operação.", code="response")
    if (data.get("ok") is not True or data.get("directory") != draft["output"] or data.get("launch") != draft["launch"]
            or not isinstance(data.get("command"), str) or len(data["command"]) > 16384
            or not isinstance(data.get("user"), str) or len(data["user"]) > 256
            or (action == "submit" and not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", str(data.get("job_id", ""))))):
        raise MonitorError("A resposta remota da submissão não corresponde à execução revisada.", code="response")
    return data


def remote_preparation(config, request, timeout=45):
    script = Path(__file__).with_name("remote_prepare.py").read_bytes()
    command = "import base64;exec(base64.b64decode(" + repr(base64.b64encode(script).decode()) + "))"
    args = ssh_arguments(config)[:-1] + ["python3 -c " + shlex.quote(command)]
    try:
        result = subprocess.run(args, input=json.dumps(request), capture_output=True, encoding="utf-8", errors="replace",
                                timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError as exc:
        raise MonitorError("OpenSSH não encontrado.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MonitorError("A preparação remota excedeu o tempo limite. Verifique o servidor antes de repetir uma alteração.",
                           504, "uncertain" if request.get("action") in ("create_clone", "write") else "unavailable") from exc
    lines = [line for line in result.stdout.split("\n") if line.startswith("HELIXFORGE_PREPARATION_V1:")]
    if len(lines) != 1:
        raise MonitorError("A resposta da preparação remota é inválida.", code="response")
    try:
        data = json.loads(lines[0].split(":", 1)[1])
    except ValueError as exc:
        raise MonitorError("A resposta da preparação remota é inválida.", code="response") from exc
    if "error" in data:
        code = data.get("code", "invalid")
        raise MonitorError(data["error"], 400 if code in ("invalid", "missing", "exists", "symlink", "version") else 502, code)
    if result.returncode:
        raise MonitorError("A sessão remota terminou antes de confirmar a preparação.", code="response")
    return data


def query_execution(value):
    if not isinstance(value, dict) or set(value) not in ({"connection", "directory"}, {"connection", "directory", "log"}, {"connection", "directory", "file"}):
        raise MonitorError("Cadastro de execução inválido.", 400)
    config = connection_config(value["connection"])
    if 'file' in value:
        try:
            PROBE.validate_file(value['file'])
        except ValueError as exc:
            raise MonitorError(str(exc), 400) from exc
    if "log" in value:
        selection = value["log"]
        if (not isinstance(selection, dict) or set(selection) != {"task_id", "native_id", "name", "file"}
                or any(not isinstance(item, str) or len(item) > 512 for item in selection.values())
                or selection["file"] not in (".command.out", ".command.err", ".command.log")):
            raise MonitorError("Seleção de log inválida.", 400)
    directory = value["directory"]
    if (not isinstance(directory, str) or not directory.startswith("/") or len(directory) > 2048
            or any(ord(char) < 32 for char in directory)):
        raise MonitorError("Informe o caminho absoluto do diretório de saída no servidor.", 400)
    script = (Path(__file__).parent / "probe.py").read_bytes()
    command = "import base64;exec(base64.b64decode(" + repr(base64.b64encode(script).decode()) + "))"
    args = ssh_arguments(config)[:-1] + ["python3 -c " + shlex.quote(command)]
    try:
        request = {"directory": directory}
        if "log" in value:
            request["log"] = value["log"]
        if 'file' in value:
            request['file'] = value['file']
        result = subprocess.run(args, input=json.dumps(request), capture_output=True,
                                encoding="utf-8", errors="replace", timeout=25,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise MonitorError("Não foi possível consultar o diretório. Verifique o SSH e tente novamente.") from exc
    lines = [line for line in result.stdout.split("\n") if line.startswith("HELIXFORGE_EXECUTION_V1:")]
    if result.returncode or len(lines) != 1:
        error = result.stderr.lower()
        code = "permission" if "permission denied" in error else "unavailable"
        raise MonitorError("A leitura remota falhou. Verifique o SSH e a disponibilidade de Python 3 no servidor.", code=code)
    try:
        data = json.loads(lines[0].split(":", 1)[1])
    except ValueError as exc:
        raise MonitorError("Resposta remota inválida.") from exc
    if "error" in data:
        raise MonitorError(data["error"], 400, data.get("code", "partial"))
    data["checked_at"] = datetime.now(timezone.utc).isoformat()
    return data


class QueueMonitor:
    """One in-flight query; cache both successes and errors to bound Slurm calls."""
    def __init__(self, query=query_jobs, clock=time.monotonic):
        self.query, self.clock = query, clock
        self.lock = threading.Lock()
        self.cache = {}

    def get(self, config):
        if not self.lock.acquire(blocking=False):
            raise MonitorError("Uma consulta já está em andamento. Aguarde e atualize novamente.", 429)
        try:
            key = tuple(config.values())
            now = self.clock()
            entry = self.cache.get(key)
            if entry and now - entry[0] < 30:
                value = entry[1]
            else:
                try:
                    value = self.query(config)
                except MonitorError as exc:
                    value = exc
                if len(self.cache) >= 8:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = (self.clock(), value)
            if isinstance(value, MonitorError):
                raise value
            return value
        finally:
            self.lock.release()


class MonitorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, monitor=None):
        super().__init__(address, Handler)
        self.monitor = monitor or QueueMonitor()
        self.executions = QueueMonitor(query=lambda config: query_execution(json.loads(config["request"])))
        self.token = secrets.token_urlsafe(32)
        self.submissions = {}
        self.submission_lock = threading.Lock()
        self.preparations = {}
        self.preparation_lock = threading.Lock()

    def _review(self, kind, value):
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self.preparation_lock:
            self.preparations = {key: item for key, item in self.preparations.items() if now - item[0] < 600}
            if len(self.preparations) >= 16:
                self.preparations.pop(next(iter(self.preparations)))
            self.preparations[token] = (now, kind, value)
        return token

    def _consume_review(self, token, kind):
        if not isinstance(token, str):
            raise MonitorError("Confirmação inválida.", 400, "invalid")
        with self.preparation_lock:
            prepared = self.preparations.pop(token, None)
        if not prepared or time.monotonic() - prepared[0] >= 600 or prepared[1] != kind:
            raise MonitorError("A revisão expirou. Revise a etapa novamente.", 409, "expired")
        return prepared[2]

    def review_clone(self, value):
        if not isinstance(value, dict) or set(value) != {"connection", "clone"}:
            raise MonitorError("Solicitação de clone inválida.", 400, "invalid")
        config = connection_config(value["connection"])
        try:
            clone = PREPARATION.validate_clone(value["clone"])
        except PREPARATION.PlanError as exc:
            raise MonitorError(str(exc), 400, "invalid") from exc
        inspection = remote_preparation(config, {"action":"inspect_clone", "clone":clone})
        response = {"inspection":inspection}
        if clone["mode"] == "new":
            response["review_token"] = self._review("clone", {"config":config, "clone":clone})
        return response

    def create_clone(self, value):
        if not isinstance(value, dict) or set(value) != {"review_token"}:
            raise MonitorError("Confirmação de clone inválida.", 400, "invalid")
        reviewed = self._consume_review(value["review_token"], "clone")
        return remote_preparation(reviewed["config"], {"action":"create_clone", "clone":reviewed["clone"]}, 210)

    def review_preparation(self, value):
        if not isinstance(value, dict) or set(value) != {"connection", "plan"}:
            raise MonitorError("Plano de preparação inválido.", 400, "invalid")
        config = connection_config(value["connection"])
        try:
            generated = PREPARATION.generate_documents(value["plan"])
        except PREPARATION.PlanError as exc:
            raise MonitorError(str(exc), 400, "invalid:" + exc.field) from exc
        plan, documents = generated["plan"], generated["documents"]
        request = {"action":"preflight", "clone":plan["clone"], "project_root":plan["storage"]["project_root"],
                   "inputs":PREPARATION.input_paths(plan), "documents":documents, "runtime":plan["runtime"],
                   "storage":plan["storage"],
                   "integration":plan["integration"] if plan["workflow"] == "integrative" else {}}
        preflight = remote_preparation(config, request)
        token = self._review("documents", {"config":config, "plan":plan, "documents":documents, "request":request})
        return {"review_token":token, "preflight":preflight,
                "documents":[{"path":item["path"], "relative_path":item["relative_path"], "kind":item["kind"], "content":item["content"]} for item in documents]}

    def write_preparation(self, value):
        if not isinstance(value, dict) or set(value) != {"review_token"}:
            raise MonitorError("Confirmação de escrita inválida.", 400, "invalid")
        reviewed = self._consume_review(value["review_token"], "documents")
        request = {**reviewed["request"], "action":"write"}
        result = remote_preparation(reviewed["config"], request)
        result.update({"connection":reviewed["config"], "draft":PREPARATION.submission_from_plan(reviewed["plan"])})
        return result

    def prepare_submission(self, value):
        if not isinstance(value, dict) or set(value) != {"connection", "draft"}:
            raise MonitorError("Solicitação de revisão inválida.", 400, "invalid")
        config = connection_config(value["connection"])
        draft = submission_draft(value["draft"])
        preflight = remote_submission(config, draft, "prepare")
        review_token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self.submission_lock:
            self.submissions = {key: item for key, item in self.submissions.items() if now - item[0] < 600}
            if len(self.submissions) >= 16:
                self.submissions.pop(next(iter(self.submissions)))
            self.submissions[review_token] = (now, config, draft)
        return {"review_token": review_token, "preflight": preflight}

    def submit_execution(self, value):
        if not isinstance(value, dict) or set(value) != {"review_token"} or not isinstance(value["review_token"], str):
            raise MonitorError("Confirmação de submissão inválida.", 400, "invalid")
        with self.submission_lock:
            prepared = self.submissions.pop(value["review_token"], None)
        if not prepared or time.monotonic() - prepared[0] >= 600:
            raise MonitorError("A revisão expirou. Valide a execução novamente.", 409, "expired")
        _created, config, draft = prepared
        result = remote_submission(config, draft, "submit")
        result.update({"connection": config, "draft": draft, "submitted_at": datetime.now(timezone.utc).isoformat()})
        return result


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(35)

    def log_message(self, *_args):
        pass  # Do not log connection details or jobs.

    def allowed_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def send_body(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data: blob:; frame-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed_host():
            return self.send_body(403, {"error": "Host local inválido."})
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/executions.js": ("executions.js", "text/javascript; charset=utf-8"),
                 "/results.js": ("results.js", "text/javascript; charset=utf-8"),
                 "/execution-state.js": ("execution-state.js", "text/javascript; charset=utf-8"),
                 "/new-execution.js": ("new-execution.js", "text/javascript; charset=utf-8"),
                 "/connections.js": ("connections.js", "text/javascript; charset=utf-8"),
                 "/styles.css": ("styles.css", "text/css; charset=utf-8")}
        if self.path not in files:
            return self.send_body(404, {"error": "Recurso não encontrado."})
        name, content_type = files[self.path]
        body = (STATIC / name).read_bytes().replace(b"__SESSION_TOKEN__", self.server.token.encode())
        self.send_body(200, body, content_type)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if (not self.allowed_host()
                or origin not in (None, "http://" + self.headers.get("Host", ""))
                or self.headers.get("X-HelixForge-Token") != self.server.token):
            return self.send_body(403, {"error": "Sessão local inválida. Recarregue a página."})
        if self.path not in ("/api/jobs", "/api/execution", "/api/connection",
                             "/api/submission/prepare", "/api/submission/submit",
                             "/api/clone/review", "/api/clone/create",
                             "/api/preparation/review", "/api/preparation/write"):
            return self.send_body(404, {"error": "Recurso não encontrado."})
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise MonitorError("Envie a configuração em JSON.", 400)
            size = int(self.headers.get("Content-Length", "0"))
            maximum = 2 * 1024 * 1024 if self.path == "/api/preparation/review" else 16384 if self.path in ("/api/submission/prepare", "/api/clone/review") else 4096
            if not 0 < size <= maximum:
                raise MonitorError("Tamanho de configuração inválido.", 400)
            value = json.loads(self.rfile.read(size))
            if self.path == "/api/connection":
                self.send_body(200, {"connection": connection_config(value)})
            elif self.path == "/api/submission/prepare":
                self.send_body(200, self.server.prepare_submission(value))
            elif self.path == "/api/submission/submit":
                self.send_body(200, self.server.submit_execution(value))
            elif self.path == "/api/clone/review":
                self.send_body(200, self.server.review_clone(value))
            elif self.path == "/api/clone/create":
                self.send_body(200, self.server.create_clone(value))
            elif self.path == "/api/preparation/review":
                self.send_body(200, self.server.review_preparation(value))
            elif self.path == "/api/preparation/write":
                self.send_body(200, self.server.write_preparation(value))
            elif self.path == "/api/execution":
                self.send_body(200, self.server.executions.get({"request": json.dumps(value, sort_keys=True)}))
            else:
                self.send_body(200, self.server.monitor.get(connection_config(value)))
        except (ValueError, UnicodeError):
            self.send_body(400, {"error": "Configuração JSON inválida."})
        except MonitorError as exc:
            self.send_body(exc.status, {"error": str(exc), "code": exc.code})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        server = MonitorServer(("127.0.0.1", args.port))
    except OSError as exc:
        parser.exit(1, f"Cannot start the local monitor: {exc}\n")
    print(f"HelixForge Slurm: http://127.0.0.1:{server.server_port}", flush=True)
    print("Monitor and submission UI. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
