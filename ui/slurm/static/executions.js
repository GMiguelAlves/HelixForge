"use strict";
(() => {
  const key = "helixforge.executions.v1";
  const workflows = { chipseq: "ChIP-seq", rnaseq: "RNA-seq", integrative: "Integrativo", all: "Todos" };
  let runs = [];
  let selected = null;
  let reading = false;
  let detailId = null;
  let detailSection = "summary";
  let taskPage = 0;
  let taskIndex = null;
  let logRequest = 0;
  let logController = null;
  let logRun = null;
  let removeCandidate = null;
  let removedRun = null;
  let removeTimer = null;
  let progressTimer = null;
  const availabilityLabels = {available:"Disponível", failed:"Falha indicada", current:"Atual", stale:"Snapshot preservado", partial:"Parcial", missing:"Ausente", permission:"Sem permissão", unavailable:"Indisponível", identity:"Identidade alterada"};
  const healthLabels = {trace:"Trace", exit_logs:"Saída e logs", manifests:"Manifestos", files:"Arquivos"};
  function normalizeRun(run) {
    run.history = Array.isArray(run.history) ? run.history : [];
    run.availability = run.availability || {state:run.data.overall_state === "partial" ? "partial" : "current", checked_at:run.data.checked_at};
    return run;
  }
  function validRuns(value) {
    return Array.isArray(value) && value.length <= 200 && !value.some((run) => typeof run.id !== "string" || !run.id || run.id.length > 128 ||
      typeof run.name !== "string" || run.name.length > 120 || !workflows[run.workflow] ||
      typeof run.connection?.host !== "string" || run.connection.host.length > 253 ||
      typeof run.data?.directory !== "string" || run.data.directory.length > 2048 ||
      !Array.isArray(run.data.tasks) || run.data.tasks.length > 2000 || !Array.isArray(run.data.artifacts) || run.data.artifacts.length > 1000 ||
      run.data.artifacts.some((path) => typeof path !== "string" || path.length > 2048));
  }
  function snapshotSummary(data, state="current", reason="") {
    return {checked_at:data.checked_at, state, reason, tasks:data.tasks.length, artifacts:data.artifacts.length,
            health:data.health || null};
  }
  function history(run, entry) { return [entry, ...(run.history || [])].slice(0, 10); }
  function clearLog() {
    logRequest++; logController?.abort(); logController = null;
    $("log-content").textContent = "Nenhum log carregado.";
    $("log-path").textContent = "";
    $("log-status").textContent = "Selecione um processo e leia o log.";
    $("log-read").textContent = "Ler log ↻";
    $("log-read").disabled = !$("log-task").options.length;
  }
  const error = (message) => {
    $("execution-error").textContent = message;
    $("execution-error").hidden = !message;
    $("run-error").textContent = message;
    $("run-error").hidden = !message;
  };
  const persist = (next) => {
    try { localStorage.setItem(key, JSON.stringify(next)); }
    catch { throw new Error("Não foi possível salvar o histórico. Verifique o espaço e as permissões de armazenamento do navegador."); }
    runs = next;
  };
  window.registerSubmittedExecution = (submission) => {
    const checkedAt = submission.submitted_at || new Date().toISOString();
    const data = {directory:submission.directory, checked_at:checkedAt, trace_found:false, trace_path:"", trace_modified:null,
      tasks:[], artifacts:[], artifact_details:[], declarations:[], overall_state:"partial",
      health:{trace:{state:"missing"}, exit_logs:{state:"missing"}, manifests:{state:"missing"}, files:{state:"missing"}}};
    const run = normalizeRun({id:crypto.randomUUID(), name:submission.draft.name, workflow:submission.draft.workflow,
      connection:submission.connection, created_at:checkedAt, data, availability:{state:"partial", checked_at:checkedAt}, history:[],
      submission:{job_id:submission.job_id, submitted_at:checkedAt, launch:submission.launch}});
    persist([run, ...runs]); selected = run.id; detailId = run.id;
    location.hash = `execution/${run.id}/summary`; render();
  };
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "[]");
    if (!validRuns(saved)) throw new Error();
    runs = saved.map(normalizeRun);
    selected = runs[0]?.id;
    if (runs.length) {
      if (!$("host").value) {
        for (const id of ["host", "user", "port", "control_path"]) $(id).value = runs[0].connection[id] || "";
      }
      $("connection-settings").open = false;
    }
  } catch { error("O histórico salvo não pôde ser lido. Nenhum cadastro foi alterado."); }

  function showScreen(screen) {
    $("executions-screen").hidden = screen !== "executions";
    $("jobs-screen").hidden = screen !== "jobs";
    $("execution-screen").hidden = screen !== "execution";
    $("new-execution-screen").hidden = screen !== "new";
    $("connections-screen").hidden = screen !== "connections";
    for (const name of ["executions", "new", "jobs", "connections"]) {
      if (name === screen || (name === "executions" && screen === "execution")) $("nav-" + name).setAttribute("aria-current", "page");
      else $("nav-" + name).removeAttribute("aria-current");
    }
  }
  $("nav-executions").addEventListener("click", () => { location.hash = "executions"; });
  $("nav-new").addEventListener("click", () => { location.hash = "new"; });
  $("nav-jobs").addEventListener("click", () => { location.hash = "jobs"; });
  $("nav-connections").addEventListener("click", () => { location.hash = "connections"; });
  function route() {
    const parts = location.hash.slice(1).split("/");
    const previous = detailId;
    detailId = parts[0] === "execution" && runs.some((run) => run.id === parts[1]) ? parts[1] : null;
    detailSection = ["summary", "processes", "logs", "files"].includes(parts[2]) ? parts[2] : "summary";
    if (previous !== detailId) {
      taskPage = 0; taskIndex = null;
      $("run-task-search").value = ""; $("run-task-state").value = "all";
    }
    showScreen(detailId ? "execution" : ["jobs", "new", "connections"].includes(parts[0]) ? parts[0] : "executions");
    for (const section of ["summary", "processes", "logs", "files"]) {
      $("run-panel-" + section).hidden = section !== detailSection;
      if (section === detailSection) $("run-tab-" + section).setAttribute("aria-current", "page");
      else $("run-tab-" + section).removeAttribute("aria-current");
    }
    render();
    if (detailId && previous !== detailId) $("run-title").focus({preventScroll:true});
  }
  window.addEventListener("hashchange", route);
  for (const section of ["summary", "processes", "logs", "files"]) $("run-tab-" + section).addEventListener("click", () => {
    location.hash = `execution/${detailId}/${section}`;
  });
  $("open-execution").addEventListener("click", () => { if (selected) location.hash = `execution/${selected}/summary`; });
  const date = (value) => value ? new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
  const traceLabel = (data) => !data.trace_found ? "Sem trace" : data.tasks.some((task) => task.status === "FAILED") ? "Falhas registradas" : `${data.tasks.length} registros`;
  function scheduleProgressRefresh(run) {
    clearTimeout(progressTimer);
    if (!run?.submission || !detailId || reading || document.hidden) return;
    const terminal = run.data.tasks.length && run.data.tasks.every((task) => ["COMPLETED", "CACHED", "FAILED", "ABORTED", "CANCELLED"].includes(task.status));
    if (!terminal) progressTimer = setTimeout(() => $("update-execution").click(), 30000);
  }

  function render() {
    const query = $("execution-search").value.trim().toLocaleLowerCase();
    const filter = $("execution-filter").value;
    const visible = runs.filter((run) => (filter === "all" || run.workflow === filter) &&
      [run.name, workflows[run.workflow], run.connection.host].some((text) => text.toLocaleLowerCase().includes(query)));
    if (!visible.some((run) => run.id === selected)) selected = visible[0]?.id;
    $("execution-rows").replaceChildren();
    for (const run of visible) {
      const row = element("tr", "", run.id === selected ? "selected" : "");
      const name = element("td", "");
      const button = element("button", run.name, "job-select");
      button.setAttribute("aria-pressed", String(run.id === selected));
      button.addEventListener("click", () => { selected = run.id; location.hash = `execution/${run.id}/summary`; });
      name.append(button, element("small", `${workflows[run.workflow]} · ${run.connection.host}`));
      const state = run.availability?.state === "stale" ? `${traceLabel(run.data)} · stale (${availabilityLabels[run.availability.reason] || run.availability.reason})` : traceLabel(run.data);
      row.append(name, element("td", state), element("td", date(run.data.checked_at)));
      $("execution-rows").append(row);
    }
    $("execution-table").hidden = !visible.length;
    $("execution-empty").hidden = Boolean(visible.length);
    $("execution-empty").replaceChildren(element("h2", runs.length ? "Nenhuma execução corresponde ao filtro" : "Nenhuma execução registrada"),
      element("p", runs.length ? "Tente outro nome, servidor ou workflow." : "Registre o diretório de saída de uma análise para consultar seus processos e arquivos."));
    $("execution-count").textContent = `${visible.length} de ${runs.length} execuções`;
    const run = runs.find((item) => item.id === (detailId || selected));
    $("execution-placeholder").hidden = Boolean(run);
    $("execution-detail").hidden = !run;
    if (!run) { resultsViewer.bind(null); return; }
    const data = run.data;
    const logKey = run.id + ":" + data.checked_at;
    if (logRun !== logKey) {
      logRun = logKey;
      $("log-task").replaceChildren(...data.tasks.map((task, index) => {
        const option = element("option", `${task.name} · ${task.native_id || task.task_id || "sem ID Slurm"}`);
        option.value = String(index); return option;
      }));
      clearLog();
      if (!data.tasks.length) $("log-status").textContent = "Nenhum processo no trace. Atualize a execução para consultar os registros disponíveis.";
    }
    $("run-title").textContent = run.name;
    $("run-breadcrumb-name").textContent = run.name;
    $("run-subtitle").textContent = `${workflows[run.workflow]} / ${run.connection.host}`;
    const stale = run.availability?.state === "stale";
    $("run-read-time").textContent = `Último snapshot válido: ${date(data.checked_at)} · dados salvos neste navegador`;
    $("execution-detail-title").textContent = run.name;
    $("execution-note").textContent = stale ? `Snapshot stale preservado. A consulta mais recente indicou: ${availabilityLabels[run.availability.reason] || run.availability.reason}.` : "Estado final da análise não confirmado. Dados da última leitura.";
    $("execution-info").replaceChildren();
    const completed = data.tasks.filter((task) => ["COMPLETED", "CACHED"].includes(task.status)).length;
    const progress = data.tasks.length ? Math.round(completed * 100 / data.tasks.length) : 0;
    $("run-progress").value = progress;
    $("run-progress-note").textContent = data.tasks.length ? `${completed} de ${data.tasks.length} processos registrados concluídos ou em cache (${progress}%).` :
      (run.submission ? `Job coordenador ${run.submission.job_id} enviado; aguardando o primeiro trace do Nextflow.` : "Aguardando registros no trace.");
    const fields = { Workflow: workflows[run.workflow], Servidor: run.connection.host,
      "Job coordenador": run.submission?.job_id || "—",
      "Diretório": data.directory, "Registrada em": date(run.created_at), "Última leitura": date(data.checked_at),
      "Trace alterado": date(data.trace_modified && data.trace_modified * 1000),
      "Processos": String(data.tasks.length), "Concluídos / cache": String(completed),
      "Falhas no trace": String(data.tasks.filter((task) => task.status === "FAILED").length) };
    for (const [label, value] of Object.entries(fields)) $("execution-info").append(element("dt", label), element("dd", value));
    for (const declaration of data.declarations || []) {
      $("execution-info").append(element("dt", "Estado declarado no manifesto"), element("dd", `${declaration.status} · ${declaration.path}`));
    }
    $("snapshot-history").replaceChildren();
    const snapshots = [snapshotSummary(data, run.availability?.state || "current", run.availability?.reason || ""), ...(run.history || [])];
    for (const item of snapshots.slice(0, 10)) {
      const line = element("p", `${date(item.checked_at)} · ${availabilityLabels[item.state] || item.state}${item.reason ? ` (${availabilityLabels[item.reason] || item.reason})` : ""} · ${item.tasks} processos · ${item.artifacts} arquivos`);
      $("snapshot-history").append(line);
    }
    $("execution-preview").replaceChildren();
    for (const [label, value] of Object.entries({Workflow: workflows[run.workflow], Servidor:run.connection.host, Processos: String(data.tasks.length), "Última leitura":date(data.checked_at)})) $("execution-preview").append(element("dt", label), element("dd", value));
    $("run-overall-status").textContent = stale ? "Snapshot preservado" : data.overall_state === "failed" ? "Falha indicada" : data.overall_state === "partial" ? "Leitura parcial" : "Disponível";
    $("run-health").replaceChildren();
    const health = data.health || {trace:{state:data.trace_found ? "available" : "missing"}, files:{state:data.artifacts.length ? "available" : "missing"}};
    for (const [component, value] of Object.entries(health)) {
      const line = element("div", "");
      line.append(element("strong", availabilityLabels[value.state] || value.state), element("span", healthLabels[component] || component));
      $("run-health").append(line);
    }
    $("run-trace-status").textContent = traceLabel(data);
    $("run-counts").replaceChildren();
    for (const [label, count] of [["Concluídos", data.tasks.filter((task) => task.status === "COMPLETED").length], ["Em cache", data.tasks.filter((task) => task.status === "CACHED").length], ["Falhas", data.tasks.filter((task) => task.status === "FAILED").length]]) {
      const line = element("div", ""); line.append(element("strong", String(count)), element("span", label)); $("run-counts").append(line);
    }
    $("execution-trace-note").textContent = data.trace_found ? `Registros de ${data.trace_path || "pipeline_info/execution_trace.tsv"}. Uma nova execução no mesmo diretório pode substituir esse arquivo.` : "Trace ainda não encontrado nos caminhos suportados. O cadastro foi mantido para consultas posteriores.";
    renderTasks(data);
    resultsViewer.bind(run);
    scheduleProgressRefresh(run);
  }

  function renderTasks(data) {
    const query = $("run-task-search").value.trim().toLocaleLowerCase();
    const state = $("run-task-state").value;
    const filtered = data.tasks.map((task, index) => ({task, index})).filter(({task}) =>
      [task.name, task.native_id || ""].some((value) => value.toLocaleLowerCase().includes(query)) &&
      (state === "all" || (state === "other" ? !["COMPLETED", "CACHED", "FAILED"].includes(task.status) : task.status === state)));
    taskPage = Math.min(taskPage, Math.max(0, Math.ceil(filtered.length / 25) - 1));
    const page = filtered.slice(taskPage * 25, (taskPage + 1) * 25);
    if (!page.some(({index}) => index === taskIndex)) taskIndex = page[0]?.index;
    $("execution-tasks").replaceChildren();
    for (const {task, index} of page) {
      const row = element("tr", "", index === taskIndex ? "selected" : "");
      const name = element("td", ""); const select = element("button", task.name, "job-select");
      select.setAttribute("aria-pressed", String(index === taskIndex));
      select.addEventListener("click", () => { taskIndex = index; renderTasks(data); });
      name.append(select);
      row.append(name, element("td", task.native_id || "—"), element("td", task.status === "CACHED" ? "Em cache" : labels[task.status] || task.status), element("td", task.duration || "—"));
      $("execution-tasks").append(row);
    }
    $("run-tasks-empty").hidden = Boolean(filtered.length);
    $("execution-task-count").textContent = `${filtered.length ? taskPage * 25 + 1 : 0}–${Math.min((taskPage + 1) * 25, filtered.length)} de ${filtered.length} registros`;
    $("run-page-prev").disabled = taskPage === 0;
    $("run-page-next").disabled = (taskPage + 1) * 25 >= filtered.length;
    const task = data.tasks[taskIndex];
    $("run-task-title").textContent = task ? task.name : "Nenhum processo selecionado";
    $("run-task-info").replaceChildren();
    $("task-open-logs").disabled = !task;
    if (task) {
      const detailRun = runs.find((item) => item.id === detailId);
      const currentJob = findCurrentSlurmJob(task, detailRun?.connection, typeof connection === "undefined" ? null : connection, typeof snapshot === "undefined" ? null : snapshot);
      const sameConnection = typeof connection !== "undefined" && connection && detailRun && ["host", "user", "port", "control_path"].every((field) => (connection[field] || "") === (detailRun.connection[field] || ""));
      const fields = {"ID tarefa":task.task_id, "ID Slurm":task.native_id, Estado:task.status, "Código de saída":task.exit, Duração:task.duration, "Tempo em execução":task.realtime,
                      "Fila Slurm atual":currentJob ? (labels[currentJob.state] || currentJob.state) : sameConnection && snapshot ? "Não encontrado na fila atual" : "Fila não consultada nesta conexão"};
      for (const [label, value] of Object.entries(fields)) $("run-task-info").append(element("dt",label),element("dd",value || "—"));
    }
  }
  for (const id of ["run-task-search", "run-task-state"]) $(id).addEventListener(id.endsWith("search") ? "input" : "change", () => { taskPage = 0; render(); });
  $("run-page-prev").addEventListener("click", () => { taskPage--; render(); });
  $("run-page-next").addEventListener("click", () => { taskPage++; render(); });
  $("task-open-logs").addEventListener("click", () => {
    if (taskIndex == null) return;
    $("log-task").value = String(taskIndex); clearLog();
    location.hash = `execution/${detailId}/logs`;
  });
  $("logs-open-results").addEventListener("click", (event) => { event.preventDefault(); location.hash = `execution/${detailId}/files`; });
  $("log-task").addEventListener("change", clearLog);
  $("log-file").addEventListener("change", clearLog);
  $("log-read").addEventListener("click", async () => {
    const run = runs.find((item) => item.id === detailId);
    const task = run?.data.tasks[Number($("log-task").value)];
    if (!task) return;
    const requestId = ++logRequest;
    logController?.abort(); logController = new AbortController();
    const controller = logController;
    const timeout = setTimeout(() => controller.abort(), 30000);
    $("log-read").disabled = true; $("log-read").textContent = "Lendo…";
    $("log-status").textContent = "Consultando o log no servidor…";
    try {
      const response = await fetch("/api/execution", {method:"POST", headers:{"Content-Type":"application/json", "X-HelixForge-Token":token},
        body:JSON.stringify({connection:run.connection, directory:run.data.directory, log:{task_id:task.task_id, native_id:task.native_id, name:task.name, file:$("log-file").value}}), signal:controller.signal});
      const data = await response.json();
      if (requestId !== logRequest || detailId !== run.id) return;
      if (!response.ok) throw new Error(data.error || "Não foi possível ler o log.");
      $("log-content").textContent = data.content || "Arquivo vazio.";
      $("log-path").textContent = data.path;
      $("connection-status").textContent = `Leitura de log realizada · ${run.connection.host}`;
      document.querySelector(".connection-bar").className = "connection-bar connected";
      $("last-checked").textContent = `Última leitura de log: ${date(data.checked_at)}`;
      $("log-status").textContent = `Leitura: ${date(data.checked_at)} · ${data.size} bytes no arquivo${data.truncated ? " · exibindo somente o trecho final" : " · conteúdo completo"}.`;
    } catch (error) {
      if (requestId !== logRequest || detailId !== run.id) return;
      $("log-status").textContent = (error.name === "AbortError" ? "A leitura excedeu o tempo limite." : error instanceof TypeError ? "O serviço local não respondeu." : error.message) + " O conteúdo exibido, se houver, é da leitura anterior.";
    } finally {
      clearTimeout(timeout);
      if (requestId === logRequest) { $("log-read").disabled = false; $("log-read").textContent = "Ler log ↻"; }
    }
  });

  async function inspectRun(config, directory) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch("/api/execution", { method: "POST", headers: { "Content-Type": "application/json", "X-HelixForge-Token": token }, body: JSON.stringify({ connection: config, directory }), signal: controller.signal });
      const data = await response.json();
      if (!response.ok) { const problem = new Error(data.error || "Não foi possível ler a execução."); problem.code = data.code || "unavailable"; throw problem; }
      $("connection-status").textContent = `Leitura realizada · ${config.host}`;
      document.querySelector(".connection-bar").className = "connection-bar connected";
      $("last-checked").textContent = `Última leitura de execução: ${date(data.checked_at)}`;
      return data;
    } catch (err) {
      if (err.name === "AbortError") { const problem = new Error("A consulta demorou demais. Verifique a conexão SSH."); problem.code = "unavailable"; throw problem; }
      if (err instanceof TypeError) { const problem = new Error("O serviço local não respondeu. Verifique se ele continua aberto."); problem.code = "unavailable"; throw problem; }
      throw err;
    } finally { clearTimeout(timeout); }
  }
  function setReading(value) {
    reading = value;
    for (const id of ["save-execution", "update-execution", "remove-execution", "cancel-execution"]) $(id).disabled = value;
    $("save-execution").textContent = value ? "Consultando…" : "Verificar e registrar";
    $("update-execution").textContent = value ? "Consultando…" : "Atualizar leitura ↻";
  }
  $("register-execution").addEventListener("click", () => {
    $("execution-form").hidden = false;
    $("execution-name").focus();
  });
  $("cancel-execution").addEventListener("click", () => { $("execution-form").hidden = true; error(""); });
  $("execution-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (reading) return;
    error("");
    const name = $("execution-name").value.trim();
    if (!name) return error("Informe o nome da execução.");
    const config = Object.fromEntries(["host", "user", "port", "control_path"].map((id) => [id, $(id).value.trim()]));
    const workflow = $("execution-workflow").value;
    if (!config.host) { $("connection-settings").open = true; $("host").focus(); return error("Configure o servidor SSH acima antes de registrar."); }
    setReading(true);
    try {
      const data = await inspectRun(config, $("execution-directory").value.trim());
      if (runs.some((run) => run.connection.host === config.host && run.connection.user === config.user && run.connection.port === config.port &&
          (run.data.directory === data.directory || data.fingerprint && run.data.fingerprint === data.fingerprint))) throw new Error("Esta execução já está cadastrada para esta conexão.");
      const run = normalizeRun({ id: crypto.randomUUID(), name, workflow, connection: config, created_at: new Date().toISOString(), data,
        availability:{state:data.overall_state === "partial" ? "partial" : "current", checked_at:data.checked_at}, history:[] });
      persist([run, ...runs]);
      selected = run.id;
      $("execution-form").reset();
      $("execution-form").hidden = true;
      $("connection-settings").open = false;
      render();
    } catch (err) { error(err.message); }
    finally { setReading(false); }
  });
  $("update-execution").addEventListener("click", async () => {
    const run = runs.find((item) => item.id === (detailId || selected));
    if (!run || reading) return;
    error(""); setReading(true);
    try {
      const data = await inspectRun(run.connection, run.data.directory);
      const degraded = executionRegression(run.data, data);
      if (degraded) {
        const changed = preserveExecutionSnapshot(run, degraded.code, new Date().toISOString());
        persist(runs.map((item) => item.id === run.id ? changed : item));
        throw Object.assign(new Error(degraded.message), {code:degraded.code, preserved:true});
      }
      const changed = {...run, data, availability:{state:data.overall_state === "partial" ? "partial" : "current", checked_at:data.checked_at},
        history:history(run, snapshotSummary(run.data, run.availability?.state || "current", run.availability?.reason || ""))};
      persist(runs.map((item) => item.id === run.id ? changed : item));
      render();
    } catch (err) {
      if (!err.preserved) {
        const changed = preserveExecutionSnapshot(run, err.code || "unavailable", new Date().toISOString());
        try { persist(runs.map((item) => item.id === run.id ? changed : item)); render(); } catch { /* Original error remains actionable. */ }
      }
      error(`${err.message} O último snapshot válido foi preservado.`);
    }
    finally { setReading(false); }
  });
  $("remove-execution").addEventListener("click", () => {
    if (reading) return;
    const id = detailId || selected;
    if (removeCandidate !== id) {
      removeCandidate = id; $("remove-execution").textContent = "Confirmar remoção";
      $("remove-note").textContent = "Clique novamente para remover somente o cadastro local.";
      clearTimeout(removeTimer); removeTimer = setTimeout(() => { removeCandidate = null; $("remove-execution").textContent = "Remover do histórico"; $("remove-note").textContent = "Os arquivos no servidor são mantidos."; }, 5000);
      return;
    }
    try {
      const removal = removeExecutionLocally(runs, id); removedRun = removal.removed; persist(removal.remaining);
      selected = runs[0]?.id; detailId = null; removeCandidate = null; error(""); location.hash = "executions"; render();
      $("undo-remove").hidden = false; error("Cadastro removido. Os arquivos no servidor foram mantidos; você pode desfazer a remoção.");
    }
    catch (err) { error(err.message); }
  });
  $("undo-remove").addEventListener("click", () => {
    if (!removedRun) return;
    try { const restored = removedRun; persist(restoreExecutionLocally(runs, restored)); selected = restored.id; removedRun = null; $("undo-remove").hidden = true; location.hash = `execution/${selected}/summary`; render(); }
    catch (err) { error(err.message); }
  });
  $("export-executions").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({schema:"helixforge.slurm.executions.v1", exported_at:new Date().toISOString(), runs}, null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "helixforge-executions.json"; link.click(); URL.revokeObjectURL(url);
  });
  $("import-executions").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", async () => {
    try {
      const file = $("import-file").files[0];
      if (!file || file.size > 10 * 1024 * 1024) throw new Error("O histórico deve ser um JSON de até 10 MiB.");
      const parsed = JSON.parse(await file.text());
      if (parsed.schema !== "helixforge.slurm.executions.v1" || !validRuns(parsed.runs)) throw new Error("Arquivo de histórico inválido.");
      const merged = [...parsed.runs.map(normalizeRun), ...runs.filter((run) => !parsed.runs.some((item) => item.id === run.id))];
      persist(merged); selected = runs[0]?.id; error(""); render();
    } catch (err) { error(err.message || "Não foi possível importar o histórico."); }
    finally { $("import-file").value = ""; }
  });
  $("execution-search").addEventListener("input", render);
  $("execution-filter").addEventListener("change", render);
  document.addEventListener("visibilitychange", render);
  route();
})();
