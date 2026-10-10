import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

const source = await readFile(new URL("../../static/js/rbac_nav.js", import.meta.url), "utf8");

// Loads rbac_nav.js, whose fetch wrapper every app page goes through, over a fetch that
// always answers with the given status and body.
function loadPage(status, body) {
  const response = { status, ok: status < 400, json: async () => body, clone() { return this; } };
  const window = { location: { href: "/connectors" }, fetch: async () => response };
  const document = { addEventListener() {}, getElementById: () => null };
  runInNewContext(source, { window, document, setTimeout, clearTimeout });
  return window;
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));

test("an API call refused for a pending password change opens the login page", async () => {
  const window = loadPage(403, { error: "Password change required", code: "must_change_password" });
  await window.fetch("/api/connections");
  await settle();
  assert.equal(window.location.href, "/login");
});

test("other refusals leave the page where it is", async () => {
  const window = loadPage(403, { error: "invalid origin" });
  await window.fetch("/api/connections");
  await settle();
  assert.equal(window.location.href, "/connectors");
});
