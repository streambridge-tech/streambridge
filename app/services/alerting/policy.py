from __future__ import annotations

import json

RULE_STATES = ("FAILED", "UNKNOWN", "PAUSED")
ACTIONS = ("pause", "re-trigger", "notify")
_RULE_SET = set(RULE_STATES)
_ACTION_SET = set(ACTIONS)


def _one_rule(rule, action) -> dict | None:
    want = str(rule or "FAILED").upper()
    act = str(action or "pause").lower()
    if want not in _RULE_SET:
        return None
    if act not in _ACTION_SET:
        act = "pause"
    return {"rule": want, "action": act}


def parse_rules(raw, fallback_rule="FAILED", fallback_action="pause") -> list[dict]:
    rows = raw
    if isinstance(raw, str) and raw.strip():
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            rows = None
    out = []
    seen = set()
    if isinstance(rows, list):
        for item in rows:
            if not isinstance(item, dict):
                continue
            parsed = _one_rule(item.get("rule") or item.get("conditionValue"), item.get("action"))
            if not parsed or parsed["rule"] in seen:
                continue
            seen.add(parsed["rule"])
            out.append(parsed)
    if out:
        return out
    parsed = _one_rule(fallback_rule, fallback_action)
    return [parsed] if parsed else [{"rule": "FAILED", "action": "pause"}]


def rules_for(alert) -> list[dict]:
    return parse_rules(
        getattr(alert, "rules_json", None),
        getattr(alert, "condition_value", None),
        getattr(alert, "match_action", None),
    )


def dump_rules(rules: list[dict]) -> str:
    return json.dumps(rules, separators=(",", ":"))


def validate_rules(rules: list[dict]) -> str | None:
    if not rules:
        return "Add at least one rule."
    seen = set()
    for item in rules:
        rule = item.get("rule")
        action = item.get("action")
        if rule not in _RULE_SET:
            return f"Unknown rule '{rule}'."
        if action not in _ACTION_SET:
            return f"Unknown action '{action}'."
        if rule in seen:
            return f"Rule {rule} is already set. Each status can appear once."
        seen.add(rule)
        if rule == "PAUSED" and action == "pause":
            return "PAUSED cannot use pause — the connector is already paused. Use re-trigger or notify."
    return None


def first_match(rules: list[dict], status: str) -> tuple[int | None, dict | None]:
    got = (status or "").upper()
    for idx, item in enumerate(rules):
        if item["rule"] == got:
            return idx, item
    return None, None


def policy_name(connector: str, rules: list[dict]) -> str:
    name = connector or "connector"
    labels = ",".join(item["rule"] for item in rules)
    return f"{name} · {labels}" if labels else name


def rules_from_payload(data: dict, fallback_rule="FAILED", fallback_action="pause") -> tuple[list[dict], str | None]:
    raw = data.get("rules")
    if raw is None and ("conditionValue" in data or "action" in data):
        raw = [{"rule": data.get("conditionValue", fallback_rule), "action": data.get("action", fallback_action)}]
    rules = parse_rules(raw, fallback_rule, fallback_action)
    return rules, validate_rules(rules)
