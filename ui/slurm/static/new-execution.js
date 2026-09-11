"use strict";
const SUBMISSION_FIELD_LABELS = {
  host:"Servidor ou alias SSH", "clone.path":"Caminho do clone", "clone.ref":"Tag, branch ou commit",
  name:"Nome da análise", "storage.project_root":"Diretório do projeto leve", "storage.launch":"Diretório de lançamento",
  "storage.output":"Diretório de resultados", "storage.work":"Workdir", "runtime.partition":"Partição Slurm",
  "runtime.memory":"Memória do coordenador (GB)", "runtime.hours":"Tempo do coordenador (h)",
  "organism.name":"Organismo", "organism.reference_id":"Identificador da referência", "organism.genome_fasta":"Genoma FASTA",
  "organism.transcriptome_fasta":"Transcriptoma FASTA", "organism.annotation":"Anotação GTF ou GFF3",
  "science.effective_genome_size":"Effective genome size", "statistics.variable":"Variável principal", "statistics.formula":"Fórmula",
  "statistics.alpha":"Alpha", "statistics.lfc_threshold":"Limiar absoluto log2FC", "statistics.min_replicates":"Mínimo de replicatas",
  "statistics.contrasts.0.numerator":"Numerador do contraste", "statistics.contrasts.0.denominator":"Denominador do contraste",
  rnaseq_samples:"Amostras RNA-seq", chipseq_samples:"Amostras ChIP-seq",
  "integration.rna_manifest":"Manifest RNA-seq", "integration.chip_manifest":"Manifest ChIP-seq",
  "integration.policy_paths.harmonization":"Política de harmonização", "integration.policy_paths.interpretation":"Política de interpretação",
  "integration.policy_paths.mark_roles":"Papéis das marcas", "integration.policy_paths.prioritization_context":"Contexto de priorização",
  "integration.policy_paths.functional_annotation":"Anotação funcional"
};
const SAMPLE_FIELD_LABELS = {sample_id:"Sample ID", fastq_1:"FASTQ R1", fastq_2:"FASTQ R2", condition:"Condição", batch:"Batch", replicate:"Replicata", dataset:"Dataset", run_accession:"Run accession", mark_or_factor:"Mark / fator", control_id:"Control ID", layout:"Layout"};
function submissionFieldLabel(field) {
  const sample = /^(rnaseq|chipseq)_samples\.(\d+)\.([a-z0-9_]+)$/.exec(field);
  if (sample) return `${SAMPLE_FIELD_LABELS[sample[3]] || sample[3]} da amostra ${+sample[2] + 1} de ${sample[1] === "rnaseq" ? "RNA-seq" : "ChIP-seq"}`;
  return SUBMISSION_FIELD_LABELS[field] || field;
}
const requiredFieldMessage = (field) => `O campo “${submissionFieldLabel(field)}” é obrigatório.`;
function buildExecutionCommand(draft) {
  const quote = (value) => /^[A-Za-z0-9_./,:=@%+-]+$/.test(value) ? value : "'" + value.replace(/'/g, "'\\''") + "'";
  if (!["rnaseq", "chipseq", "integrative", "all"].includes(draft.workflow)) throw new Error("Escolha um workflow válido.");
  if (!["slurm", "slurm,apptainer", "slurm,singularity"].includes(draft.runtime)) throw new Error("Escolha um ambiente válido.");
  if (!draft.name?.trim() || !draft.host?.trim()) throw new Error("Informe o nome e configure o servidor SSH.");
  for (const field of ["repo", "config", "launch", "output", "work"]) {
    const path = draft[field];
    if (typeof path !== "string" || !path.startsWith("/") || path.length > 2048 || /[\x00-\x1f\x7f%]/.test(path) || path.split("/").some((part) => [".", ".."].includes(part))) throw new Error("Use caminhos absolutos e normalizados.");
  }
  const normalized = (path) => path.replace(/\/+/g, "/").replace(/\/$/, "") || "/";
  const output = normalized(draft.output), work = normalized(draft.work), repo = normalized(draft.repo), launch = normalized(draft.launch);
  const contains = (parent, child) => parent === "/" || child === parent || child.startsWith(parent + "/");
  if (contains(output, work) || contains(work, output) || contains(output, repo) || contains(work, repo) || contains(output, launch) || contains(work, launch)) throw new Error("Separe saída e trabalho; eles não podem conter o clone ou launch.");
  for (const [field, maximum] of [["memory", 1024], ["hours", 720]]) if (!/^\d+$/.test(draft[field]) || +draft[field] < 1 || +draft[field] > maximum) throw new Error("Memória e tempo inválidos.");
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(draft.partition) || (draft.account && !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(draft.account))) throw new Error("Partição ou conta inválida.");
  const jobName = "hf-" + draft.name.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9_-]+/g, "-").slice(0, 60);
  const command = ["nextflow", "run", repo, "-profile", draft.runtime, "-c", draft.config, "-work-dir", work, "--workflow", draft.workflow, "--outdir", output].map(quote).join(" ");
  const args = ["sbatch", "--job-name", jobName, "--partition", draft.partition, "--cpus-per-task", "1", "--mem", `${+draft.memory}G`, "--time", `${+draft.hours}:00:00`, "--chdir", launch, "--output", `${launch}/helixforge-%j.log`];
  if (draft.account) args.push("--account", draft.account);
  args.push("--wrap", "exec " + command);
  const lines = [args[0]];
  for (let i = 1; i < args.length; i += 2) lines.push(`${args[i]} ${quote(args[i + 1])}`);
  return lines.join(" \\\n+  ");
}
if (typeof module !== "undefined") module.exports = {buildExecutionCommand, requiredFieldMessage, submissionFieldLabel};

if (typeof document !== "undefined") (() => {
  const names = ["Conexão", "HelixForge", "Workflow", "Dados", "Referências", "Ciência", "Slurm", "Arquivos", "Preflight", "Submissão"];
  let step = 0, furthest = 0, busy = false, cloneReady = false, cloneToken = null, preparationToken = null, submissionToken = null;
  const rows = {rnaseq:[], chipseq:[]};
  const value = (id) => $(id).value.trim();
  const connection = () => Object.fromEntries(["host", "user", "port", "control_path"].map((field) => [field, value(field)]));
  const workflow = () => document.querySelector('input[name="workflow"]:checked').value;
  const cloneMode = () => document.querySelector('input[name="clone-mode"]:checked').value;
  const message = (text, failed=false) => { $("new-message").textContent = text; $("new-message").className = "wizard-message" + (failed ? " error" : ""); };
  async function api(path, body) {
    const response = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json", "X-HelixForge-Token":token}, body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) { const error = new Error(data.error || "A operação não pôde ser concluída."); error.code = data.code || "unavailable"; throw error; }
    return data;
  }
  function renderSteps() {
    $("wizard-steps").replaceChildren();
    names.forEach((name, index) => {
      const item = document.createElement("li"), button = element("button", `${String(index + 1).padStart(2, "0")} ${name}`);
      button.type = "button"; button.disabled = busy || index > furthest;
      if (index === step) button.setAttribute("aria-current", "step");
      button.addEventListener("click", () => { if (index <= furthest) { step = index; showStep(); } });
      item.append(button); $("wizard-steps").append(item);
    });
  }
  function setBusy(state, text="") {
    busy = state; for (const button of $("new-form").querySelectorAll("button")) button.disabled = state;
    if (text) message(text); if (!state) showStep();
  }
  function showStep() {
    for (const panel of document.querySelectorAll(".wizard-step")) panel.hidden = Number(panel.dataset.step) !== step;
    $("wizard-back").hidden = step === 0 || step === 9; $("wizard-next").hidden = step >= 8;
    $("wizard-position").textContent = `${step + 1} / 10`;
    $("wizard-server").textContent = value("host") || "Nenhum servidor selecionado";
    $("wizard-user").textContent = value("host") ? (value("user") || "Usuário definido pelo SSH config") : "Configure a conexão SSH para continuar.";
    renderSteps(); updateWorkflow();
  }
  function updateWorkflow() {
    const selected = workflow();
    $("rna-data").hidden = !["rnaseq", "all"].includes(selected); $("chip-data").hidden = !["chipseq", "all"].includes(selected);
    $("integrative-data").hidden = selected !== "integrative"; $("genome-field").hidden = !["chipseq", "all"].includes(selected) && !(["rnaseq", "all"].includes(selected) && value("new-quantification") === "star");
    $("transcriptome-field").hidden = !["rnaseq", "all"].includes(selected); $("blacklist-field").hidden = !["chipseq", "all"].includes(selected);
    for (const id of ["organism-field", "reference-id-field", "annotation-field"]) $(id).hidden = selected === "integrative";
    $("reference-note").textContent = selected === "integrative" ? "Organismo e genome/build serão lidos e comparados nos dois manifests." : "Índices Salmon e Bowtie2 são construídos pelo workflow; não são entradas obrigatórias.";
    $("genes-field").hidden = !["rnaseq", "all"].includes(selected); $("policy-field").hidden = !["integrative", "all"].includes(selected);
    $("rna-science").hidden = !["rnaseq", "all"].includes(selected); $("chip-science").hidden = !["chipseq", "all"].includes(selected);
    const required = ["new-repo", "new-name", "new-project-root", "new-launch", "new-output", "new-work", "new-partition", "new-runtime", "new-memory", "new-hours"];
    for (const id of required) setRequired($(id), true);
    setRequired($("new-ref"), cloneMode() === "new");
    for (const id of ["new-organism", "new-reference-id", "new-annotation"]) setRequired($(id), selected !== "integrative");
    setRequired($("new-transcriptome"), ["rnaseq", "all"].includes(selected));
    setRequired($("new-genome"), !$("genome-field").hidden);
    setRequired($("new-effective-genome-size"), ["chipseq", "all"].includes(selected));
    for (const id of ["new-variable", "new-formula", "new-alpha", "new-lfc", "new-min-replicates", "new-numerator", "new-denominator"]) setRequired($(id), selected !== "integrative");
    for (const id of ["new-rna-manifest", "new-chip-manifest"]) setRequired($(id), selected === "integrative");
    for (const id of ["new-policy-harmonization", "new-policy-interpretation", "new-policy-mark-roles", "new-policy-prioritization", "new-policy-functional"]) setRequired($(id), ["integrative", "all"].includes(selected) && value("new-policy-mode") === "custom");
  }
  function setRequired(input, state) {
    if (!input) return; input.required = state; const label = input.closest("label"); if (!label) return;
    let marker = label.querySelector(":scope > .required");
    if (state && !marker) { marker = element("span", "obrigatório", "required"); label.insertBefore(document.createTextNode(" "), input); label.insertBefore(marker, input); }
    if (!state && marker) marker.remove();
  }
  function inputField(label, key, initial="", type="text", required=type !== "checkbox") {
    const wrapper = document.createElement("label"), input = document.createElement("input"); wrapper.textContent = label; input.type = type; input.dataset.key = key; input.required = required;
    if (type === "checkbox") input.checked = Boolean(initial); else input.value = initial || ""; wrapper.append(input); return wrapper;
  }
  function syncSampleRequirements(card, assay) {
    if (assay !== "chipseq") return;
    setRequired(card.querySelector('[data-key="fastq_2"]'), card.querySelector('[data-key="layout"]').value === "paired");
    setRequired(card.querySelector('[data-key="control_id"]'), !card.querySelector('[data-key="is_control"]').checked);
  }
  function readSample(card, assay) {
    const result = {}; for (const input of card.querySelectorAll("[data-key]")) result[input.dataset.key] = input.type === "checkbox" ? input.checked : input.value.trim();
    if (assay === "rnaseq") result.layout = "paired"; return result;
  }
  function addSample(assay, initial={}) { rows[assay].push({id:crypto.randomUUID(), initial}); renderSamples(assay); }
  function renderSamples(assay) {
    const target = $(`${assay === "rnaseq" ? "rna" : "chip"}-samples`);
    const saved = new Map([...target.querySelectorAll(".sample-card")].map((card) => [card.dataset.id, readSample(card, assay)])); target.replaceChildren();
    rows[assay].forEach((row, index) => {
      const data = saved.get(row.id) || row.initial, card = element("article", "", "sample-card"); card.dataset.id = row.id;
      const heading = element("div", "", "sample-heading"), remove = element("button", "Remover"); heading.append(element("strong", `${assay === "rnaseq" ? "RNA" : "ChIP"} · amostra ${index + 1}`));
      remove.type = "button"; remove.addEventListener("click", () => { rows[assay] = rows[assay].filter((item) => item.id !== row.id); renderSamples(assay); }); heading.append(remove); card.append(heading);
      const fields = element("div", "", "sample-fields");
      if (assay === "rnaseq") fields.append(inputField("Dataset", "dataset", data.dataset || "dataset1"), inputField("Sample ID", "sample_id", data.sample_id), inputField("Run accession", "run_accession", data.run_accession), inputField("FASTQ R1", "fastq_1", data.fastq_1), inputField("FASTQ R2", "fastq_2", data.fastq_2), inputField("Condição", "condition", data.condition), inputField("Batch", "batch", data.batch || "batch1"), inputField("Replicata", "replicate", data.replicate || "1"));
      else {
        fields.append(inputField("Sample ID", "sample_id", data.sample_id), inputField("FASTQ R1", "fastq_1", data.fastq_1), inputField("FASTQ R2", "fastq_2", data.fastq_2));
        const layout = document.createElement("label"), select = document.createElement("select"); layout.textContent = "Layout"; select.dataset.key = "layout";
        for (const optionValue of ["paired", "single"]) { const option = new Option(optionValue === "paired" ? "Paired-end" : "Single-end", optionValue); option.selected = optionValue === (data.layout || "paired"); select.add(option); } layout.append(select); fields.append(layout);
        fields.append(inputField("Mark / fator", "mark_or_factor", data.mark_or_factor), inputField("Condição", "condition", data.condition), inputField("É controle/Input", "is_control", data.is_control, "checkbox"), inputField("Control ID", "control_id", data.control_id, "text", false), inputField("Batch", "batch", data.batch || "batch1"), inputField("Replicata", "replicate", data.replicate || "1"));
      }
      card.append(fields); target.append(card);
      for (const input of fields.querySelectorAll("[data-key]")) setRequired(input, input.required);
      if (assay === "chipseq") { syncSampleRequirements(card, assay); card.querySelector('[data-key="layout"]').addEventListener("change", () => syncSampleRequirements(card, assay)); card.querySelector('[data-key="is_control"]').addEventListener("change", () => syncSampleRequirements(card, assay)); }
    });
  }
  const sampleValues = (assay) => [...$(`${assay === "rnaseq" ? "rna" : "chip"}-samples`).querySelectorAll(".sample-card")].map((card) => readSample(card, assay));
  async function importTsv(file, assay) {
    if (!file || file.size > 2 * 1024 * 1024) throw new Error("Use metadata TSV de até 2 MiB.");
    const lines = (await file.text()).replace(/\r\n/g, "\n").split("\n").filter((line) => line.trim());
    if (lines.length < 2 || lines.length > 1001) throw new Error("A metadata deve ter cabeçalho e até 1.000 amostras.");
    const headers = lines[0].split("\t"); rows[assay] = lines.slice(1).map((line) => ({id:crypto.randomUUID(), initial:Object.fromEntries(headers.map((header, index) => [header, line.split("\t")[index] || ""]))}));
    renderSamples(assay); message(`${rows[assay].length} amostras importadas. Revise as células antes de continuar.`);
  }
  function plan() {
    const selected = workflow(), numerator = value("new-numerator"), denominator = value("new-denominator");
    return {name:value("new-name"), workflow:selected, clone:{mode:cloneMode(), path:value("new-repo"), repository:value("new-repository"), ref:value("new-ref")},
      storage:{project_root:value("new-project-root"), launch:value("new-launch"), output:value("new-output"), work:value("new-work")}, runtime:{partition:value("new-partition"), account:value("new-account"), profile:value("new-runtime"), memory:value("new-memory"), hours:value("new-hours")},
      organism:{name:value("new-organism"), reference_id:value("new-reference-id"), genome_fasta:value("new-genome"), transcriptome_fasta:value("new-transcriptome"), annotation:value("new-annotation"), blacklist:value("new-blacklist")},
      science:{quantification:value("new-quantification"), peak_type:value("new-peak-type"), effective_genome_size:value("new-effective-genome-size"), consensus_method:value("new-consensus-method"), idr:$("new-idr").checked},
      rnaseq_samples:["rnaseq", "all"].includes(selected) ? sampleValues("rnaseq") : [], chipseq_samples:["chipseq", "all"].includes(selected) ? sampleValues("chipseq") : [],
      statistics:{variable:value("new-variable"), covariates:value("new-covariates").split(",").map((item) => item.trim()).filter(Boolean), formula:value("new-formula"), alpha:value("new-alpha"), lfc_threshold:value("new-lfc"), min_replicates:value("new-min-replicates"), genes:value("new-genes").split(",").map((item) => item.trim()).filter(Boolean), contrasts:selected !== "integrative" || numerator || denominator ? [{numerator, denominator}] : []},
      integration:{rna_manifest:value("new-rna-manifest"), chip_manifest:value("new-chip-manifest"), policy_mode:value("new-policy-mode"), policy_paths:{harmonization:value("new-policy-harmonization"), interpretation:value("new-policy-interpretation"), mark_roles:value("new-policy-mark-roles"), prioritization_context:value("new-policy-prioritization"), functional_annotation:value("new-policy-functional")}}};
  }
  const fieldMap = {host:"host", name:"new-name", "clone.path":"new-repo", "clone.ref":"new-ref", rnaseq_samples:"rna-add", chipseq_samples:"chip-add", "storage.project_root":"new-project-root", "storage.launch":"new-launch", "storage.output":"new-output", "storage.work":"new-work", "runtime.profile":"new-runtime", "runtime.partition":"new-partition", "runtime.account":"new-account", "runtime.memory":"new-memory", "runtime.hours":"new-hours", "organism.name":"new-organism", "organism.reference_id":"new-reference-id", "organism.genome_fasta":"new-genome", "organism.transcriptome_fasta":"new-transcriptome", "organism.annotation":"new-annotation", "organism.blacklist":"new-blacklist", "science.quantification":"new-quantification", "science.peak_type":"new-peak-type", "science.effective_genome_size":"new-effective-genome-size", "science.consensus_method":"new-consensus-method", "science.idr":"new-idr", "statistics.variable":"new-variable", "statistics.covariates":"new-covariates", "statistics.formula":"new-formula", "statistics.alpha":"new-alpha", "statistics.lfc_threshold":"new-lfc", "statistics.min_replicates":"new-min-replicates", "statistics.contrasts.0.numerator":"new-numerator", "statistics.contrasts.0.denominator":"new-denominator", "integration.rna_manifest":"new-rna-manifest", "integration.chip_manifest":"new-chip-manifest", "integration.policy_mode":"new-policy-mode", "integration.policy_paths.harmonization":"new-policy-harmonization", "integration.policy_paths.interpretation":"new-policy-interpretation", "integration.policy_paths.mark_roles":"new-policy-mark-roles", "integration.policy_paths.prioritization_context":"new-policy-prioritization", "integration.policy_paths.functional_annotation":"new-policy-functional"};
  function fieldTarget(field) {
    const sample = /^(rnaseq|chipseq)_samples\.(\d+)\.([a-z0-9_]+)$/.exec(field);
    if (sample) return $(`${sample[1] === "rnaseq" ? "rna" : "chip"}-samples`).querySelectorAll(".sample-card")[+sample[2]]?.querySelector(`[data-key="${sample[3]}"]`);
    return $(fieldMap[field]);
  }
  function fieldStep(field) {
    if (field === "host") return 0;
    if (field.startsWith("clone.")) return 1;
    if (/^(rnaseq|chipseq)_samples(?:\.|$)/.test(field) || field.startsWith("integration.") && field.endsWith("_manifest")) return 3;
    if (field.startsWith("organism.")) return 4;
    if (field.startsWith("science.") || field.startsWith("statistics.") || field.startsWith("integration.policy")) return 5;
    if (field === "name" || field.startsWith("storage.") || field.startsWith("runtime.")) return 6;
    return step;
  }
  function showFieldError(error) {
    const field = error.code?.startsWith("invalid:") ? error.code.slice(8) : "", target = fieldTarget(field);
    if (target) { step = fieldStep(field); showStep(); target.setAttribute("aria-invalid", "true"); target.focus(); }
    message(error.message, true);
  }
  function reportMissing(field) {
    const error = new Error(requiredFieldMessage(field)); error.code = "invalid:" + field; showFieldError(error); return false;
  }
  function requireValue(field) { const target = fieldTarget(field); return target && (target.type === "checkbox" ? target.checked : target.value.trim()) ? true : reportMissing(field); }
  function validateSampleFields(assay) {
    const cards = [...$(`${assay === "rnaseq" ? "rna" : "chip"}-samples`).querySelectorAll(".sample-card")];
    if (!cards.length) return reportMissing(`${assay}_samples`);
    for (let index = 0; index < cards.length; index++) {
      const prefix = `${assay}_samples.${index}.`, card = cards[index], required = assay === "rnaseq" ? ["dataset", "sample_id", "run_accession", "fastq_1", "fastq_2", "condition", "batch", "replicate"] : ["sample_id", "fastq_1", "condition", "batch", "replicate", "mark_or_factor"];
      if (assay === "chipseq" && card.querySelector('[data-key="layout"]').value === "paired") required.push("fastq_2");
      if (assay === "chipseq" && !card.querySelector('[data-key="is_control"]').checked) required.push("control_id");
      for (const key of required) if (!card.querySelector(`[data-key="${key}"]`).value.trim()) return reportMissing(prefix + key);
    }
    return true;
  }
  function validateCurrentStep() {
    const selected = workflow();
    if (step === 0) return requireValue("host");
    if (step === 1) return requireValue("clone.path") && (cloneMode() !== "new" || requireValue("clone.ref"));
    if (step === 3) {
      if (["rnaseq", "all"].includes(selected) && !validateSampleFields("rnaseq")) return false;
      if (["chipseq", "all"].includes(selected) && !validateSampleFields("chipseq")) return false;
      if (selected === "integrative" && (!requireValue("integration.rna_manifest") || !requireValue("integration.chip_manifest"))) return false;
    }
    if (step === 4 && selected !== "integrative") {
      for (const field of ["organism.name", "organism.reference_id", "organism.annotation"]) if (!requireValue(field)) return false;
      if (["rnaseq", "all"].includes(selected) && !requireValue("organism.transcriptome_fasta")) return false;
      if ((["chipseq", "all"].includes(selected) || value("new-quantification") === "star") && !requireValue("organism.genome_fasta")) return false;
    }
    if (step === 5) {
      if (["chipseq", "all"].includes(selected) && !requireValue("science.effective_genome_size")) return false;
      if (selected !== "integrative") for (const field of ["statistics.variable", "statistics.formula", "statistics.alpha", "statistics.lfc_threshold", "statistics.min_replicates", "statistics.contrasts.0.numerator", "statistics.contrasts.0.denominator"]) if (!requireValue(field)) return false;
      if (["integrative", "all"].includes(selected) && value("new-policy-mode") === "custom") for (const field of ["integration.policy_paths.harmonization", "integration.policy_paths.interpretation", "integration.policy_paths.mark_roles", "integration.policy_paths.prioritization_context", "integration.policy_paths.functional_annotation"]) if (!requireValue(field)) return false;
    }
    if (step === 6) for (const field of ["name", "storage.project_root", "storage.launch", "storage.output", "storage.work", "runtime.partition", "runtime.memory", "runtime.hours"]) if (!requireValue(field)) return false;
    return true;
  }
  function renderReview(data) {
    preparationToken = data.review_token; $("document-list").replaceChildren();
    data.documents.forEach((document, index) => { const button = element("button", document.relative_path); button.type = "button"; button.addEventListener("click", () => { $("document-preview").textContent = document.content; for (const item of $("document-list").children) item.removeAttribute("aria-current"); button.setAttribute("aria-current", "true"); }); $("document-list").append(button); if (index === 0) button.click(); });
    $("preflight-results").replaceChildren(); const p = data.preflight;
    const checks = {"Clone HelixForge":`${p.clone.ref} · ${p.clone.commit.slice(0, 12)}${p.clone.dirty ? " · alterações locais" : ""}`, Java:p.java, Nextflow:p.nextflow, Slurm:`partição ${p.partition} · conta ${p.account}`, Armazenamento:p.storage, Entradas:`${p.inputs} arquivos legíveis`, Documentos:`${p.documents} novos arquivos`};
    for (const [label, result] of Object.entries(checks)) { const card = element("div", "", "preflight-card"); card.append(element("span", "✓", "check-mark"), element("strong", label), element("small", result)); $("preflight-results").append(card); }
  }
  async function reviewPreparation() {
    setBusy(true, "Validando documentos, entradas e ambiente remoto…");
    try { const data = await api("/api/preparation/review", {connection:connection(), plan:plan()}); renderReview(data); step = 7; furthest = 8; message("Preflight concluído. Revise cada documento antes de criar os arquivos."); }
    catch (error) { showFieldError(error); throw error; } finally { setBusy(false); }
  }
  $("clone-check").addEventListener("click", async () => {
    if (busy || !validateCurrentStep()) return; setBusy(true, "Verificando o clone e a referência no servidor…");
    try { const clone = {mode:cloneMode(), path:value("new-repo"), repository:value("new-repository"), ref:value("new-ref")}, data = await api("/api/clone/review", {connection:connection(), clone}), info = data.inspection; cloneToken = data.review_token || null;
      $("clone-result").hidden = false; $("clone-result").replaceChildren(element("strong", info.state === "available" ? `${info.ref} · ${info.commit.slice(0, 12)}` : `Referência fixada · ${info.commit.slice(0, 12)}`), element("span", info.state === "available" ? `${info.dirty ? "Há alterações locais; elas serão preservadas. · " : ""}Origem: ${info.origin}` : info.command));
      cloneReady = info.state === "available"; $("clone-create").hidden = !cloneToken; message(cloneReady ? "Clone verificado." : "Revise o comando e confirme a criação do clone.");
    } catch (error) { showFieldError(error); } finally { setBusy(false); }
  });
  $("clone-create").addEventListener("click", async () => {
    if (!cloneToken || busy) return; setBusy(true, "Criando o clone confirmado no servidor…");
    try { const info = await api("/api/clone/create", {review_token:cloneToken}); cloneToken = null; cloneReady = true; $("clone-create").hidden = true; $("clone-result").replaceChildren(element("strong", `${info.ref} · ${info.commit.slice(0, 12)}`), element("span", "Clone criado sem alterar outros diretórios.")); message("Clone criado e verificado."); }
    catch (error) { cloneToken = null; showFieldError(error); } finally { setBusy(false); }
  });
  $("wizard-next").addEventListener("click", async () => {
    if (busy) return; message("");
    if (!validateCurrentStep()) { if (step === 0) $("connection-settings").open = true; return; }
    if (step === 1 && !cloneReady) return message("Verifique o clone antes de continuar.", true);
    if (step === 6) { try { await reviewPreparation(); } catch { return; } } else { step++; furthest = Math.max(furthest, step); showStep(); }
  });
  $("wizard-back").addEventListener("click", () => { if (!busy && step > 0) { step--; showStep(); } }); $("new-form").addEventListener("submit", (event) => event.preventDefault());
  $("new-form").addEventListener("input", (event) => event.target.removeAttribute?.("aria-invalid"));
  $("rna-add").addEventListener("click", () => addSample("rnaseq")); $("chip-add").addEventListener("click", () => addSample("chipseq"));
  $("rna-import").addEventListener("change", async () => { try { await importTsv($("rna-import").files[0], "rnaseq"); } catch (error) { showFieldError(error); } $("rna-import").value = ""; });
  $("chip-import").addEventListener("change", async () => { try { await importTsv($("chip-import").files[0], "chipseq"); } catch (error) { showFieldError(error); } $("chip-import").value = ""; });
  for (const input of document.querySelectorAll('input[name="workflow"]')) input.addEventListener("change", () => { preparationToken = null; updateWorkflow(); });
  $("new-policy-mode").addEventListener("change", () => { $("custom-policy-fields").hidden = value("new-policy-mode") !== "custom"; preparationToken = null; updateWorkflow(); });
  $("new-quantification").addEventListener("change", () => { updateWorkflow(); preparationToken = null; });
  for (const input of document.querySelectorAll('input[name="clone-mode"]')) input.addEventListener("change", () => { cloneReady = false; cloneToken = null; $("clone-new-fields").hidden = cloneMode() !== "new"; $("clone-result").hidden = true; $("clone-create").hidden = true; updateWorkflow(); });
  for (const id of ["new-repo", "new-ref"]) $(id).addEventListener("input", () => { cloneReady = false; cloneToken = null; });
  $("preparation-write").addEventListener("click", async () => {
    if (!preparationToken || busy) return; setBusy(true, "Criando os documentos de forma atômica no servidor…");
    try { const written = await api("/api/preparation/write", {review_token:preparationToken}); preparationToken = null; const reviewed = await api("/api/submission/prepare", {connection:written.connection, draft:written.draft}); submissionToken = reviewed.review_token;
      $("write-result").replaceChildren(element("strong", `${written.documents.length} documentos criados`), element("span", written.project_root)); $("new-command").textContent = reviewed.preflight.command; step = 9; furthest = 9; message("Arquivos criados e submissão validada. Confira o comando final."); showStep();
    } catch (error) { preparationToken = null; showFieldError(error); } finally { setBusy(false); }
  });
  $("new-submit").addEventListener("click", async () => { if (!submissionToken || busy) return; setBusy(true, "Enviando o job coordenador ao Slurm…"); try { const data = await api("/api/submission/submit", {review_token:submissionToken}); submissionToken = null; window.registerSubmittedExecution(data); message(`Job ${data.job_id} enviado e registrado.`); } catch (error) { submissionToken = null; showFieldError(error); } finally { setBusy(false); } });
  $("new-copy").addEventListener("click", async () => { try { await navigator.clipboard.writeText($("new-command").textContent); message("Comando copiado."); } catch { message("Não foi possível copiar automaticamente.", true); } });
  for (const id of ["host", "user", "port", "control_path"]) $(id).addEventListener("input", (event) => { event.target.removeAttribute("aria-invalid"); cloneReady = false; showStep(); });
  addSample("rnaseq"); addSample("chipseq", {is_control:true, mark_or_factor:"input", condition:"control"}); showStep();
})();
