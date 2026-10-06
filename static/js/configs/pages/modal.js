import {
  allFolders,
  cloneConfig,
  configs,
  createFolder,
  deleteConfig,
  deleteFolderRemote,
  deployNotebook,
  folderName,
  impact,
  parentFolder,
  renameFolderRemote,
  topicsOf,
  ui,
  upsertNotebook,
  downstreamOf,
} from "../store.js";
import { esc, toast } from "../util.js";
import { go } from "../router.js";

export function closeModal() {
  const root = document.getElementById("cfgModalRoot");
  if (!root) return;
  root.hidden = true;
  root.innerHTML = "";
}

export function openUnsavedModal({ onSave, onDiscard, onCancel } = {}) {
  const root = shell(`
    <h2>Unsaved changes</h2>
    <p class="cfg-hint">Do you want to keep this save?</p>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgUnsavedDiscard">Don't save</button>
      <button class="cfg-btn" type="button" id="cfgUnsavedCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-primary" type="button" id="cfgUnsavedSave">Save</button>
    </div>`);
  root.querySelector("#cfgUnsavedCancel").onclick = () => {
    closeModal();
    onCancel?.();
  };
  root.querySelector("#cfgUnsavedDiscard").onclick = () => {
    closeModal();
    onDiscard?.();
  };
  root.querySelector("#cfgUnsavedSave").onclick = () => {
    if (onSave?.() === false) return;
    closeModal();
  };
}

function shell(html) {
  const root = document.getElementById("cfgModalRoot");
  if (!root) return null;
  root.hidden = false;
  root.innerHTML = `<div class="cfg-modal">${html}</div>`;
  root.onclick = (event) => { if (event.target === root) closeModal(); };
  return root;
}

export function openFolderModal({ parent = "" } = {}) {
  const root = shell(`
    <h2>${parent ? `New folder <span class="cfg-sub">in ${esc(parent)}</span>` : "New parent folder"}</h2>
    <div class="cfg-field">
      <label class="cfg-label" for="cfgFolderName">Name</label>
      <input class="cfg-input" id="cfgFolderName" placeholder="folder name" autocomplete="off">
    </div>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgFolderCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-primary" type="button" id="cfgFolderOk">Create</button>
    </div>`);
  const input = root.querySelector("#cfgFolderName");
  input?.focus();
  root.querySelector("#cfgFolderCancel").onclick = closeModal;
  const create = async () => {
    const created = await createFolder(input?.value, parent);
    if (created.error) {
      toast(created.error);
      return;
    }
    ui.expanded.add(`folder:${created.path}`);
    if (parent) ui.expanded.add(`folder:${parent}`);
    closeModal();
    toast(`Folder ${created.path}`);
    go({ kind: "folder", folder: created.path });
  };
  root.querySelector("#cfgFolderOk").onclick = create;
  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") create();
  });
}

export function openRenameFolderModal(folder) {
  const leaf = folder.split("/").filter(Boolean).pop() || folder;
  const root = shell(`
    <h2>Rename folder</h2>
    <div class="cfg-field">
      <label class="cfg-label" for="cfgRenameFolder">Name</label>
      <input class="cfg-input" id="cfgRenameFolder" value="${esc(leaf)}" autocomplete="off">
    </div>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-primary" type="button" id="cfgOk">Rename</button>
    </div>`);
  root.querySelector("#cfgCancel").onclick = closeModal;
  root.querySelector("#cfgOk").onclick = async () => {
    const renamed = await renameFolderRemote(folder, root.querySelector("#cfgRenameFolder").value);
    if (renamed.error) {
      toast(renamed.error);
      return;
    }
    closeModal();
    toast("Folder renamed");
    go({ kind: "folder", folder: renamed.path });
  };
}

export function openDeleteFolderModal(folder) {
  const root = shell(`
    <h2>Delete ${esc(folderName(folder))}</h2>
    <p class="cfg-hint">Removes this folder and everything inside it.</p>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-danger" type="button" id="cfgOk">Delete</button>
    </div>`);
  root.querySelector("#cfgCancel").onclick = closeModal;
  root.querySelector("#cfgOk").onclick = async () => {
    const parent = parentFolder(folder);
    const err = await deleteFolderRemote(folder);
    if (err) {
      toast(err);
      return;
    }
    closeModal();
    toast("Folder deleted");
    if (parent) go({ kind: "folder", folder: parent });
    else go({ kind: "home" });
  };
}

export function openCloneModal(record) {
  const folderOpts = allFolders().map((f) => `<option${f === record.folder ? " selected" : ""}>${esc(f)}</option>`).join("");
  const root = shell(`
    <h2>Clone connector</h2>
    <p class="cfg-hint">Copies JSON, notes, lineage, and binds. Does not copy live. New name, not a revision.</p>
    <div class="cfg-field">
      <label class="cfg-label" for="cfgCloneName">New name</label>
      <input class="cfg-input" id="cfgCloneName" value="${esc(record.name)}-copy" autocomplete="off">
    </div>
    <div class="cfg-field">
      <label class="cfg-label" for="cfgCloneFolder">Folder</label>
      <select class="cfg-select" id="cfgCloneFolder">${folderOpts}</select>
    </div>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-primary" type="button" id="cfgOk">Clone</button>
    </div>`);
  root.querySelector("#cfgCancel").onclick = closeModal;
  root.querySelector("#cfgOk").onclick = () => {
    const button = root.querySelector("#cfgOk");
    if (button.disabled) return;
    // Clone opens as an unsaved draft (like a new connector); the user reviews then Saves.
    const copy = cloneConfig(record, {
      name: root.querySelector("#cfgCloneName").value,
      folder: root.querySelector("#cfgCloneFolder").value,
    });
    ui.expanded.add(`folder:${copy.folder}`);
    closeModal();
    toast(`Cloned as ${copy.name} — review and Save`);
    go({ kind: "editor", id: copy.id });
  };
}

export function openMoveModal(record) {
  const folderOpts = allFolders().map((f) => `<option${f === record.folder ? " selected" : ""}>${esc(f)}</option>`).join("");
  const root = shell(`
    <h2>Move ${esc(record.name)}</h2>
    <div class="cfg-field">
      <label class="cfg-label" for="cfgMoveFolder">Folder</label>
      <select class="cfg-select" id="cfgMoveFolder">${folderOpts}</select>
    </div>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-primary" type="button" id="cfgOk">Move</button>
    </div>`);
  root.querySelector("#cfgCancel").onclick = closeModal;
  root.querySelector("#cfgOk").onclick = async () => {
    const button = root.querySelector("#cfgOk");
    if (button.disabled) return;
    button.disabled = true;
    const moved = { ...record, folder: root.querySelector("#cfgMoveFolder").value };
    try {
      const error = await upsertNotebook(moved);
      if (error) throw new Error(error);
    } catch (error) {
      button.disabled = false;
      toast(error.message || "Could not move the connector");
      return;
    }
    Object.assign(record, moved);
    ui.expanded.add(`folder:${record.folder}`);
    closeModal();
    toast("Moved");
    window.dispatchEvent(new Event("cfg-render"));
  };
}

export function openDeleteModal(record) {
  const root = shell(`
    <h2>Delete ${esc(record.name)}</h2>
    <p class="cfg-hint">Removes the saved notebook. The live connector on the cluster is not deleted.</p>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-danger" type="button" id="cfgOk">Delete</button>
    </div>`);
  root.querySelector("#cfgCancel").onclick = closeModal;
  root.querySelector("#cfgOk").onclick = () => {
    const folder = record.folder;
    deleteConfig(record.id);
    closeModal();
    toast("Connector deleted");
    go({ kind: "folder", folder });
  };
}

export function openDeployModal(record) {
  const snap = impact(record);
  const downs = downstreamOf(record);
  const topics = topicsOf(record);
  const root = shell(`
    <h2>Deploy ${esc(record.name)}</h2>
    <p><strong>${esc(snap.action)}</strong> on ${esc(record.attachedCluster)}</p>
    <p class="cfg-hint">topics: ${esc(topics.join(", ") || "—")}</p>
    <p class="cfg-hint">downstream: ${snap.downstream}${downs.length ? ` (${esc(downs.map((d) => d.name).join(", "))})` : ""}</p>
    <p class="cfg-hint">secrets: resolve {prod.xyz} from Connections at deploy. JSON stays unresolved.</p>
    <p class="cfg-hint" id="cfgDeployStatus">Logs will show saving config, resolving secrets, then deploying connector.</p>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-primary" type="button" id="cfgOk">Deploy</button>
    </div>`);
  root.querySelector("#cfgCancel").onclick = closeModal;
  root.querySelector("#cfgOk").onclick = async () => {
    const okBtn = root.querySelector("#cfgOk");
    const cancel = root.querySelector("#cfgCancel");
    const status = root.querySelector("#cfgDeployStatus");
    okBtn.disabled = true;
    cancel.disabled = true;
    okBtn.classList.add("is-busy");
    okBtn.innerHTML = `<span class="cfg-btn-spin" aria-hidden="true"></span>Deploying`;
    if (status) status.textContent = "Saving config, resolving secrets, deploying connector…";
    const err = await deployNotebook(record);
    closeModal();
    toast(err ? `Deploy failed — ${err}` : "Deploy succeeded");
  };
}

export function openDependsModal(record) {
  const others = configs.filter((c) => c.id !== record.id);
  const opts = others.map((c) => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join("");
  const root = shell(`
    <h2>Add depends-on</h2>
    <div class="cfg-field">
      <label class="cfg-label">Connector</label>
      <select class="cfg-select" id="cfgDepName">${opts || "<option value=''>No other connectors</option>"}</select>
    </div>
    <div class="cfg-modal-actions">
      <button class="cfg-btn" type="button" id="cfgCancel">Cancel</button>
      <button class="cfg-btn cfg-btn-primary" type="button" id="cfgOk">Add</button>
    </div>`);
  root.querySelector("#cfgCancel").onclick = closeModal;
  root.querySelector("#cfgOk").onclick = () => {
    const name = root.querySelector("#cfgDepName").value;
    record.lineage = record.lineage || { dependsOn: [] };
    if (name && !record.lineage.dependsOn.some((d) => d.name === name && d.type === "connector")) {
      record.lineage.dependsOn.push({ type: "connector", name });
    }
    closeModal();
    window.dispatchEvent(new Event("cfg-render"));
  };
}
