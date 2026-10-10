import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { SourceTextModule, SyntheticModule } from "node:vm";

const source = await readFile(new URL("../../static/js/configs/pages/modal.js", import.meta.url), "utf8");

let previousDocument;
let previousWindow;

function restoreGlobals() {
  globalThis.document = previousDocument;
  globalThis.window = previousWindow;
}

function harness(outcome) {
  const record = { id: "original", name: "source", folder: "old", doc: { name: "source" } };
  const configs = [record];
  const requests = [];
  const notifications = [];
  const routes = [];
  const events = [];
  const controls = {
    "#cfgOk": { disabled: false },
    "#cfgCancel": {},
    "#cfgCloneName": { value: "source-copy" },
    "#cfgCloneFolder": { value: "new" },
    "#cfgMoveFolder": { value: "new" },
  };
  const root = { hidden: true, innerHTML: "", querySelector: selector => controls[selector] };
  const ui = { expanded: new Set(), savedClone: {} };
  let resolveSave;
  const save = new Promise(resolve => { resolveSave = resolve; });
  const store = {
    allFolders: () => ["old", "new"],
    cloneConfig: (original, values) => {
      const copy = { ...original, ...values, id: "copy" };
      configs.push(copy);
      ui.savedClone[copy.id] = copy;
      return copy;
    },
    configs,
    ui,
    upsertNotebook: async value => {
      requests.push({ ...value });
      await save;
      if (outcome === "network-error") throw new Error("offline");
      return outcome === "api-error" ? "rejected" : "";
    },
  };
  return {
    record, configs, requests, notifications, routes, events, controls, root, ui, resolveSave, store,
    async load() {
      const module = new SourceTextModule(source);
      await module.link(specifier => {
        const values = specifier.endsWith("store.js") ? {
          createFolder: null, deleteConfig: null, deleteFolderRemote: null,
          deployNotebook: null, folderName: null, impact: null, parentFolder: null,
          renameFolderRemote: null, topicsOf: null, downstreamOf: null, ...store,
        } : specifier.endsWith("util.js") ? {
          esc: value => value, toast: message => notifications.push(message),
        } : { go: route => routes.push(route) };
        return new SyntheticModule(Object.keys(values), function () {
          for (const [name, value] of Object.entries(values)) this.setExport(name, value);
        });
      });
      previousDocument = globalThis.document;
      previousWindow = globalThis.window;
      globalThis.document = { getElementById: () => root };
      globalThis.window = { dispatchEvent: event => events.push(event.type) };
      await module.evaluate();
      return module;
    },
  };
}

test("clone opens an unsaved draft", async () => {
  const { controls, root, notifications, routes, record, configs, ui, load, requests } = harness("success");
  const module = await load();
  try {
    module.namespace.openCloneModal(record);
    await controls["#cfgOk"].onclick();
    assert.equal(requests.length, 0);
    assert.equal(configs.length, 2);
    assert.equal(configs[1].name, "source-copy");
    assert.equal(configs[1].folder, "new");
    assert.equal(record.folder, "old");
    assert.equal(root.hidden, true);
    assert.equal(ui.expanded.has("folder:new"), true);
    assert.deepEqual(routes, [{ kind: "editor", id: "copy" }]);
    assert.deepEqual(notifications, ["Cloned as source-copy — review and Save"]);
  } finally {
    restoreGlobals();
  }
});

for (const outcome of ["success", "api-error", "network-error"]) {
  test(`move: ${outcome}`, async () => {
    const { controls, root, notifications, routes, events, record, configs, ui, load, requests, resolveSave } = harness(outcome);
    const module = await load();
    try {
      module.namespace.openMoveModal(record);
      const pending = controls["#cfgOk"].onclick();
      await controls["#cfgOk"].onclick();
      assert.equal(requests.length, 1);
      assert.equal(requests[0].folder, "new");
      assert.equal(root.hidden, false);
      assert.equal(record.folder, "old");
      assert.deepEqual(notifications, []);
      resolveSave();
      await pending;
      if (outcome === "success") {
        assert.equal(root.hidden, true);
        assert.equal(ui.expanded.has("folder:new"), true);
        assert.equal(record.folder, "new");
        assert.deepEqual(events, ["cfg-render"]);
      } else {
        assert.equal(root.hidden, false);
        assert.equal(controls["#cfgOk"].disabled, false);
        assert.equal(configs.length, 1);
        assert.equal(record.folder, "old");
        assert.deepEqual(routes, []);
        assert.deepEqual(events, []);
        assert.deepEqual(notifications, [outcome === "api-error" ? "rejected" : "offline"]);
      }
    } finally {
      restoreGlobals();
    }
  });
}
