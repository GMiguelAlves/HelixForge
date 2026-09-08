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
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "[]");
    if (!Array.isArray(saved) || saved.some((run) => !run.id || typeof run.name !== "string" || !workflows[run.workflow] ||
        typeof run.connection?.host !== "string" || typeof run.data?.directory !== "string" ||
        !Array.isArray(run.data.tasks) || !Array.isArray(run.data.artifacts))) throw new Error();
    runs = saved;
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
    for (const name of ["executions", "jobs"]) {
      if (name === screen || (name === "executions" && screen === "execution")) $("nav-" + name).setAttribute("aria-current", "page");
      else $("nav-" + name).removeAttribute("aria-current");
    }
  }
  $("nav-executions").addEventListener("click", () => { location.hash = "executions"; });
  $("nav-jobs").addEventListener("click", () => { location.hash = "jobs"; });
  function route() {
    const parts = location.hash.slice(1).split("/");
    const previous = detailId;
    detailId = parts[0] === "execution" && runs.some((run) => run.id === parts[1]) ? parts[1] : null;
    detailSection = ["summary", "processes", "files"].includes(parts[2]) ? parts[2] : "summary";
    if (previous !== detailId) {
      taskPage = 0; taskIndex = null;
      $("run-task-search").value = ""; $("run-task-state").value = "all";
    }
    showScreen(detailId ? "execution" : parts[0] === "jobs" ? "jobs" : "executions");
    for (const section of ["summary", "processes", "files"]) {
      $("run-panel-" + section).hidden = section !== detailSection;
      if (section === detailSection) $("run-tab-" + section).setAttribute("aria-current", "page");
      else $("run-tab-" + section).removeAttribute("aria-current");
    }
    render();
    if (detailId && previous !== detailId) $("run-title").focus({preventScroll:true});
  }
  window.addEventListener("hashchange", route);
  for (const section of ["summary", "processes", "files"]) $("run-tab-" + section).addEventListener("click", () => {
    location.hash = `execution/${detailId}/${section}`;
  });
  $("open-execution").addEventListener("click", () => { if (selected) location.hash = `execution/${selected}/summary`; });
  const date = (value) => value ? new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
  const traceLabel = (data) => !data.trace_found ? "Sem trace" : data.tasks.some((task) => task.status === "FAILED") ? "Falhas registradas" : `${data.tasks.length} registros`;

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
      row.append(name, element("td", traceLabel(run.data)), element("td", date(run.data.checked_at)));
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
    if (!run) return;
    const data = run.data;
    $("run-title").textContent = run.name;
    $("run-breadcrumb-name").textContent = run.name;
    $("run-subtitle").textContent = `${workflows[run.workflow]} / ${run.connection.host}`;
    $("run-read-time").textContent = `Última leitura: ${date(data.checked_at)} · dados salvos neste navegador`;
    $("execution-detail-title").textContent = run.name;
    $("execution-note").textContent = "Estado final da análise não confirmado. Dados da última leitura.";
    $("execution-info").replaceChildren();
    const completed = data.tasks.filter((task) => ["COMPLETED", "CACHED"].includes(task.status)).length;
    const fields = { Workflow: workflows[run.workflow], Servidor: run.connection.host,
      "Diretório": data.directory, "Registrada em": date(run.created_at), "Última leitura": date(data.checked_at),
      "Trace alterado": date(data.trace_modified && data.trace_modified * 1000),
      "Processos": String(data.tasks.length), "Concluídos / cache": String(completed),
      "Falhas no trace": String(data.tasks.filter((task) => task.status === "FAILED").length) };
    for (const [label, value] of Object.entries(fields)) $("execution-info").append(element("dt", label), element("dd", value));
    $("execution-preview").replaceChildren();
    for (const [label, value] of Object.entries({Workflow: workflows[run.workflow], Servidor:run.connection.host, Processos: String(data.tasks.length), "Última leitura":date(data.checked_at)})) $("execution-preview").append(element("dt", label), element("dd", value));
    $("run-trace-status").textContent = traceLabel(data);
    $("run-counts").replaceChildren();
    for (const [label, count] of [["Concluídos", data.tasks.filter((task) => task.status === "COMPLETED").length], ["Em cache", data.tasks.filter((task) => task.status === "CACHED").length], ["Falhas", data.tasks.filter((task) => task.status === "FAILED").length]]) {
      const line = element("div", ""); line.append(element("strong", String(count)), element("span", label)); $("run-counts").append(line);
    }
    $("execution-trace-note").textContent = data.trace_found ? "Registros presentes no trace desta saída. Uma nova execução no mesmo diretório pode substituir esse arquivo." : "execution_trace.tsv ainda não foi encontrado em pipeline_info. O cadastro foi mantido para consultas posteriores.";
    renderTasks(data);
    $("execution-artifacts").replaceChildren();
    $("run-copy-status").textContent = "";
    if (!data.artifacts.length) $("execution-artifacts").append(element("p", "Nenhum relatório ou manifesto encontrado nos caminhos esperados."));
    for (const path of data.artifacts) {
      const row = element("div", "", "run-file");
      const text = element("div", "");
      const title = path.endsWith("execution_report.html") ? "Relatório de execução" : path.endsWith("execution_timeline.html") ? "Timeline" : "Manifesto · " + path.split("/")[0];
      text.append(element("h3", title), element("code", path));
      const copy = element("button", "Copiar caminho");
      copy.setAttribute("aria-label", `Copiar caminho: ${title}`);
      copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(data.directory.replace(/\/$/, "") + "/" + path); $("run-copy-status").textContent = `Caminho copiado: ${title}.`; }
        catch { $("run-copy-status").textContent = `Copie o caminho: ${data.directory.replace(/\/$/, "")}/${path}`; }
      });
      row.append(text, copy); $("execution-artifacts").append(row);
    }
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
    if (task) for (const [label, value] of Object.entries({"ID tarefa":task.task_id, "ID Slurm":task.native_id, Estado:task.status, "Código de saída":task.exit, Duração:task.duration, "Tempo em execução":task.realtime})) $("run-task-info").append(element("dt",label),element("dd",value || "—"));
  }
  for (const id of ["run-task-search", "run-task-state"]) $(id).addEventListener(id.endsWith("search") ? "input" : "change", () => { taskPage = 0; render(); });
  $("run-page-prev").addEventListener("click", () => { taskPage--; render(); });
  $("run-page-next").addEventListener("click", () => { taskPage++; render(); });

  async function inspectRun(config, directory) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch("/api/execution", { method: "POST", headers: { "Content-Type": "application/json", "X-HelixForge-Token": token }, body: JSON.stringify({ connection: config, directory }), signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Não foi possível ler a execução.");
      $("connection-status").textContent = `Leitura realizada · ${config.host}`;
      document.querySelector(".connection-bar").className = "connection-bar connected";
      $("last-checked").textContent = `Última leitura de execução: ${date(data.checked_at)}`;
      return data;
    } catch (err) {
      if (err.name === "AbortError") throw new Error("A consulta demorou demais. Verifique a conexão SSH.");
      if (err instanceof TypeError) throw new Error("O serviço local não respondeu. Verifique se ele continua aberto.");
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
      if (runs.some((run) => run.connection.host === config.host && run.connection.user === config.user && run.connection.port === config.port && run.data.directory === data.directory)) throw new Error("Este diretório já está cadastrado para esta conexão.");
      const run = { id: crypto.randomUUID(), name, workflow, connection: config, created_at: new Date().toISOString(), data };
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
      persist(runs.map((item) => item.id === run.id ? { ...run, data } : item));
      render();
    } catch (err) { error(`${err.message} Os dados da última leitura foram mantidos.`); }
    finally { setReading(false); }
  });
  $("remove-execution").addEventListener("click", () => {
    if (reading) return;
    try { persist(runs.filter((run) => run.id !== (detailId || selected))); selected = runs[0]?.id; detailId = null; error(""); location.hash = "executions"; render(); }
    catch (err) { error(err.message); }
  });
  $("execution-search").addEventListener("input", render);
  $("execution-filter").addEventListener("change", render);
  route();
})();
