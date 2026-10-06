from __future__ import annotations

from datetime import datetime, timezone
import json

from app.models.connector_notebook import ConnectorNotebook


class NotebookStore:
    """Map Connectors-page payloads onto the notebook row."""

    def apply(self, notebook: ConnectorNotebook, data: dict) -> str | None:
        if "name" in data:
            name = str(data.get("name") or "").strip()
            if not name:
                return "Name is required"
            notebook.name = name[:128]
        if "folder" in data:
            notebook.folder = (str(data.get("folder") or "default").strip() or "default")[:256]
        if "attachedCluster" in data:
            notebook.attached_cluster = str(data.get("attachedCluster") or "")[:128]
        if "pluginId" in data:
            notebook.plugin_id = str(data.get("pluginId") or "blank")[:128]
        if "level" in data:
            notebook.level = str(data.get("level") or "starter")[:32]
        if "type" in data:
            notebook.connector_type = str(data.get("type") or "expert")[:32]
        if "notes" in data:
            notebook.notes = data.get("notes") or ""
        if "doc" in data:
            doc = data.get("doc")
            if not isinstance(doc, dict):
                return "doc must be an object"
            if notebook.name:
                doc = {**doc, "name": notebook.name}
            notebook.doc_json = json.dumps(doc, separators=(",", ":"))
        if "lineage" in data:
            lineage = data.get("lineage") or {"dependsOn": []}
            if not isinstance(lineage, dict):
                return "lineage must be an object"
            notebook.lineage_json = json.dumps(lineage, separators=(",", ":"))
        if "connections" in data:
            binds = data.get("connections") or {}
            if not isinstance(binds, dict):
                return "connections must be an object"
            notebook.connections_json = json.dumps(binds, separators=(",", ":"))
        notebook.updated_at = datetime.now(timezone.utc)
        return None
