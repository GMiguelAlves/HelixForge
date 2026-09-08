#!/usr/bin/env python3
"""Local, single-user Slurm monitor. Python 3.10+ and an existing SSH setup."""

import argparse
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import threading
import time


STATIC = Path(__file__).parent / "static"
SEPARATOR = "\x1f"
MARKER = "HELIXFORGE_SLURM_V1:"
FIELDS = ("id", "name", "state", "elapsed", "time_limit", "nodes", "cpus",
          "memory", "partition", "reason", "submitted", "start")
FORMAT = SEPARATOR.join(("%i", "%j", "%T", "%M", "%l", "%D", "%C",
                         "%m", "%P", "%R", "%V", "%S"))
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


class MonitorError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


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


def query_execution(value):
    if not isinstance(value, dict) or set(value) != {"connection", "directory"}:
        raise MonitorError("Cadastro de execução inválido.", 400)
    config = connection_config(value["connection"])
    directory = value["directory"]
    if (not isinstance(directory, str) or not directory.startswith("/") or len(directory) > 2048
            or any(ord(char) < 32 for char in directory)):
        raise MonitorError("Informe o caminho absoluto do diretório de saída no servidor.", 400)
    script = (Path(__file__).parent / "probe.py").read_bytes()
    command = "import base64;exec(base64.b64decode(" + repr(base64.b64encode(script).decode()) + "))"
    args = ssh_arguments(config)[:-1] + ["python3 -c " + shlex.quote(command)]
    try:
        result = subprocess.run(args, input=json.dumps({"directory": directory}), capture_output=True,
                                encoding="utf-8", errors="replace", timeout=25,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise MonitorError("Não foi possível consultar o diretório. Verifique o SSH e tente novamente.") from exc
    lines = [line for line in result.stdout.split("\n") if line.startswith("HELIXFORGE_EXECUTION_V1:")]
    if result.returncode or len(lines) != 1:
        raise MonitorError("A leitura remota falhou. Verifique o SSH e a disponibilidade de Python 3 no servidor.")
    try:
        data = json.loads(lines[0].split(":", 1)[1])
    except ValueError as exc:
        raise MonitorError("Resposta remota inválida.") from exc
    if "error" in data:
        raise MonitorError(data["error"], 400)
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
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed_host():
            return self.send_body(403, {"error": "Host local inválido."})
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/executions.js": ("executions.js", "text/javascript; charset=utf-8"),
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
        if self.path not in ("/api/jobs", "/api/execution"):
            return self.send_body(404, {"error": "Recurso não encontrado."})
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise MonitorError("Envie a configuração em JSON.", 400)
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4096:
                raise MonitorError("Tamanho de configuração inválido.", 400)
            value = json.loads(self.rfile.read(size))
            if self.path == "/api/execution":
                self.send_body(200, self.server.executions.get({"request": json.dumps(value, sort_keys=True)}))
            else:
                self.send_body(200, self.server.monitor.get(connection_config(value)))
        except (ValueError, UnicodeError):
            self.send_body(400, {"error": "Configuração JSON inválida."})
        except MonitorError as exc:
            self.send_body(exc.status, {"error": str(exc)})


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
    print("Read-only monitor. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
