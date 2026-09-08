"use strict";
function buildExecutionCommand(draft) {
  const quote = (value) => /^[A-Za-z0-9_./,:=@%+-]+$/.test(value) ? value : "'" + value.replace(/'/g, "'\\''") + "'";
  if (!["rnaseq", "chipseq", "integrative", "all"].includes(draft.workflow)) throw new Error("Escolha um workflow válido.");
  if (!["slurm", "slurm,apptainer", "slurm,singularity"].includes(draft.runtime)) throw new Error("Escolha um ambiente válido.");
  if (!draft.name?.trim() || !draft.host?.trim()) throw new Error("Informe o nome e configure o servidor SSH no topo da página.");
  for (const field of ["repo", "config", "launch", "output", "work"]) {
    const path = draft[field];
    if (typeof path !== "string" || !path.startsWith("/") || path.length > 2048 || /[\x00-\x1f\x7f%]/.test(path) || path.split("/").some((part) => [".", ".."].includes(part))) throw new Error("Use caminhos absolutos, sem '.', '..', '%' ou quebras de linha.");
  }
  const normalized = (path) => path.replace(/\/+/g, "/").replace(/\/$/, "") || "/";
  const output = normalized(draft.output), work = normalized(draft.work), repo = normalized(draft.repo), launch = normalized(draft.launch);
  const contains = (a, b) => a === "/" || b === a || b.startsWith(a + "/");
  if (contains(output, work) || contains(work, output) || contains(output, repo) || contains(work, repo) || contains(output, launch) || contains(work, launch)) throw new Error("Separe saída e trabalho; eles não podem conter o repositório ou o diretório de lançamento.");
  for (const [field, max] of [["memory", 1024], ["hours", 720]]) if (!/^\d+$/.test(draft[field]) || +draft[field] < 1 || +draft[field] > max) throw new Error("Informe memória e tempo como números inteiros dentro dos limites do formulário.");
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(draft.partition) || (draft.account && !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(draft.account))) throw new Error("Partição ou conta inválida.");
  const jobName = "hf-" + draft.name.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9_-]+/g, "-").slice(0, 60);
  const command = ["nextflow", "run", draft.repo, "-profile", draft.runtime, "-c", draft.config, "-work-dir", draft.work,
    "--workflow", draft.workflow, "--outdir", draft.output].map(quote).join(" ");
  const args = ["sbatch", "--job-name", jobName, "--partition", draft.partition, "--cpus-per-task", "1", "--mem", `${+draft.memory}G`,
    "--time", `${+draft.hours}:00:00`, "--chdir", draft.launch, "--output", `${launch}/helixforge-%j.log`];
  if (draft.account) args.push("--account", draft.account);
  args.push("--wrap", "exec " + command);
  const lines = [args[0]];
  for (let i = 1; i < args.length; i += 2) lines.push(`${args[i]} ${quote(args[i + 1])}`);
  return lines.join(" \\\n  ");
}
if (typeof module !== "undefined") module.exports = { buildExecutionCommand };
if (typeof document !== "undefined") (() => {
  const storage = "helixforge.new-execution.v1";
  const fields = ["name", "workflow", "repo", "config", "launch", "output", "work", "partition", "runtime", "memory", "hours", "account"];
  const workflows = {rnaseq: "RNA-seq", chipseq: "ChIP-seq", integrative: "Integrativo", all: "RNA-seq + ChIP-seq + Integrativo"};
  let reviewed = null;
  const message = (text) => { $("new-message").textContent = text; };
  function read() { return {...Object.fromEntries(fields.map((field) => [field, $("new-" + field).value.trim()])), host: $("host").value.trim(), user: $("user").value.trim(), port: $("port").value.trim()}; }
  function describe() {
    $("new-server").textContent = $("host").value.trim() || "Configure a conexão SSH";
    const workflow = $("new-workflow").value;
    $("new-workflow-note").textContent = workflow === "integrative" ? "A configuração deve apontar para os manifestos RNA-seq e ChIP-seq e as políticas de integração." : workflow === "rnaseq" ? "A configuração deve definir as amostras, referências, modo de execução e desenho da análise de RNA-seq." : workflow === "chipseq" ? "A configuração deve definir amostras e controles, referências, parâmetros de picos e desenho da análise de ChIP-seq." : "A configuração deve reunir as entradas e os parâmetros dos três workflows.";
  }
  function save() {
    try { localStorage.setItem(storage, JSON.stringify(read())); message("Rascunho salvo neste navegador. Nenhum job enviado."); return true; }
    catch { message("Não foi possível salvar o rascunho. Verifique o armazenamento do navegador."); return false; }
  }
  function edit() { reviewed = null; $("new-review").hidden = true; $("new-form").hidden = false; }
  try {
    const saved = JSON.parse(localStorage.getItem(storage));
    if (saved && typeof saved === "object") for (const field of fields) if (typeof saved[field] === "string") $("new-" + field).value = saved[field];
  } catch { message("O rascunho anterior não pôde ser recuperado."); }
  $("new-form").addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      const draft = read(); const command = buildExecutionCommand(draft);
      if (!save()) return;
      reviewed = draft;
      $("new-command").textContent = command;
      $("new-review-info").replaceChildren();
      for (const [label, value] of Object.entries({Nome:draft.name, Workflow:workflows[draft.workflow], Servidor:draft.host, Usuário:draft.user || "Do SSH config", Porta:draft.port || "Do SSH config", Configuração:draft.config, Lançamento:draft.launch, Saída:draft.output, Trabalho:draft.work, Partição:draft.partition, "Job de coordenação":`1 CPU · ${draft.memory} GB · ${draft.hours} h`})) $("new-review-info").append(element("dt", label), element("dd", value));
      $("new-form").hidden = true; $("new-review").hidden = false;
      $("new-review").scrollIntoView({block:"start"});
    } catch (error) { message(error.message); $("new-message").scrollIntoView({block:"center"}); }
  });
  $("new-save").addEventListener("click", save);
  $("new-clear").addEventListener("click", () => {
    try { localStorage.removeItem(storage); $("new-form").reset(); edit(); describe(); message("Rascunho removido deste navegador."); }
    catch { message("Não foi possível remover o rascunho salvo."); }
  });
  $("new-edit").addEventListener("click", edit);
  $("new-workflow").addEventListener("change", describe);
  for (const field of ["host", "user", "port", "control_path"]) $(field).addEventListener("input", () => { if (reviewed) { edit(); message("Conexão alterada. Revise novamente antes de copiar o comando."); } describe(); });
  $("new-copy").addEventListener("click", async () => {
    if (!reviewed || JSON.stringify(read()) !== JSON.stringify(reviewed)) { edit(); message("Os dados mudaram. Revise a execução novamente."); return; }
    try { await navigator.clipboard.writeText($("new-command").textContent); message("Comando copiado. Nenhum job foi enviado pela UI."); }
    catch { message("Não foi possível copiar automaticamente. Selecione o comando abaixo."); }
  });
  window.addEventListener("hashchange", describe);
  describe();
})();
