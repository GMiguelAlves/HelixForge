"use strict";
function executionRegression(previous, current) {
  if (previous.fingerprint && current.fingerprint && previous.fingerprint !== current.fingerprint) {
    return {code:"identity", message:"A identidade do diretório mudou."};
  }
  if (previous.trace_found && !current.trace_found) {
    return {code:"missing", message:"O trace anterior não está mais disponível."};
  }
  if (previous.health?.trace?.state === "available" && current.health?.trace?.state === "partial") {
    return {code:"partial", message:"O trace atual terminou com um registro incompleto."};
  }
  const oldInventory = previous.artifact_details?.map((item) => item.path) || previous.artifacts;
  const newInventory = current.artifact_details?.map((item) => item.path) || current.artifacts;
  const currentFiles = new Set(newInventory);
  const missing = oldInventory.filter((path) => !currentFiles.has(path));
  return missing.length ? {code:"missing", message:`${missing.length} arquivo(s) do snapshot anterior desapareceram.`} : null;
}
function preserveExecutionSnapshot(run, reason, checkedAt) {
  const entry = {checked_at:checkedAt, state:"stale", reason, tasks:run.data.tasks.length,
                 artifacts:run.data.artifacts.length, health:run.data.health || null};
  return {...run, availability:{state:"stale", reason, checked_at:checkedAt},
          history:[entry, ...(run.history || [])].slice(0, 10)};
}
function findCurrentSlurmJob(task, runConnection, activeConnection, queue) {
  const fields = ["host", "user", "port", "control_path"];
  if (!task?.native_id || !runConnection || !activeConnection || !queue ||
      !fields.every((field) => (runConnection[field] || "") === (activeConnection[field] || ""))) return null;
  return queue.jobs?.find((job) => job.id === task.native_id) || null;
}
function removeExecutionLocally(runs, id) {
  return {removed:runs.find((run) => run.id === id) || null, remaining:runs.filter((run) => run.id !== id)};
}
function restoreExecutionLocally(runs, removed) {
  return removed && !runs.some((run) => run.id === removed.id) ? [removed, ...runs] : runs;
}
if (typeof module !== "undefined") module.exports = {executionRegression, preserveExecutionSnapshot, findCurrentSlurmJob,
  removeExecutionLocally, restoreExecutionLocally};
