"use strict";
const resultsViewer = (() => {
  let run = null, key = null, page = 0, request = 0, controller = null;
  let file = null, offset = 0, next = 0, size = 0;
  const policy = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'";
  function clear() {
    request++; controller?.abort();
    file = null; offset = 0; next = 0; size = 0;
    $("result-preview").replaceChildren();
    $("result-status").textContent = "Selecione um arquivo para ler.";
    $("result-title").textContent = "Visualização";
    for (const id of ["result-prev", "result-next", "result-tail"]) $(id).disabled = true;
  }
  function category(path) {
    if (/\.(log|out|err)$/.test(path)) return "logs";
    if (/\.html$/.test(path)) return "reports";
    if (/\.svg$/.test(path)) return "figures";
    if (/\.json$/.test(path)) return "manifests";
    return "tables";
  }
  function render() {
    if (!run) return;
    const query = $("result-search").value.trim().toLocaleLowerCase();
    const kind = $("result-filter").value;
    const paths = run.data.artifacts.filter((path) => path.toLocaleLowerCase().includes(query) && (kind === "all" || category(path) === kind));
    page = Math.min(page, Math.max(0, Math.ceil(paths.length / 20) - 1));
    $("execution-artifacts").replaceChildren();
    for (const path of paths.slice(page * 20, page * 20 + 20)) {
      const row = element("div", "", "run-file");
      const title = element("code", path);
      const actions = element("div", "", "form-actions");
      const read = element("button", "Ler texto");
      read.addEventListener("click", () => readFile(path));
      actions.append(read);
      if (/\.(html|svg)$/.test(path)) {
        const preview = element("button", "Visualizar");
        preview.addEventListener("click", () => readFile(path, 0, true));
        actions.append(preview);
      }
      const copy = element("button", "Copiar caminho");
      copy.addEventListener("click", async () => {
        const absolute = run.data.directory.replace(/\/$/, "") + "/" + path;
        try { await navigator.clipboard.writeText(absolute); $("run-copy-status").textContent = "Caminho copiado."; }
        catch { $("run-copy-status").textContent = absolute; }
      });
      row.append(title, actions); actions.append(copy); $("execution-artifacts").append(row);
    }
    $("result-count").textContent = `${paths.length} arquivos · página ${page + 1}${run.data.artifacts_truncated ? " · inventário parcial (limite atingido)" : ""}`;
    if (!paths.length) $("execution-artifacts").append(element("p", "Nenhum arquivo corresponde ao filtro. Atualize a leitura se os resultados ainda estão sendo gerados."));
    $("result-page-prev").disabled = !page;
    $("result-page-next").disabled = (page + 1) * 20 >= paths.length;
  }
  function staticReport(content) {
    // The backend allowlists static markup. Never parse untrusted HTML in the parent document.
    return `<!doctype html><meta http-equiv="Content-Security-Policy" content="${policy}">` + content;
  }
  async function readFile(path, start = 0, preview = false) {
    if (!run) return;
    const selectedRun = run;
    const id = ++request;
    controller?.abort(); controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    $("result-preview").replaceChildren();
    $("result-title").textContent = path;
    $("result-status").textContent = "Lendo arquivo…";
    for (const button of ["result-prev", "result-next", "result-tail"]) $(button).disabled = true;
    try {
      const response = await fetch("/api/execution", {method:"POST", headers:{"Content-Type":"application/json", "X-HelixForge-Token":token},
        body:JSON.stringify({connection:run.connection, directory:run.data.directory, file:{path, offset:start, preview}}), signal:controller.signal});
      const data = await response.json();
      if (id !== request || run !== selectedRun) return;
      if (!response.ok) throw new Error(data.error || "Falha na leitura do arquivo.");
      file = path; offset = data.offset; next = data.next_offset; size = data.size;
      if (data.kind === "html") {
        const frame = document.createElement("iframe");
        frame.title = `Prévia estática de ${path}`; frame.setAttribute("sandbox", "");
        frame.referrerPolicy = "no-referrer"; frame.srcdoc = staticReport(data.content);
        $("result-preview").append(frame);
      } else if (data.kind === "svg") {
        const img = document.createElement("img"); img.alt = path;
        img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(data.content);
        $("result-preview").append(img);
      } else {
        const text = element("pre", data.content || "Arquivo vazio."); text.tabIndex = 0;
        $("result-preview").append(text);
      }
      $("result-status").textContent = `${data.size} bytes · trecho ${offset}–${next}${data.truncated ? " · há mais conteúdo" : " · fim do arquivo"}${preview ? " · prévia estática; scripts, links e recursos externos desativados" : " · busca disponível no trecho exibido"}`;
      $("result-prev").disabled = preview || !offset;
      $("result-next").disabled = preview || !data.truncated;
      $("result-tail").disabled = preview || size <= 65536;
      $("result-title").focus({preventScroll:true});
    } catch (error) {
      if (id === request) $("result-status").textContent = error.name === "AbortError" ? "A leitura excedeu o tempo limite. Tente novamente." : error.message;
    } finally { clearTimeout(timeout); }
  }
  for (const id of ["result-search", "result-filter"]) $(id).addEventListener(id.endsWith("search") ? "input" : "change", () => { page = 0; render(); });
  $("result-page-prev").addEventListener("click", () => { page--; render(); });
  $("result-page-next").addEventListener("click", () => { page++; render(); });
  $("result-prev").addEventListener("click", () => readFile(file, Math.max(0, offset - 65536)));
  $("result-next").addEventListener("click", () => readFile(file, next));
  $("result-tail").addEventListener("click", () => readFile(file, Math.max(0, size - 65536)));
  window.addEventListener("hashchange", () => { request++; controller?.abort(); });
  return {bind(value) {
    run = value;
    const current = value ? value.id + ":" + value.data.checked_at : null;
    if (current !== key) { key = current; page = 0; clear(); }
    render();
  }};
})();
