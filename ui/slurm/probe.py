"""Bounded, read-only inspection of an explicitly supplied output directory."""
import csv
import io
import json
import os
from pathlib import Path
import stat
import sys
from contextlib import contextmanager
from html import escape
from html.parser import HTMLParser


TEXT_LIMIT = 65536
PREVIEW_LIMIT = 4 * 1024 * 1024
EXTENSIONS = {'.html', '.svg', '.json', '.tsv', '.csv', '.txt', '.md', '.log', '.out', '.err', '.exit', '.done', '.yml'}


class StaticReport(HTMLParser):
    """Conservative static HTML: no URLs, scripts, navigation or embedded documents."""
    tags = set('html head body title style div span p pre code h1 h2 h3 h4 h5 h6 table thead tbody tfoot tr th td caption colgroup col ul ol li dl dt dd strong em b i small hr br section article header footer main aside details summary blockquote'.split())
    attributes = {'class', 'id', 'style', 'title', 'colspan', 'rowspan'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.suppressed = None

    def handle_starttag(self, tag, attrs):
        if self.suppressed:
            return
        if tag in ('script', 'iframe', 'object', 'svg', 'math', 'template'):
            self.suppressed = tag
        elif tag in self.tags:
            safe = ''.join(' ' + key + '="' + escape(value or '', quote=True) + '"'
                           for key, value in attrs if key in self.attributes)
            self.output.append('<' + tag + safe + '>')

    def handle_endtag(self, tag):
        if self.suppressed:
            if tag == self.suppressed:
                self.suppressed = None
        elif tag in self.tags:
            self.output.append('</' + tag + '>')

    def handle_data(self, data):
        if not self.suppressed:
            self.output.append(escape(data))


def static_report(content):
    parser = StaticReport()
    parser.feed(content)
    parser.close()
    return ''.join(parser.output)


def validate_file(selection):
    if (not isinstance(selection, dict) or set(selection) != {'path', 'offset', 'preview'}
            or not isinstance(selection['path'], str) or len(selection['path']) > 2048
            or any(ord(c) < 32 for c in selection['path'])
            or '\\' in selection['path']
            or any(part in ('', '.', '..') for part in selection['path'].split('/'))
            or type(selection['offset']) is not int or not 0 <= selection['offset'] <= 2**53 - 1
            or type(selection['preview']) is not bool):
        raise ValueError('Seleção de arquivo inválida.')


@contextmanager
def open_result(directory, relative):
    """Anchor every component to an open directory; never follow symlinks."""
    validate_file({'path': relative, 'offset': 0, 'preview': False})
    root = Path(directory).resolve(strict=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise ValueError('O diretório não pertence ao usuário autenticado.')
        parts = relative.split('/')
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError('O resultado deve ser um arquivo regular do usuário autenticado.')
            yield handle, info
    finally:
        os.close(fd)


def catalog(root):
    artifacts, visited, truncated = [], 0, False
    # Never descend into task work/cache trees, even when a launch directory is registered.
    allowed = {'results', 'pipeline_info', 'integration', 'rnaseq', 'chipseq',
               'execution', 'evaluation', 'manifests', 'failed_attempts',
               'contracts', 'reentry', 'real', 'synthetic'}
    for base, dirs, files in os.walk(root, followlinks=False):
        visited += 1
        if visited > 5000:
            return artifacts, True
        depth = len(Path(base).relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d != 'work'
                         and not (Path(base) / d).is_symlink() and (depth > 0 or d in allowed))
        if depth >= 8:
            truncated |= bool(dirs)
            dirs[:] = []
        for name in sorted(files):
            visited += 1
            if visited > 5000 or len(artifacts) >= 1000:
                return artifacts, True
            path = Path(base) / name
            if path.suffix.lower() not in EXTENSIONS and name != 'SHA256SUMS':
                continue
            if name.startswith('.') and name != '.nextflow.log':
                continue
            try:
                info = path.lstat()
                if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid():
                    artifacts.append(str(path.relative_to(root)).replace(os.sep, '/'))
            except OSError:
                continue
    return artifacts, truncated


def read_file(directory, selection):
    validate_file(selection)
    path = selection['path']
    root = Path(directory).resolve(strict=True)
    paths, _ = catalog(root)
    if path not in paths:
        raise ValueError('Arquivo não listado nos resultados. Atualize a execução.')
    suffix = Path(path).suffix.lower()
    with open_result(root, path) as (handle, info):
        preview = selection['preview']
        if preview and (suffix not in ('.html', '.svg') or info.st_size > PREVIEW_LIMIT):
            raise ValueError('Prévia disponível apenas para HTML/SVG de até 4 MiB. Use a leitura de texto.')
        offset = min(selection['offset'], info.st_size)
        if preview:
            offset = 0
        handle.seek(offset)
        raw = handle.read(PREVIEW_LIMIT + 1 if preview else TEXT_LIMIT)
        if preview and len(raw) > PREVIEW_LIMIT:
            raise ValueError('Arquivo cresceu além do limite de prévia. Tente a leitura de texto.')
    content = raw.decode('utf-8', errors='replace')
    if preview and suffix == '.html':
        content = static_report(content)
    return {'path': path, 'size': info.st_size, 'modified': info.st_mtime,
            'content': content, 'offset': offset,
            'next_offset': offset + len(raw), 'truncated': offset + len(raw) < info.st_size,
            'kind': suffix[1:] if preview else 'text'}


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

    trace = next((path for name in ('pipeline_info/execution_trace.tsv',
                  'results/pipeline_info/execution_trace.tsv', 'execution/trace.tsv', 'trace.tsv')
                  if (path := owned_file(name))), None)
    tasks = []
    modified = None
    if trace:
        # Nonblocking open and fstat also guard against special files replaced during inspection.
        with open_result(root, str(trace.relative_to(root))) as (handle, info):
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
    artifacts, truncated = catalog(root)
    # Preserve the existing artifacts string-array contract; omit the trace already shown as tasks.
    artifacts = [path for path in artifacts if not trace or root / path != trace]
    declarations = []
    inspected_manifests = 0
    for path in artifacts:
        if (path.startswith('failed_attempts/') or not path.endswith(('run_manifest.json', 'report_manifest.json'))
                or inspected_manifests >= 20):
            continue
        inspected_manifests += 1
        try:
            with open_result(root, path) as (handle, info):
                if info.st_size > TEXT_LIMIT:
                    continue
                raw = handle.read(TEXT_LIMIT + 1)
            manifest = json.loads(raw)
            if isinstance(manifest, dict) and isinstance(manifest.get('status'), str):
                declarations.append({'path': path, 'status': manifest['status'][:128]})
        except (OSError, ValueError):
            # A partial or malformed manifest must not hide the rest of the execution.
            continue
    return {"directory": str(root), "trace_found": bool(trace), "trace_modified": modified,
            "trace_path": str(trace.relative_to(root)) if trace else None,
            "tasks": tasks, "artifacts": artifacts, "artifacts_truncated": truncated,
            "declarations": declarations}


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
        if 'file' in request:
            result = read_file(request['directory'], request['file'])
        else:
            result = read_log(request["directory"], request["log"]) if "log" in request else inspect(request["directory"])
    except FileNotFoundError:
        result = {"error": "Log, trace ou diretório não encontrado. Os arquivos podem ainda não existir ou ter sido removidos."}
    except (ValueError, OSError, KeyError) as exc:
        result = {"error": str(exc) if isinstance(exc, ValueError) else "Diretório indisponível ou sem permissão de leitura."}
    print("HELIXFORGE_EXECUTION_V1:" + json.dumps(result))
