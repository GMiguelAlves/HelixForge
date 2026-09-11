"use strict";
(() => {
  const key = "helixforge.connections.v1";
  const fields = ["host", "user", "port", "control_path"];
  let profiles = [], editing = null, working = false, damaged = false;
  const results = new Map();
  const current = () => Object.fromEntries(fields.map((id) => [id, $(id).value.trim()]));
  const same = (a, b) => fields.every((field) => (a[field] || "") === (b[field] || ""));
  const message = (text) => { $("profile-message").textContent = text; };
  function persist(next) {
    if (damaged) throw new Error("O histórico de conexões está inválido e foi preservado. Não foi possível salvar alterações.");
    localStorage.setItem(key, JSON.stringify(next)); profiles = next;
  }
  try {
    const stored = localStorage.getItem(key);
    const saved = JSON.parse(stored || "[]");
    if (!Array.isArray(saved) || saved.some((p) => typeof p.id !== "string" || typeof p.name !== "string" || !p.config || fields.some((field) => typeof p.config[field] !== "string"))) throw new Error("invalid");
    profiles = saved;
    if (stored === null && current().host) persist([{id:crypto.randomUUID(), name:current().host, config:current()}]);
  } catch { damaged = true; message("Não foi possível ler ou salvar os perfis neste navegador. A configuração atual continua disponível no topo da página."); }

  function use(profile) {
    if (busy || working) { message("Aguarde a consulta em andamento."); return false; }
    selectConnection(profile.config);
    try { if ($("remember").checked) localStorage.setItem(storageKey, JSON.stringify(profile.config)); }
    catch { message("Destino selecionado, mas não foi possível salvar a preferência."); }
    $("connection-settings").open = false;
    render();
    return true;
  }
  function form(profile = null) {
    if (working) return;
    editing = profile?.id || null;
    $("profile-form").reset();
    $("profile-name").value = profile?.name || "";
    for (const field of fields) $("profile-" + field).value = profile?.config[field] || "";
    $("profile-form-title").textContent = profile ? "Editar conexão" : "Nova conexão";
    $("profile-form").hidden = false;
    $("profile-name").focus();
  }
  function render() {
    $("profiles-list").replaceChildren();
    $("profiles-empty").hidden = profiles.length > 0;
    for (const profile of profiles) {
      const selected = same(profile.config, current());
      const row = element("article", "", "profile-row" + (selected ? " profile-selected" : ""));
      row.setAttribute("aria-label", profile.name);
      const heading = element("div", "", "profile-heading");
      heading.append(element("h2", profile.name), element("span", selected ? "Destino selecionado" : "Perfil salvo", "draft-label"));
      const address = `${profile.config.user ? profile.config.user + "@" : ""}${profile.config.host}${profile.config.port ? ":" + profile.config.port : ""}`;
      const result = results.get(profile.id);
      row.append(heading, element("p", address, "profile-address"), element("p", profile.config.control_path ? "Socket: " + profile.config.control_path : "Autenticação pelo SSH configurado", "profile-meta"), element("p", result || "Acesso ainda não testado nesta sessão.", "profile-result"));
      const actions = element("div", "", "form-actions");
      const choose = element("button", "Usar conexão"); choose.disabled = working || busy || selected;
      choose.addEventListener("click", () => { if (use(profile)) message(`Destino selecionado: ${profile.name}. Teste o acesso para consultar os jobs.`); });
      const test = element("button", working ? "Aguarde…" : "Testar acesso"); test.disabled = working || busy;
      test.addEventListener("click", async () => {
        if (!use(profile)) return;
        working = true; render(); message(`Testando ${profile.name}…`);
        connection = {...profile.config};
        try {
          await refresh(true);
          const stamp = new Date().toLocaleString("pt-BR");
          const result = snapshot && $("error").hidden ? `Teste em ${stamp}: acesso confirmado · ${snapshot.user} · ${snapshot.jobs.length} jobs na consulta.` : `Teste em ${stamp}: ${$("error").textContent || "Não foi possível consultar o servidor."}`;
          results.set(profile.id, result); message(result);
        } finally { working = false; render(); }
      });
      const edit = element("button", "Editar"); edit.disabled = working || busy; edit.addEventListener("click", () => form(profile));
      const remove = element("button", "Excluir perfil"); remove.disabled = working || busy;
      remove.addEventListener("click", () => {
        if (busy || working) return;
        try {
          persist(profiles.filter((item) => item.id !== profile.id)); results.delete(profile.id);
          if (editing === profile.id) { editing = null; $("profile-form").hidden = true; }
          message("Perfil excluído. A conexão atual e as execuções cadastradas foram mantidas."); render();
        } catch { message("Não foi possível excluir o perfil do armazenamento local."); }
      });
      actions.append(choose, test, edit, remove); row.append(actions); $("profiles-list").append(row);
    }
    $("profile-new").disabled = working;
    $("profile-save").disabled = working;
    $("profile-cancel").disabled = working;
  }
  $("profile-new").addEventListener("click", () => form());
  $("profile-cancel").addEventListener("click", () => { editing = null; $("profile-form").hidden = true; });
  $("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || working) return message("Aguarde a consulta em andamento.");
    const name = $("profile-name").value.trim();
    if (!name) return message("Informe um nome para a conexão.");
    working = true; render();
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const config = Object.fromEntries(fields.map((field) => [field, $("profile-" + field).value.trim()]));
      const response = await fetch("/api/connection", {method:"POST", headers:{"Content-Type":"application/json", "X-HelixForge-Token":token}, body:JSON.stringify(config), signal:controller.signal});
      const data = await response.json(); if (!response.ok) throw new Error(data.error || "Configuração inválida.");
      if (profiles.some((profile) => profile.id !== editing && same(profile.config, data.connection))) throw new Error("Essa conexão já está salva em outro perfil.");
      const old = profiles.find((profile) => profile.id === editing);
      const profile = {id:editing || crypto.randomUUID(), name, config:data.connection};
      persist(old ? profiles.map((item) => item.id === old.id ? profile : item) : [...profiles, profile]);
      results.delete(profile.id);
      if (old && same(old.config, current())) {
        selectConnection(profile.config);
        try { if ($("remember").checked) localStorage.setItem(storageKey, JSON.stringify(profile.config)); } catch { /* Profile is already saved. */ }
      }
      $("profile-form").hidden = true; editing = null;
      message("Conexão salva. Use “Testar acesso” para verificar o SSH e o Slurm.");
    } catch (error) { message(error.name === "AbortError" ? "O serviço local demorou a responder." : error.message); }
    finally { clearTimeout(timeout); working = false; render(); $("profile-message").scrollIntoView({block:"center"}); }
  });
  document.addEventListener("connection-updated", render);
  for (const field of fields) $(field).addEventListener("input", render);
  window.addEventListener("hashchange", render);
  render();
})();
