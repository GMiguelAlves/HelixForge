"use strict";
(() => {
  const key = "helixforge.executions.v1";
  const workflows = { chipseq: "ChIP-seq", rnaseq: "RNA-seq", integrative: "Integrativo", all: "Todos" };
  let runs = [];
  let selected = null;
  let reading = false;
  const error = (message) => {
    $("execution-error").textContent = message;
    $("execution-error").hidden = !message;
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
    for (const name of ["executions", "jobs"]) {
      if (name === screen) $("nav-" + name).setAttribute("aria-current", "page");
      else $("nav-" + name).removeAttribute("aria-current");
    }
  }
  $("nav-executions").addEventListener("click", () => showScreen("executions"));
  $("nav-jobs").addEventListener("click", () => showScreen("jobs"));
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
      button.addEventListener("click", () => { selected = run.id; render(); });
      name.append(button, element("small", `${workflows[run.workflow]} · ${run.connection.host}`));
      row.append(name, element("td", traceLabel(run.data)), element("td", date(run.data.checked_at)));
      $("execution-rows").append(row);
    }
    $("execution-table").hidden = !visible.length;
    $("execution-empty").hidden = Boolean(visible.length);
    $("execution-empty").replaceChildren(element("h2", runs.length ? "Nenhuma execução corresponde ao filtro" : "Nenhuma execução registrada"),
      element("p", runs.length ? "Tente outro nome, servidor ou workflow." : "Registre o diretório de saída de uma análise para consultar seus processos e arquivos."));
    $("execution-count").textContent = `${visible.length} de ${runs.length} execuções`;
    const run = runs.find((item) => item.id === selected);
    $("execution-placeholder").hidden = Boolean(run);
    $("execution-detail").hidden = !run;
    $("execution-records").hidden = !run;
    if (!run) return;
    const data = run.data;
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
    $("execution-trace-note").textContent = data.trace_found ? "Registros presentes no trace desta saída. Uma nova execução no mesmo diretório pode substituir esse arquivo." : "execution_trace.tsv ainda não foi encontrado em pipeline_info. O cadastro foi mantido para consultas posteriores.";
    $("execution-tasks").replaceChildren();
    for (const task of data.tasks.slice(-100)) {
      const row = element("tr", "");
      row.append(element("td", task.name), element("td", task.native_id || "—"), element("td", labels[task.status] || task.status), element("td", task.duration || "—"));
      $("execution-tasks").append(row);
    }
    $("execution-task-count").textContent = data.tasks.length > 100 ? `Exibindo os últimos 100 de ${data.tasks.length} registros.` : `${data.tasks.length} registros no trace.`;
    $("execution-artifacts").replaceChildren(...(data.artifacts.length ? data.artifacts : ["Nenhum relatório ou manifesto encontrado nos caminhos esperados."]).map((path) => element("li", path)));
  }

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
    const run = runs.find((item) => item.id === selected);
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
    try { persist(runs.filter((run) => run.id !== selected)); selected = runs[0]?.id; error(""); render(); }
    catch (err) { error(err.message); }
  });
  $("execution-search").addEventListener("input", render);
  $("execution-filter").addEventListener("change", render);
  render();
})();
