/** Pipelines: YAML file rows, editor + runs. Mock until apply API. */
(function () {

  const SAMPLE_YAML = `pipeline:
  name: ecommerce
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    mysql_plugin: mysql-json
    s3_plugin: s3-json
    topic_prefix: ecommerce
  connector:
    "ecommerce-mysql-connector-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.port: "{mysql_port}"
        database.user: "{mysql_username}"
        database.password: "{mysql_password}"
        database.include.list: "{mysql_database}"
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{ops_slack}"
    "ecommerce-s3-connector-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: ecommerce.ecommerce.orders
        s3.bucket.name: "{s3_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
`;

  const STUB_YAML = `pipeline:
  name: {name}
  stage: development
  stages:
    development:
      vault: dev
  common:
    mysql_plugin: mysql-json
  connector:
    "{name}-connector-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
`;

  const ICO_CODE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>';
  const ICO_PLAY = '<svg viewBox="0 0 24 24"><polygon points="9 7 17 12 9 17"/></svg>';

  const PL = {
    state: {
      files: [],
      search: "",
      selected: null,
      tab: "code",
      activeJob: null,
      timers: [],
      sidebarW: 300,
      histW: 220,
      logH: 140,
    },
  };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function uid(prefix) {
    return prefix + "-" + Math.random().toString(36).slice(2, 8);
  }

  function relTime(ts) {
    const seconds = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    if (seconds < 60) return seconds + "s ago";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
    return Math.floor(seconds / 86400) + "d ago";
  }

  function statusLabel(s) {
    if (s === "ok") return "Success";
    if (s === "fail") return "Failed";
    if (s === "run") return "Running";
    return "Waiting";
  }

  function lastRun(file) {
    return (file.runs || []).slice().sort(function (a, b) { return b.n - a.n; })[0] || null;
  }

  function highlightYaml(text) {
    return String(text || "").split("\n").map(function (line) {
      const trimmed = line.trim();
      if (trimmed.charAt(0) === "#") {
        return '<span class="pl-yc">' + esc(line) + "</span>";
      }
      const m = /^(\s*)([^:#\n][^:\n]*?)(:)(\s*)(.*)$/.exec(line);
      if (m) {
        return esc(m[1])
          + '<span class="pl-yk">' + esc(m[2]) + "</span>"
          + '<span class="pl-yp">' + esc(m[3]) + "</span>"
          + esc(m[4])
          + paintValue(m[5]);
      }
      return paintValue(line);
    }).join("\n");
  }

  function paintValue(value) {
    return esc(value).replace(/\{[^}]+\}/g, function (bit) {
      return '<span class="pl-yv">' + bit + "</span>";
    });
  }

  function parseConnectorNames(yaml) {
    const names = [];
    let inConn = false;
    let base = -1;
    String(yaml || "").split("\n").forEach(function (line) {
      if (/^\s*connector:\s*$/.test(line)) {
        inConn = true;
        base = line.search(/\S/);
        return;
      }
      if (!inConn) return;
      const idx = line.search(/\S/);
      if (idx === -1) return;
      if (idx <= base) {
        inConn = false;
        return;
      }
      const m = line.match(/^\s+"([^"]+)"\s*:/);
      if (m && idx <= base + 4) names.push(m[1]);
    });
    return names;
  }

  function connectorLabel(name) {
    return String(name || "")
      .replace(/\{stage\}/g, "")
      .replace(/-connector-?/g, "-")
      .replace(/-+$/g, "")
      .replace(/^[^-]+-/, "") || name;
  }

  function connectorId(name, i) {
    const slug = String(name || "")
      .replace(/\{stage\}/g, "")
      .replace(/[^a-z0-9]+/gi, "-")
      .replace(/-+$/g, "")
      .toLowerCase();
    return slug || ("c" + i);
  }

  function jobLog(label, status) {
    if (status === "run") return label + " started";
    if (status === "wait") return "waiting";
    if (status === "fail") return label + " started\n" + label + " failed · check vault keys and plugin overlay";
    return label + " started\n" + label + " succeeded";
  }

  function jobsForYaml(yaml, status) {
    const cons = parseConnectorNames(yaml);
    const jobs = [{
      id: "generate",
      stage: "generate",
      label: "generate",
      status: status === "run" ? "run" : "ok",
      log: jobLog("generate", status === "run" ? "run" : "ok"),
    }];
    cons.forEach(function (name, i) {
      let st = "ok";
      if (status === "run") st = "wait";
      else if (status === "fail" && i === cons.length - 1) st = "fail";
      else if (status === "fail") st = "ok";
      jobs.push({
        id: connectorId(name, i),
        stage: "validate",
        label: connectorLabel(name),
        status: st,
        log: jobLog(connectorLabel(name), st),
      });
    });
    const later = status === "ok" ? "ok" : "wait";
    jobs.push({ id: "deploy", stage: "deploy", label: "deploy", status: later, log: jobLog("deploy", later) });
    jobs.push({ id: "alerts", stage: "publish", label: "alerts", status: later, log: later === "ok" ? "alerts upserted\nconfigs written" : "waiting for deploy" });
    return jobs;
  }

  function makeRuns(yaml, rows) {
    return rows.map(function (row) {
      return {
        id: uid("run"),
        n: row.n,
        stage: row.stage || "development",
        vault: row.vault || "dev",
        status: row.status,
        jobs: jobsForYaml(yaml, row.status),
        createdAt: Date.now() - row.ago,
      };
    });
  }

  function defaultJobs(status) {
    return jobsForYaml(SAMPLE_YAML, status);
  }

  function jobIcon(status) {
    if (status === "ok") {
      return '<span class="pl-gico ok" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="8"/><path d="M4.5 8.2l2.2 2.2 4.8-4.8" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span>';
    }
    if (status === "fail") {
      return '<span class="pl-gico fail" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="8"/><path d="M5.2 5.2l5.6 5.6M10.8 5.2l-5.6 5.6" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/></svg></span>';
    }
    if (status === "run") {
      return '<span class="pl-gico run" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="8" r="3"/></svg></span>';
    }
    return '<span class="pl-gico wait" aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></span>';
  }

  function graphStages(jobs) {
    const order = ["generate", "validate", "deploy", "publish"];
    const map = {};
    (jobs || []).forEach(function (j) {
      const key = j.stage || j.id;
      if (!map[key]) map[key] = [];
      map[key].push(j);
    });
    return order.filter(function (name) { return map[name]; }).map(function (name) {
      return { name: name, jobs: map[name] };
    });
  }

  function renderGraph(run, activeId) {
    const stages = graphStages(run.jobs);
    let html = '<div class="pl-graph" role="region" aria-label="Pipeline jobs">';
    stages.forEach(function (stage, i) {
      if (i) html += '<div class="pl-edge" aria-hidden="true"><span></span></div>';
      const grouped = stage.jobs.length > 1;
      html += '<div class="pl-gstage"><div class="pl-gstage-name">' + esc(stage.name) + "</div>";
      html += grouped ? '<div class="pl-ggroup">' : "";
      stage.jobs.forEach(function (j) {
        const on = j.id === activeId;
        html += '<button type="button" class="pl-gjob ' + j.status + (on ? " is-on" : "") + '" data-job="' + esc(j.id) + '">' +
          jobIcon(j.status) + "<span>" + esc(j.label) + "</span></button>";
      });
      html += grouped ? "</div>" : "";
      html += "</div>";
    });
    html += "</div>";
    return html;
  }

  function seed() {
    const extras = (window.PL_EXAMPLES || []).map(function (ex, i) {
      const yaml = ex.yaml;
      const busy = i % 3 === 0;
      const runs = busy
        ? makeRuns(yaml, [
          { n: 9, status: "run", ago: 180000 },
          { n: 8, status: "fail", ago: 5400000, stage: "production", vault: "prod" },
          { n: 7, status: "ok", ago: 172800000 },
        ])
        : makeRuns(yaml, [
          { n: 3 + (i % 4), status: i % 2 ? "ok" : "fail", ago: 3600000 * (i + 1), stage: i % 2 ? "production" : "development", vault: i % 2 ? "prod" : "dev" },
        ]);
      return {
        id: "pl-ex-" + i,
        name: ex.name,
        yaml: yaml,
        saved: yaml,
        dirty: false,
        runs: runs,
      };
    });
    PL.state.files = [
      {
        id: "pl-ecommerce",
        name: "ecommerce.yaml",
        yaml: SAMPLE_YAML,
        saved: SAMPLE_YAML,
        dirty: false,
        runs: makeRuns(SAMPLE_YAML, [
          { n: 14, status: "run", ago: 120000 },
          { n: 13, status: "fail", ago: 3600000 },
          { n: 12, status: "ok", ago: 86400000 },
        ]),
      },
      {
        id: "pl-orders",
        name: "orders-pg-s3.yaml",
        yaml: STUB_YAML.replace(/\{name\}/g, "orders-pg-s3"),
        saved: STUB_YAML.replace(/\{name\}/g, "orders-pg-s3"),
        dirty: false,
        runs: makeRuns(STUB_YAML.replace(/\{name\}/g, "orders-pg-s3"), [
          { n: 4, status: "ok", ago: 7200000, stage: "production", vault: "prod" },
        ]),
      },
    ].concat(extras);
  }

  function selectedFile() {
    return PL.state.files.find(function (f) { return f.id === PL.state.selected; });
  }

  function selectedRun(file) {
    if (!file) return null;
    if (file.activeRunId) {
      const found = (file.runs || []).find(function (r) { return r.id === file.activeRunId; });
      if (found) return found;
    }
    return lastRun(file);
  }

  function renderTree() {
    const tree = document.getElementById("plTree");
    if (!tree) return;
    const q = PL.state.search;
    const files = PL.state.files.filter(function (f) {
      return !q || f.name.toLowerCase().indexOf(q) >= 0;
    });
    if (!files.length) {
      tree.innerHTML = '<div class="pl-tree-empty">No pipelines yet. Create one to save a YAML recipe.</div>';
      return;
    }
    tree.innerHTML = files.map(function (f) {
      const latest = lastRun(f);
      const on = PL.state.selected === f.id;
      const meta = latest
        ? "#" + latest.n + " · " + relTime(latest.createdAt)
        : "No runs";
      const badge = latest
        ? '<span class="pl-badge ' + latest.status + '">' + statusLabel(latest.status) + "</span>"
        : "";
      return '<button type="button" class="pl-row' + (on ? " is-on" : "") + '" data-file="' + esc(f.id) + '">' +
        '<span class="pl-row-ico">' + (window.SB_FILE_ICON || "") + "</span>" +
        '<span class="pl-row-copy"><strong>' + esc(f.name) + "</strong><small>" + esc(meta) + "</small></span>" +
        badge +
        "</button>";
    }).join("");
  }

  function renderDetail() {
    const el = document.getElementById("plDetail");
    if (!el) return;
    const file = selectedFile();
    if (!file) {
      el.innerHTML = '<div class="pl-empty"><div class="pl-empty-card"><h2>No pipeline selected</h2><p>Pick a YAML file, then use Code or Trigger.</p></div></div>';
      return;
    }
    el.innerHTML = renderWorkbench(file);
    bindWorkbench(file);
  }

  function renderTabs(file) {
    const tab = PL.state.tab;
    return '<div class="pl-tabs" role="tablist">' +
      '<button type="button" class="pl-tab' + (tab === "code" ? " is-on" : "") + '" data-tab="code" role="tab" aria-selected="' + (tab === "code") + '">' +
      ICO_CODE + " Code</button>" +
      '<button type="button" class="pl-tab' + (tab === "trigger" ? " is-on" : "") + '" data-tab="trigger" role="tab" aria-selected="' + (tab === "trigger") + '">' +
      '<span class="pl-play-circle" aria-hidden="true">' + ICO_PLAY + "</span> Trigger</button>" +
      "</div>";
  }

  function renderHead(file, extraActions) {
    return '<div class="pl-head">' +
      '<div class="pl-head-row"><div>' +
      "<h1>" + esc(file.name) + "</h1></div>" +
      '<div class="pl-head-actions">' + (extraActions || "") + "</div></div></div>" +
      renderTabs(file);
  }

  function renderCode(file) {
    const actions = (file.dirty ? '<span class="pl-dirty">Unsaved</span>' : "") +
      '<button type="button" class="pl-btn" id="plSave">Save</button>';
    return renderHead(file, actions) +
      '<div class="pl-work is-code">' +
      '<div class="pl-editor-wrap"><div class="pl-code-scroll" id="plCodeScroll">' +
      '<div class="pl-gutter" id="plGutter"></div>' +
      '<div class="pl-code-main">' +
      '<pre class="pl-yaml-hl" id="plYamlHl" aria-hidden="true"></pre>' +
      '<textarea class="pl-yaml" id="plYaml" spellcheck="false" wrap="off">' + esc(file.yaml) + "</textarea>" +
      "</div></div></div></div>";
  }

  function currentJob(run) {
    if (!run || !run.jobs || !run.jobs.length) return null;
    const id = PL.state.activeJob;
    return run.jobs.find(function (j) { return j.id === id; }) ||
      run.jobs.find(function (j) { return j.status === "fail" || j.status === "run"; }) ||
      run.jobs[0];
  }

  function bindDrag(handle, axis, onMove) {
    if (!handle) return;
    handle.addEventListener("mousedown", function (event) {
      event.preventDefault();
      const startX = event.clientX;
      const startY = event.clientY;
      handle.classList.add("is-dragging");
      document.body.classList.add(axis === "y" ? "pl-resizing-y" : "pl-resizing-x");
      function move(ev) {
        onMove(ev.clientX - startX, ev.clientY - startY);
      }
      function up() {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        handle.classList.remove("is-dragging");
        document.body.classList.remove("pl-resizing-x", "pl-resizing-y");
      }
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });
  }

  function applySplitSizes() {
    const side = document.getElementById("plSidebar");
    if (side) side.style.width = PL.state.sidebarW + "px";
    const hist = document.getElementById("plTrigHist");
    if (hist) hist.style.width = PL.state.histW + "px";
    const log = document.getElementById("plLogPane");
    if (log) log.style.height = PL.state.logH + "px";
  }

  function renderTrigger(file) {
    const run = selectedRun(file);
    const job = currentJob(run);
    const runs = (file.runs || []).slice().sort(function (a, b) { return b.n - a.n; });
    const rows = runs.length
      ? runs.map(function (r) {
        const on = run && run.id === r.id;
        return '<button type="button" class="pl-trig-row' + (on ? " is-on" : "") + '" data-run="' + esc(r.id) + '">' +
          '<span class="pl-play-circle sm ' + r.status + '" aria-hidden="true">' + ICO_PLAY + "</span>" +
          "<span><strong>#" + r.n + "</strong><small>" + esc(r.stage) + " · " + relTime(r.createdAt) + "</small></span>" +
          '<span class="pl-badge ' + r.status + '">' + statusLabel(r.status) + "</span></button>";
      }).join("")
      : '<div class="pl-tree-empty">No triggers yet.</div>';

    const actions = '<select class="pl-select" id="plStage"><option value="development">development</option><option value="production">production</option><option value="all_stages">all stages</option></select>' +
      '<button type="button" class="pl-btn pl-btn-trigger" id="plDeploy">' +
      '<span class="pl-play-circle" aria-hidden="true">' + ICO_PLAY + "</span> Trigger pipeline</button>";

    return renderHead(file, actions) +
      '<div class="pl-work is-trigger">' +
      '<aside class="pl-trig-hist" id="plTrigHist">' +
      '<div class="pl-runs-h">History</div>' + rows + "</aside>" +
      '<div class="pl-resizer pl-resizer-col" id="plHistResizer" role="separator" aria-orientation="vertical" aria-label="Resize history"></div>' +
      '<div class="pl-trig-main">' +
      (run ? renderGraph(run, job.id) : '<div class="pl-tree-empty">Trigger a pipeline to see lineage.</div>') +
      (run
        ? '<div class="pl-resizer pl-resizer-row" id="plLogResizer" role="separator" aria-orientation="horizontal" aria-label="Resize logs"></div>' +
          '<div class="pl-log" id="plLogPane"><div class="pl-log-h">' + esc(job.label) + "</div>" + esc(job.log) + "</div>"
        : "") +
      "</div></div>";
  }

  function renderWorkbench(file) {
    if (PL.state.tab === "code") return renderCode(file);
    return renderTrigger(file);
  }

  function paintEditor() {
    const ta = document.getElementById("plYaml");
    const hl = document.getElementById("plYamlHl");
    const gutter = document.getElementById("plGutter");
    if (!ta || !hl || !gutter) return;
    const text = ta.value;
    const lines = text.split("\n");
    gutter.textContent = lines.map(function (_, i) { return String(i + 1); }).join("\n");
    hl.innerHTML = highlightYaml(text) + "\n";
    ta.style.height = "auto";
    const height = Math.max(ta.scrollHeight, ta.parentElement.clientHeight || 0);
    ta.style.height = height + "px";
    hl.style.height = height + "px";
    gutter.style.minHeight = height + "px";
  }

  function bindWorkbench(file) {
    document.querySelectorAll("[data-tab]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        PL.state.tab = btn.getAttribute("data-tab");
        if (PL.state.tab === "trigger" && file && !file.activeRunId && lastRun(file)) {
          openTrigger(file, lastRun(file).id);
          return;
        }
        renderDetail();
      });
    });
    const yaml = document.getElementById("plYaml");
    if (yaml) {
      paintEditor();
      yaml.addEventListener("input", function () {
        file.yaml = yaml.value;
        file.dirty = file.yaml !== file.saved;
        const mark = document.querySelector(".pl-dirty");
        const actions = document.querySelector(".pl-head-actions");
        if (file.dirty && !mark && actions) {
          const span = document.createElement("span");
          span.className = "pl-dirty";
          span.textContent = "Unsaved";
          actions.insertBefore(span, actions.firstChild);
        }
        if (!file.dirty && mark) mark.remove();
        paintEditor();
      });
    }
    const save = document.getElementById("plSave");
    if (save) save.addEventListener("click", function () {
      file.saved = file.yaml;
      file.dirty = false;
      renderDetail();
    });
    const deploy = document.getElementById("plDeploy");
    if (deploy) deploy.addEventListener("click", function () {
      startDeploy(file);
    });
    document.querySelectorAll("[data-run]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openTrigger(file, btn.getAttribute("data-run"));
      });
    });
    document.querySelectorAll("[data-job]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        PL.state.activeJob = btn.getAttribute("data-job");
        renderDetail();
      });
    });
    applySplitSizes();
    const hist = document.getElementById("plTrigHist");
    if (hist) {
      const startW = { n: PL.state.histW };
      bindDrag(document.getElementById("plHistResizer"), "x", function (dx) {
        const width = Math.max(160, Math.min(420, startW.n + dx));
        PL.state.histW = width;
        hist.style.width = width + "px";
      });
      document.getElementById("plHistResizer").addEventListener("mousedown", function () {
        startW.n = hist.getBoundingClientRect().width;
      });
    }
    const log = document.getElementById("plLogPane");
    if (log) {
      const startH = { n: PL.state.logH };
      const main = log.closest(".pl-trig-main");
      bindDrag(document.getElementById("plLogResizer"), "y", function (_, dy) {
        const maxH = Math.max(80, (main ? main.clientHeight : 480) - 90);
        const height = Math.max(80, Math.min(maxH, startH.n - dy));
        PL.state.logH = height;
        log.style.height = height + "px";
      });
      document.getElementById("plLogResizer").addEventListener("mousedown", function () {
        startH.n = log.getBoundingClientRect().height;
      });
    }
  }

  function openTrigger(file, runId) {
    file.activeRunId = runId;
    PL.state.tab = "trigger";
    const run = (file.runs || []).find(function (r) { return r.id === runId; });
    const hit = run && run.jobs.find(function (j) { return j.status === "fail" || j.status === "run"; });
    PL.state.activeJob = hit ? hit.id : (run && run.jobs[0] && run.jobs[0].id);
    renderDetail();
  }

  function clearTimers() {
    PL.state.timers.forEach(function (t) { clearTimeout(t); });
    PL.state.timers = [];
  }

  function startDeploy(file) {
    file.saved = file.yaml;
    file.dirty = false;
    const stage = (document.getElementById("plStage") || {}).value || "development";
    const n = (file.runs.reduce(function (m, r) { return Math.max(m, r.n); }, 0) || 0) + 1;
    const jobs = jobsForYaml(file.yaml, "run");
    const run = {
      id: uid("run"),
      n: n,
      stage: stage === "all_stages" ? "development" : stage,
      vault: stage === "production" ? "prod" : "dev",
      status: "run",
      jobs: jobs,
      createdAt: Date.now(),
    };
    file.runs.unshift(run);
    file.activeRunId = run.id;
    PL.state.tab = "trigger";
    PL.state.activeJob = "generate";
    clearTimers();
    jobs.forEach(function (job, i) {
      PL.state.timers.push(setTimeout(function () {
        job.status = "ok";
        job.log = jobLog(job.label, "ok");
        if (job.id === "alerts") job.log = "alerts upserted\nconfigs written";
        const next = jobs[i + 1];
        if (next) {
          next.status = "run";
          next.log = jobLog(next.label, "run");
          PL.state.activeJob = next.id;
        } else {
          run.status = "ok";
          PL.state.activeJob = job.id;
        }
        renderTree();
        renderDetail();
      }, 450 * (i + 1)));
    });
    renderTree();
    renderDetail();
  }

  function selectFile(id) {
    PL.state.selected = id;
    PL.state.tab = "code";
    renderTree();
    renderDetail();
  }

  function openModal() {
    document.getElementById("plModal").hidden = false;
    document.getElementById("plModalName").value = "";
    document.getElementById("plModalName").focus();
  }

  function closeModal() {
    document.getElementById("plModal").hidden = true;
  }

  function createPipeline() {
    const name = (document.getElementById("plModalName").value || "").trim().replace(/\.yaml$/i, "");
    if (!name) return;
    const file = {
      id: uid("pl"),
      name: name.replace(/[^A-Za-z0-9_-]/g, "-") + ".yaml",
      yaml: STUB_YAML.replace(/\{name\}/g, name),
      saved: STUB_YAML.replace(/\{name\}/g, name),
      dirty: false,
      runs: [],
    };
    PL.state.files.unshift(file);
    closeModal();
    selectFile(file.id);
  }

  function bindGlobal() {
    document.getElementById("plSearch").addEventListener("input", function (e) {
      PL.state.search = e.target.value.trim().toLowerCase();
      renderTree();
    });
    document.getElementById("plNewBtn").addEventListener("click", openModal);
    document.getElementById("plModalClose").addEventListener("click", closeModal);
    document.getElementById("plModalCancel").addEventListener("click", closeModal);
    document.getElementById("plModalCreate").addEventListener("click", createPipeline);
    document.getElementById("plModal").addEventListener("click", function (e) {
      if (e.target.id === "plModal") closeModal();
    });
    document.getElementById("plTree").addEventListener("click", function (e) {
      const btn = e.target.closest("[data-file]");
      if (btn) selectFile(btn.getAttribute("data-file"));
    });
    const sidebar = document.getElementById("plSidebar");
    if (sidebar) {
      const startW = { n: PL.state.sidebarW };
      bindDrag(document.getElementById("plSideResizer"), "x", function (dx) {
        const width = Math.max(200, Math.min(560, startW.n + dx));
        PL.state.sidebarW = width;
        sidebar.style.width = width + "px";
      });
      document.getElementById("plSideResizer").addEventListener("mousedown", function () {
        startW.n = sidebar.getBoundingClientRect().width;
      });
      sidebar.style.width = PL.state.sidebarW + "px";
    }
  }

  function initPipelinesView() {
    seed();
    bindGlobal();
    renderTree();
    renderDetail();
  }

  window.PL = PL;
  window.initPipelinesView = initPipelinesView;
  document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById("view-pipelines")) initPipelinesView();
  });
})();
