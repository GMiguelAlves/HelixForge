"""Bounded, read-only inspection of an explicitly supplied output directory."""
import csv
import io
import json
import os
from pathlib import Path
import stat
import sys


def inspect(directory):
    root = Path(directory).resolve(strict=True)
    uid = os.getuid()
    if not root.is_dir() or root.stat().st_uid != uid:
        raise ValueError("Informe um diretório de saída pertencente ao usuário autenticado.")

    def owned_file(relative):
        path = root / relative
        if not path.exists():
            return None
        path = path.resolve(strict=True)
        if root not in path.parents or path.stat().st_uid != uid or not path.is_file():
            raise ValueError("Um arquivo está fora do diretório ou não pertence ao usuário autenticado.")
        return path

    trace = owned_file("pipeline_info/execution_trace.tsv")
    tasks = []
    modified = None
    if trace:
        # Nonblocking open and fstat also guard against special files replaced during inspection.
        fd = os.open(trace, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != uid:
                raise ValueError("Trace inválido.")
            raw = handle.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("O trace excede o limite de 2 MB desta versão.")
        # An active writer may not have finished its last record yet.
        text = raw.decode("utf-8", errors="replace")
        text = text[:text.rfind("\n") + 1]
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames or not {"name", "status", "native_id"}.issubset(reader.fieldnames):
            raise ValueError("O arquivo não contém um trace compatível do HelixForge.")
        fields = ("task_id", "native_id", "name", "status", "exit", "duration", "realtime", "workdir")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("O trace contém uma linha incompleta. Tente atualizar novamente.")
            tasks.append({key: row.get(key, "")[:2048 if key == "workdir" else 512] for key in fields})
            if len(tasks) > 2000:
                raise ValueError("O trace excede o limite de 2.000 registros desta versão.")
        modified = info.st_mtime
    artifacts = []
    for relative in ("pipeline_info/execution_report.html", "pipeline_info/execution_timeline.html",
                     "rnaseq/rnaseq_run_manifest.json", "chipseq/chipseq_run_manifest.json",
                     "integration/integrative_run_manifest.json"):
        if owned_file(relative):
            artifacts.append(relative)
    return {"directory": str(root), "trace_found": bool(trace), "trace_modified": modified,
            "tasks": tasks, "artifacts": artifacts}


def read_log(directory, selection):
    if not isinstance(selection, dict) or set(selection) != {"task_id", "native_id", "name", "file"}:
        raise ValueError("Seleção de log inválida.")
    if selection["file"] not in (".command.out", ".command.err", ".command.log"):
        raise ValueError("Arquivo de log não permitido.")
    data = inspect(directory)
    matches = [task for task in data["tasks"] if all(task[key] == selection[key] for key in ("task_id", "native_id", "name"))]
    if len(matches) != 1:
        raise ValueError("O processo não corresponde ao trace atual. Atualize os detalhes da execução.")
    workdir = matches[0].get("workdir", "")
    if not workdir.startswith("/"):
        raise ValueError("O trace não informa um diretório de trabalho absoluto para este processo.")
    root = Path(workdir).resolve(strict=True)
    uid = os.getuid()
    if not root.is_dir() or root.stat().st_uid != uid:
        raise ValueError("O diretório do processo não pertence ao usuário autenticado.")
    path = (root / selection["file"]).resolve(strict=True)
    if path.parent != root:
        raise ValueError("O log aponta para fora do diretório do processo.")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid:
            raise ValueError("O log deve ser um arquivo regular do usuário autenticado.")
        start = max(0, info.st_size - 65536)
        handle.seek(start)
        raw = handle.read(65536)
    if start and b"\n" in raw:
        raw = raw.split(b"\n", 1)[1]
    lines = raw.decode("utf-8", errors="replace").splitlines(keepends=True)
    return {"content": "".join(lines[-400:]), "truncated": bool(start or len(lines) > 400),
            "path": str(path), "size": info.st_size, "modified": info.st_mtime}


if __name__ == "__main__":
    request = {}
    try:
        request = json.loads(sys.stdin.read(8192))
        result = read_log(request["directory"], request["log"]) if "log" in request else inspect(request["directory"])
    except FileNotFoundError:
        result = {"error": "Log, trace ou diretório não encontrado. Os arquivos podem ainda não existir ou ter sido removidos."}
    except (ValueError, OSError, KeyError) as exc:
        result = {"error": str(exc) if isinstance(exc, ValueError) else "Diretório indisponível ou sem permissão de leitura."}
    print("HELIXFORGE_EXECUTION_V1:" + json.dumps(result))
