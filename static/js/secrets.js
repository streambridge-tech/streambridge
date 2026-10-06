/** Connections Secrets. Persists named bags to /api/secrets. Tokens: `{bag.key}`. */
(function (global) {
  const bags = [];

  function secretRe() {
    return /\{([A-Za-z_][A-Za-z0-9_-]*)\.([A-Za-z_][A-Za-z0-9_]*)\}/g;
  }

  function fromPublic(vault) {
    return {
      name: vault.name,
      vars: (vault.vars || []).map(function (row) {
        return {
          key: row.key || "",
          value: row.masked ? "" : (row.value || ""),
          secret: Boolean(row.masked),
          hasValue: Boolean(row.hasValue),
        };
      }),
    };
  }

  function replaceBags(list) {
    bags.length = 0;
    (list || []).forEach(function (vault) {
      bags.push(fromPublic(vault));
    });
  }

  function byName(name) {
    return bags.find(function (b) { return b.name === name; });
  }

  function jsonError(res, body, fallback) {
    const msg = (body && body.error) || fallback || ("HTTP " + res.status);
    const err = new Error(msg);
    err.status = res.status;
    return err;
  }

  function refresh() {
    return fetch("/api/secrets")
      .then(function (res) {
        return res.json().then(function (body) { return { res: res, body: body }; });
      })
      .then(function (out) {
        if (!out.res.ok) throw jsonError(out.res, out.body, "Could not load secrets");
        replaceBags(out.body);
      });
  }

  function insert(name) {
    return fetch("/api/secrets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: String(name || "").trim() }),
    }).then(function (res) {
      return res.json().then(function (body) { return { res: res, body: body }; });
    }).then(function (out) {
      if (!out.res.ok) throw jsonError(out.res, out.body, "Could not create secret bag");
      const bag = fromPublic(out.body);
      bags.push(bag);
      return bag;
    });
  }

  function remove(name) {
    return fetch("/api/secrets/" + encodeURIComponent(name), { method: "DELETE" })
      .then(function (res) {
        return res.json().then(function (body) { return { res: res, body: body }; }).catch(function () {
          return { res: res, body: {} };
        });
      })
      .then(function (out) {
        if (!out.res.ok) throw jsonError(out.res, out.body, "Could not delete secret bag");
        const index = bags.findIndex(function (b) { return b.name === name; });
        if (index >= 0) bags.splice(index, 1);
      });
  }

  function persist(name) {
    const bag = byName(name);
    if (!bag) return Promise.reject(new Error("Secret bag not found"));
    const vars = (bag.vars || []).map(function (row) {
      const payload = { key: row.key || "", masked: Boolean(row.secret) };
      // A masked row loaded from the server has hasValue but an empty local value.
      // Omit that so the stored secret stays. A value typed in this session is still
      // on the row and must be sent, or the first masked save stores nothing.
      const alreadyStored = Boolean(row.secret && row.hasValue && !row.replacing && !row.value);
      if (!alreadyStored) payload.value = row.value || "";
      return payload;
    });
    return fetch("/api/secrets/" + encodeURIComponent(bag.name), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vars: vars }),
    }).then(function (res) {
      return res.json().then(function (body) { return { res: res, body: body }; });
    }).then(function (out) {
      if (!out.res.ok) throw jsonError(out.res, out.body, "Could not save secrets");
      const next = fromPublic(out.body);
      bag.vars = next.vars;
      return bag;
    });
  }

  function lookup(parent, key) {
    const row = (byName(parent)?.vars || []).find(function (v) { return v.key === key; });
    if (!row || row.secret) return undefined;
    return row.value;
  }

  function secretRef(parent, key) {
    return "{" + parent + "." + key + "}";
  }

  function collect(text) {
    const refs = [];
    String(text ?? "").replace(secretRe(), function (_, parent, key) {
      refs.push({ parent: parent, key: key, ref: secretRef(parent, key) });
      return "";
    });
    return refs;
  }

  function isSecretOnly(value) {
    const s = String(value ?? "").trim();
    if (!s) return false;
    return s.replace(secretRe(), "").trim() === "";
  }

  function resolve(text, missing) {
    const miss = missing || [];
    return String(text ?? "").replace(secretRe(), function (match, parent, key) {
      const found = lookup(parent, key);
      if (found === undefined) {
        miss.push(parent + "." + key);
        return match;
      }
      return found;
    });
  }

  function listRefs() {
    const out = [];
    bags.forEach(function (bag) {
      (bag.vars || []).forEach(function (row) {
        const key = String(row.key || "").trim();
        if (key) out.push({ parent: bag.name, key: key, ref: secretRef(bag.name, key), secret: row.secret });
      });
    });
    return out;
  }

  global.StreamBridgeSecrets = {
    bags: bags,
    byName: byName,
    insert: insert,
    remove: remove,
    persist: persist,
    refresh: refresh,
    lookup: lookup,
    secretRef: secretRef,
    collect: collect,
    isSecretOnly: isSecretOnly,
    resolve: resolve,
    listRefs: listRefs,
  };
})(typeof window !== "undefined" ? window : globalThis);
