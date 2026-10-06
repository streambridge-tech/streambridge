import { insertBlank, ui } from "./store.js";
import { renderHome } from "./pages/home.js";
import { renderFolder } from "./pages/folder.js";
import { renderEditor, bindEditor } from "./pages/editor.js";
import { openFolderModal } from "./pages/modal.js";
import { go } from "./router.js";

export function renderDetail() {
  const root = document.getElementById("cfgDetail");
  if (!root) return;
  const sel = ui.selection;
  ui.validate = sel.kind === "editor" ? ui.validate : null;
  if (sel.kind === "folder") root.innerHTML = renderFolder(sel);
  else if (sel.kind === "editor") root.innerHTML = renderEditor(sel);
  else root.innerHTML = renderHome();

  if (sel.kind === "editor") bindEditor(root);

  root.querySelectorAll("[data-new-folder]").forEach((el) => {
    el.addEventListener("click", () => openFolderModal({ parent: el.getAttribute("data-new-folder") || "" }));
  });
  root.querySelectorAll("[data-new-config]").forEach((el) => {
    el.addEventListener("click", () => {
      const record = insertBlank({ folder: el.getAttribute("data-new-config") || "default", pluginId: "blank" });
      go({ kind: "editor", id: record.id });
    });
  });

  root.querySelectorAll("[data-href]").forEach((el) => {
    el.addEventListener("click", (event) => {
      const href = el.getAttribute("data-href");
      if (!href || href.startsWith("http") || href.startsWith("/")) return;
      event.preventDefault();
      location.hash = href.startsWith("#") ? href : `#${href}`;
    });
  });
}
