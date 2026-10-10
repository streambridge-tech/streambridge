import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

const html = await readFile(new URL("../../static/login.html", import.meta.url), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

// A stand-in for the element with this id in login.html, or null like the real DOM.
function element(id) {
  const tag = html.match(new RegExp(`<[^>]*\\bid="${id}"[^>]*>`));
  if (!tag) return null;
  const listeners = {};
  return {
    id, hidden: /\shidden[\s>]/.test(tag[0]), value: "", disabled: false, textContent: "", className: "", dataset: {},
    classList: { toggle() {} },
    addEventListener(type, fn) { listeners[type] = fn; },
    fire(type) { return listeners[type]({ preventDefault() {} }); },
    focus() {},
    querySelector() { return null; },
  };
}

// Runs the page script against fake elements and a fake fetch keyed by URL.
function loadPage(responses) {
  const elements = {};
  const el = id => (elements[id] ??= element(id));
  const requests = [];
  const window = { location: { href: "/login" } };
  const fetch = async (url, options = {}) => {
    requests.push({ url, ...options });
    const [status, body] = responses[url] ?? [404, {}];
    return { ok: status < 400, status, json: async () => body };
  };
  runInNewContext(script, {
    document: { getElementById: el, querySelectorAll: () => [] },
    fetch, window, setTimeout, JSON,
  });
  return { el, requests, window };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));
const visible = page => ["signin", "welcome", "password"].filter(v => page.el(`view-${v}`)?.hidden === false);
const RETURNING = { "/api/auth/status": [200, { setupRequired: false, authEnabled: true }] };

test("a session that must change its password opens on the change form", async () => {
  const page = loadPage({
    ...RETURNING,
    "/api/auth/me": [200, { authenticated: true, user: { mustChangePassword: true } }],
  });
  await settle();
  assert.deepEqual(visible(page), ["password"]);
});

test("a signed-out visitor sees the sign-in form", async () => {
  const page = loadPage({ ...RETURNING, "/api/auth/me": [200, { authenticated: false }] });
  await settle();
  assert.deepEqual(visible(page), ["signin"]);
});

test("signing in with a temporary password shows the change form instead of the app", async () => {
  const page = loadPage({
    ...RETURNING,
    "/api/auth/me": [200, { authenticated: false }],
    "/api/auth/login": [200, { user: { mustChangePassword: true } }],
  });
  await settle();
  await page.el("signin-form").fire("submit");
  assert.deepEqual(visible(page), ["password"]);
  assert.equal(page.window.location.href, "/login");
});

test("signing in without a pending change goes to the app", async () => {
  const page = loadPage({
    ...RETURNING,
    "/api/auth/me": [200, { authenticated: false }],
    "/api/auth/login": [200, { user: { mustChangePassword: false } }],
  });
  await settle();
  await page.el("signin-form").fire("submit");
  assert.equal(page.window.location.href, "/");
});

test("the change form posts to change-password, then continues to the app", async () => {
  const page = loadPage({
    ...RETURNING,
    "/api/auth/me": [200, { authenticated: true, user: { mustChangePassword: true } }],
    "/api/auth/change-password": [200, { ok: true }],
  });
  await settle();
  page.el("cp-current").value = "temporary-pass-1";
  page.el("cp-new").value = "my-own-pass-22";
  page.el("cp-confirm").value = "my-own-pass-22";
  await page.el("password-form").fire("submit");
  const sent = page.requests.find(r => r.url === "/api/auth/change-password");
  assert.equal(sent.method, "POST");
  assert.deepEqual(JSON.parse(sent.body), { currentPassword: "temporary-pass-1", newPassword: "my-own-pass-22" });
  assert.equal(page.window.location.href, "/");
});

test("the change form shows the server's reason and stays put", async () => {
  const page = loadPage({
    ...RETURNING,
    "/api/auth/me": [200, { authenticated: true, user: { mustChangePassword: true } }],
    "/api/auth/change-password": [400, { error: "Current password is incorrect" }],
  });
  await settle();
  page.el("cp-new").value = "my-own-pass-22";
  page.el("cp-confirm").value = "my-own-pass-22";
  await page.el("password-form").fire("submit");
  assert.equal(page.el("password-msg").textContent, "Current password is incorrect");
  assert.equal(page.window.location.href, "/login");
});

test("mismatched new passwords are caught before any request", async () => {
  const page = loadPage({
    ...RETURNING,
    "/api/auth/me": [200, { authenticated: true, user: { mustChangePassword: true } }],
  });
  await settle();
  page.el("cp-new").value = "my-own-pass-22";
  page.el("cp-confirm").value = "my-own-pass-23";
  await page.el("password-form").fire("submit");
  assert.equal(page.el("password-msg").textContent, "New passwords do not match.");
  assert.ok(!page.requests.some(r => r.url === "/api/auth/change-password"));
});

test("a refused first-run setup shows the server's explanation", async () => {
  const message = "Host not allowed. Add it to server.allowed_hosts in profile.yaml.";
  const page = loadPage({
    "/api/auth/status": [200, { setupRequired: true, authEnabled: true }],
    "/api/auth/setup": [403, { error: "invalid host", message }],
  });
  await settle();
  page.el("personal-btn").fire("click");
  await settle();
  assert.equal(page.el("personal-msg").textContent, message);
});
