"use strict";
const resultsViewer = (() => {
  let run = null, key = null, page = 0, request = 0, controller = null;
  let file = null, offset = 0, next = 0, size = 0;
  let previewUrl = null;
  const policy = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'";
  const groupLabels = {current:"Execução atual", archived:"Tentativas arquivadas", logs:"Logs", manifests:"Manifestos e proveniência", evaluation:"Avaliação", reports:"Relatórios", figures:"Figuras", tables:"Tabelas e outros textos"};
  const issueLabels = {missing:"Arquivo ausente", permission:"Sem permissão", partial:"Leitura parcial", unavailable:"Origem indisponível"};
  function clear() {
    request++; controller?.abort();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    file = null; offset = 0; next = 0; size = 0;
    $("result-preview").replaceChildren();
    $("result-status").textContent = "Selecione um arquivo para ler.";
    $("result-title").textContent = "Visualização";
    for (const id of ["result-prev", "result-next", "result-tail"]) $(id).disabled = true;
  }
  function category(path) {
    if (/\.(log|out|err)$/.test(path) || /nextflow\.log\.\d+$/.test(path)) return "logs";
    if (/\.html$/.test(path)) return "reports";
    if (/\.(svg|png|jpe?g|pdf)$/.test(path)) return "figures";
    if (/\.json$/.test(path) || /manifest|provenance|sha256sums/.test(path)) return "manifests";
    return "tables";
  }
  function details() {
    if (Array.isArray(run.data.artifact_details)) return run.data.artifact_details;
    return run.data.artifacts.map((path) => ({path, group:path.startsWith("failed_attempts/") ? "archived" : category(path), kind_group:category(path), archived:path.startsWith("failed_attempts/")}));
  }
  function render() {
    if (!run) return;
    const query = $("result-search").value.trim().toLocaleLowerCase();
    const kind = $("result-filter").value;
    const records = details().filter((item) => item.path.toLocaleLowerCase().includes(query) &&
      (kind === "all" || (kind === "current" && !item.archived) || item.group === kind || item.kind_group === kind));
    const order = ["current", "logs", "manifests", "evaluation", "reports", "figures", "tables", "archived"];
    records.sort((a, b) => order.indexOf(a.archived ? "archived" : a.group) - order.indexOf(b.archived ? "archived" : b.group) || a.path.localeCompare(b.path));
    page = Math.min(page, Math.max(0, Math.ceil(records.length / 20) - 1));
    $("execution-artifacts").replaceChildren();
    let previousGroup = null;
    for (const item of records.slice(page * 20, page * 20 + 20)) {
      const path = item.path;
      const group = item.archived ? "archived" : item.group;
      if (group !== previousGroup) {
        $("execution-artifacts").append(element("h3", groupLabels[group] || group, "result-group"));
        previousGroup = group;
      }
      const row = element("div", "", "run-file");
      const title = element("code", path);
      if (item.size != null) title.append(element("small", ` · ${item.size} bytes`));
      const actions = element("div", "", "form-actions");
      const read = element("button", "Ler texto");
      read.addEventListener("click", () => readFile(path));
      if (!/\.(png|jpe?g|pdf)$/i.test(path)) actions.append(read);
      if (/\.(html|svg|png|jpe?g|pdf)$/i.test(path)) {
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
    $("result-count").textContent = `${records.length} arquivos · página ${page + 1}${run.data.artifacts_truncated ? " · inventário parcial (limite atingido)" : ""}`;
    if (!records.length) $("execution-artifacts").append(element("p", "Nenhum arquivo corresponde ao filtro. Atualize a leitura se os resultados ainda estão sendo gerados."));
    $("result-page-prev").disabled = !page;
    $("result-page-next").disabled = (page + 1) * 20 >= records.length;
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
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
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
      if (!response.ok) { const problem = new Error(data.error || "Falha na leitura do arquivo."); problem.code = data.code; throw problem; }
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
      } else if (["png", "jpg", "jpeg", "pdf"].includes(data.kind) && data.encoding === "base64") {
        const bytes = Uint8Array.from(atob(data.content), (char) => char.charCodeAt(0));
        previewUrl = URL.createObjectURL(new Blob([bytes], {type:data.mime}));
        if (data.kind === "pdf") {
          const frame = document.createElement("iframe");
          frame.title = `PDF ${path}`; frame.setAttribute("sandbox", ""); frame.src = previewUrl;
          $("result-preview").append(frame);
        } else {
          const img = document.createElement("img"); img.alt = path; img.src = previewUrl;
          $("result-preview").append(img);
        }
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
      if (id === request) $("result-status").textContent = error.name === "AbortError" ? "A leitura excedeu o tempo limite. Tente novamente." : `${issueLabels[error.code] || "Leitura indisponível"}: ${error.message} O inventário anterior foi mantido; atualize a execução para confirmar a disponibilidade.`;
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
