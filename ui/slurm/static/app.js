"use strict";
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="helixforge-token"]').content;
const storageKey = "helixforge.slurm.connection.v1";
let connection = null;
let snapshot = null;
let busy = false;
let timer = null;
let selectedJob = null;
const labels = { RUNNING: "Em execução", PENDING: "Pendente", COMPLETING: "Finalizando", CONFIGURING: "Preparando", SUSPENDED: "Suspenso", STOPPED: "Parado", FAILED: "Falhou", CANCELLED: "Cancelado", TIMEOUT: "Tempo esgotado", COMPLETED: "Concluído", PREEMPTED: "Preemptado", OUT_OF_MEMORY: "Sem memória" };

function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function statusClass(state) {
  return state === "RUNNING" ? "running" : state === "PENDING" ? "pending" : "";
}

function renderJobs() {
  const jobs = snapshot ? snapshot.jobs : [];
  const running = jobs.filter((job) => job.state === "RUNNING").length;
  const pending = jobs.filter((job) => job.state === "PENDING").length;
  for (const [id, value] of Object.entries({ total: jobs.length, running, pending, other: jobs.length - running - pending })) {
    $(id).textContent = snapshot ? value : "—";
  }
  const query = $("search").value.trim().toLocaleLowerCase();
  const state = $("state").value;
  const visible = jobs.filter((job) => {
    const matchesState = state === "all" || (state === "other" ? !["RUNNING", "PENDING"].includes(job.state) : job.state === state);
    return matchesState && [job.id, job.name, job.partition].some((value) => value.toLocaleLowerCase().includes(query));
  });
  $("jobs").replaceChildren();
  for (const job of visible) {
    const row = document.createElement("tr");
    if (selectedJob && job.id === selectedJob.id) row.className = "selected";
    const name = document.createElement("td");
    const button = element("button", job.name || "Sem nome", "job-select");
    button.type = "button";
    button.id = `job-${job.id}`;
    button.setAttribute("aria-label", `Detalhes do job ${job.id}`);
    button.setAttribute("aria-controls", "inspector-content");
    button.setAttribute("aria-pressed", String(Boolean(selectedJob && selectedJob.id === job.id)));
    button.addEventListener("click", () => openDetails(job));
    name.append(button, element("small", `#${job.id}`));
    const status = document.createElement("td");
    status.append(element("span", labels[job.state] || job.state, `badge ${statusClass(job.state)}`));
    const duration = document.createElement("td");
    duration.append(element("strong", job.elapsed), element("small", `Limite ${job.time_limit}`));
    row.append(name, status, element("td", job.partition), duration);
    $("jobs").append(row);
  }
  $("table-wrap").hidden = !visible.length;
  $("empty").hidden = Boolean(visible.length);
  if (!visible.length) {
    const title = !snapshot ? "Sem conexão" : jobs.length ? "Nenhum job corresponde ao filtro" : "Nenhum job na fila";
    const description = !snapshot ? "Configure a conexão acima para consultar seus jobs." : jobs.length ? "Tente outro nome, ID, partição ou estado." : `A consulta foi concluída para ${snapshot.user}. Jobs que saíram da fila não aparecem aqui.`;
    $("empty").replaceChildren(element("h2", title), element("p", description));
  }
  $("result-count").textContent = snapshot ? `${visible.length} de ${jobs.length} jobs · usuário ${snapshot.user}` : "Nenhuma consulta realizada";
}

function openDetails(job) {
  selectedJob = job;
  renderJobs();
  renderDetails();
  $("job-title").focus({ preventScroll: true });
  if (window.matchMedia("(max-width: 800px)").matches) {
    document.querySelector(".inspector").scrollIntoView({ block: "start" });
  }
}

function renderDetails() {
  $("inspector-empty").hidden = Boolean(selectedJob);
  $("inspector-content").hidden = !selectedJob;
  $("close-details").hidden = !selectedJob;
  if (!selectedJob) return;
  const current = snapshot && snapshot.jobs.find((job) => job.id === selectedJob.id);
  if (current) selectedJob = current;
  const job = selectedJob;
  $("job-number").textContent = `JOB / ${job.id}`;
  $("job-title").textContent = job.name || `Job ${job.id}`;
  $("job-snapshot-note").textContent = current ? "" : "Este job saiu da última consulta. Os detalhes abaixo são da consulta anterior; isso não confirma sucesso.";
  $("job-details").replaceChildren();
  const fields = { "ID Slurm": job.id, "Usuário": snapshot.user, "Estado Slurm": job.state, "Partição": job.partition, "Tempo decorrido": job.elapsed, "Limite": job.time_limit, "CPUs": job.cpus, "Nós": job.nodes, "Memória solicitada": job.memory, "Motivo / nós": job.reason, "Enviado em": job.submitted, "Início / previsão": job.start };
  for (const [label, value] of Object.entries(fields)) {
    $("job-details").append(element("dt", label), element("dd", value || "—"));
  }
}

function scheduleRefresh() {
  clearTimeout(timer);
  if (connection && $("auto").checked && location.hash === "#jobs" && !document.hidden && !busy) {
    timer = setTimeout(refresh, 30000);
  }
}

function selectConnection(config) {
  if (busy) return false;
  clearTimeout(timer);
  connection = null; snapshot = null; selectedJob = null;
  for (const id of ["host", "user", "port", "control_path"]) {
    $(id).value = config ? config[id] || "" : "";
    $(id).dispatchEvent(new Event("input", {bubbles:true}));
  }
  $("error").hidden = true;
  $("refresh").disabled = true;
  $("connection-status").textContent = config ? `Destino selecionado · ${config.host}` : "Não conectado";
  $("last-checked").textContent = "Aguardando consulta";
  document.querySelector(".connection-bar").className = "connection-bar";
  renderJobs(); renderDetails();
  return true;
}

async function refresh(collapseSettings = false) {
  if (!connection || busy) return;
  clearTimeout(timer);
  busy = true;
  $("refresh").disabled = true;
  $("connect").disabled = true;
  $("connect").textContent = "Consultando…";
  $("connection-status").textContent = `Consultando ${connection.host}…`;
  document.querySelector(".connection-bar").className = "connection-bar";
  $("error").hidden = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json", "X-HelixForge-Token": token }, body: JSON.stringify(connection), signal: controller.signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Não foi possível consultar os jobs.");
    snapshot = data;
    if (!selectedJob && snapshot.jobs.length) selectedJob = snapshot.jobs[0];
    $("connection-status").textContent = `Conectado · ${snapshot.user} em ${connection.host}${connection.port ? `:${connection.port}` : ""}`;
    document.querySelector(".connection-bar").className = "connection-bar connected";
    $("last-checked").textContent = `Última consulta: ${new Date(snapshot.checked_at).toLocaleString("pt-BR")}`;
    if (collapseSettings === true) $("connection-settings").open = false;
    renderJobs();
    renderDetails();
  } catch (error) {
    $("error").textContent = error.name === "AbortError" ? "A consulta demorou demais. Verifique o túnel e tente novamente." : error instanceof TypeError ? "O serviço local não respondeu. Verifique se ele continua aberto e tente novamente." : error.message;
    $("error").hidden = false;
    $("connection-status").textContent = snapshot ? "Conexão indisponível · dados da última consulta" : "Não conectado · consulta falhou";
    document.querySelector(".connection-bar").className = "connection-bar stale";
  } finally {
    clearTimeout(timeout);
    busy = false;
    $("connect").disabled = false;
    $("connect").textContent = "Conectar e consultar";
    $("refresh").disabled = false;
    scheduleRefresh();
    document.dispatchEvent(new Event("connection-updated"));
  }
}

$("connection-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (busy) return;
  const next = Object.fromEntries(["host", "user", "port", "control_path"].map((id) => [id, $(id).value.trim()]));
  if (JSON.stringify(next) !== JSON.stringify(connection)) {
    snapshot = null;
    selectedJob = null;
    $("last-checked").textContent = "Aguardando primeira consulta";
    renderDetails();
    renderJobs();
  }
  connection = next;
  try {
    if ($("remember").checked) localStorage.setItem(storageKey, JSON.stringify(connection));
    else localStorage.removeItem(storageKey);
  } catch { /* Connection works even when browser storage is unavailable. */ }
  refresh(true);
});
$("remember").addEventListener("change", () => {
  if (!$("remember").checked) {
    try { localStorage.removeItem(storageKey); } catch { /* Optional storage. */ }
  }
});
$("refresh").addEventListener("click", refresh);
$("search").addEventListener("input", renderJobs);
$("state").addEventListener("change", renderJobs);
$("auto").addEventListener("change", scheduleRefresh);
document.addEventListener("visibilitychange", scheduleRefresh);
window.addEventListener("hashchange", scheduleRefresh);
$("close-details").addEventListener("click", () => {
  const previousId = selectedJob && selectedJob.id;
  const target = $("job-" + previousId) || $("search");
  target.focus();
});
try {
  const saved = JSON.parse(localStorage.getItem(storageKey));
  if (saved && typeof saved === "object") {
    for (const id of ["host", "user", "port", "control_path"]) if (typeof saved[id] === "string") $(id).value = saved[id];
    $("remember").checked = true;
  }
} catch { /* Ignore invalid or unavailable saved preferences. */ }
renderJobs();
