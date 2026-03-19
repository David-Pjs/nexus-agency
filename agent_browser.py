# -*- coding: utf-8 -*-
"""
agent_browser.py — Agentic browser for NEXUS.

Safety model:
  - READ actions  (navigate, scroll, read)  → automatic, no confirmation
  - WRITE actions (fill, click, submit)      → requires explicit /confirm
  - DANGER actions (pay, purchase, delete)   → double confirmation + warning

Flow:
  1. User gives task
  2. NEXUS opens page, reads it, builds a step plan
  3. NEXUS sends plan to Telegram — waits for /confirm
  4. User approves → NEXUS executes step by step
  5. Screenshot sent after each major step
  6. Full audit log of everything done

Requires: pip install playwright && playwright install chromium
"""

import os
import sys
import json
import time
import threading
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Pending action sessions ───────────────────────────────────────────────────
# chat_id -> {plan, context, url, task, expires_at}
_pending = {}
_pending_lock = threading.Lock()
SESSION_TTL = 300  # 5 minutes to confirm before plan expires

# ── Danger keywords — trigger double confirmation ─────────────────────────────
DANGER_KEYWORDS = [
    "pay", "payment", "purchase", "buy", "checkout", "credit card",
    "card number", "cvv", "billing", "subscribe", "delete", "remove account",
    "wire transfer", "send money",
]

# ── Audit log ─────────────────────────────────────────────────────────────────
AUDIT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_audit.log")

def _audit(chat_id: int, action: str, detail: str = ""):
    from datetime import datetime
    entry = f"[{datetime.now().isoformat()}] chat={chat_id} | {action} | {detail}\n"
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass
    print(f"[AUDIT] {action} | {detail[:80]}")


def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


# ── Page reader ───────────────────────────────────────────────────────────────

def read_page_for_planning(url: str) -> dict:
    """
    Open a page and extract structured info for planning.
    Returns {title, text, forms, buttons, links, screenshot_path}.
    """
    if not _playwright_available():
        return {"error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

    from playwright.sync_api import sync_playwright

    result = {"url": url, "title": "", "text": "", "forms": [], "buttons": [], "links": [], "screenshot_path": ""}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            result["title"] = page.title()

            # Extract text
            result["text"] = page.evaluate("""() => {
                ['script','style','nav','footer'].forEach(s =>
                    document.querySelectorAll(s).forEach(e => e.remove()));
                return (document.body || document.documentElement).innerText;
            }""")[:4000]

            # Extract forms and their fields
            forms = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('form')).map(form => ({
                    action: form.action || '',
                    method: form.method || 'get',
                    fields: Array.from(form.querySelectorAll('input,textarea,select')).map(el => ({
                        type: el.type || el.tagName.toLowerCase(),
                        name: el.name || el.id || el.placeholder || '',
                        placeholder: el.placeholder || '',
                        label: el.labels && el.labels[0] ? el.labels[0].innerText.trim() : '',
                        required: el.required,
                        value: el.value || ''
                    })).filter(f => f.type !== 'hidden' && f.type !== 'submit')
                }));
            }""")
            result["forms"] = forms[:3]  # Max 3 forms

            # Extract clickable buttons
            buttons = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button, input[type=submit], a[href]'))
                    .slice(0, 20)
                    .map(el => ({
                        text: el.innerText || el.value || el.textContent || '',
                        type: el.tagName.toLowerCase(),
                        href: el.href || ''
                    }))
                    .filter(b => b.text.trim().length > 0);
            }""")
            result["buttons"] = buttons[:15]

            # Screenshot
            ss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    f"_ss_{int(time.time())}.png")
            page.screenshot(path=ss_path, full_page=False)
            result["screenshot_path"] = ss_path

            browser.close()

    except Exception as e:
        result["error"] = str(e)
        print(f"[AgentBrowser] Read error: {e}")

    return result


# ── Plan builder ──────────────────────────────────────────────────────────────

def build_plan(task: str, page_info: dict, user_data: dict = None) -> list:
    """
    Build a list of steps to accomplish the task on this page.
    Each step: {action, target, value, risk, description}

    Actions: navigate, fill, click, select, scroll, read, submit, screenshot
    Risk:    low (read-only) | medium (fill/click) | high (submit/pay)
    """
    steps = []
    forms = page_info.get("forms", [])
    buttons = page_info.get("buttons", [])
    text = page_info.get("text", "").lower()
    task_lower = task.lower()

    # Detect if task involves a form
    if forms and any(w in task_lower for w in ["fill", "apply", "register", "sign up", "submit", "complete"]):
        for form in forms:
            for field in form.get("fields", []):
                field_name = (field.get("label") or field.get("name") or field.get("placeholder") or "").lower()
                field_type = field.get("type", "text")

                # Skip password fields unless explicitly asked
                if field_type == "password":
                    steps.append({
                        "action": "fill",
                        "target": field.get("name", "password"),
                        "value": "[REQUIRES YOUR INPUT — never stored]",
                        "risk": "high",
                        "description": f"Fill password field '{field_name}' — you will be asked to provide this privately",
                        "requires_input": True,
                    })
                    continue

                # Map common fields to user data
                value = ""
                if user_data:
                    for key, val in user_data.items():
                        if key.lower() in field_name:
                            value = val
                            break

                if value:
                    steps.append({
                        "action": "fill",
                        "target": field.get("name", field_name),
                        "value": value,
                        "risk": "medium",
                        "description": f"Fill '{field_name}' with '{value}'",
                    })
                else:
                    steps.append({
                        "action": "fill",
                        "target": field.get("name", field_name),
                        "value": f"[NEEDS VALUE for: {field_name}]",
                        "risk": "medium",
                        "description": f"Fill '{field_name}' — value needed",
                        "requires_input": True,
                    })

            # Submit step
            steps.append({
                "action": "submit",
                "target": "form",
                "value": "",
                "risk": "high",
                "description": "Submit the form",
            })

    # Detect click tasks
    elif any(w in task_lower for w in ["click", "press", "tap", "open"]):
        for btn in buttons[:5]:
            btn_text = btn.get("text", "").strip().lower()
            if any(w in task_lower for w in btn_text.split()):
                steps.append({
                    "action": "click",
                    "target": btn.get("text", ""),
                    "value": "",
                    "risk": "medium",
                    "description": f"Click '{btn.get('text', '')}' button",
                })

    # Default: read and screenshot
    if not steps:
        steps.append({
            "action": "screenshot",
            "target": page_info.get("url", ""),
            "value": "",
            "risk": "low",
            "description": "Take a screenshot and read the current page state",
        })

    return steps


def _is_dangerous(steps: list) -> bool:
    """Check if any step involves dangerous actions (payments, deletions)."""
    for step in steps:
        desc = (step.get("description", "") + step.get("value", "")).lower()
        if any(kw in desc for kw in DANGER_KEYWORDS):
            return True
    return False


# ── Plan formatter ────────────────────────────────────────────────────────────

def format_plan(task: str, url: str, steps: list) -> str:
    is_dangerous = _is_dangerous(steps)

    lines = [
        f"🤖 *NEXUS  |  Action Plan*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Task: _{task}_",
        f"URL: `{url[:60]}`\n",
        f"*Steps I will take:*\n",
    ]

    for i, step in enumerate(steps, 1):
        risk = step.get("risk", "low")
        risk_em = "🟢" if risk == "low" else "🟡" if risk == "medium" else "🔴"
        needs_input = " _(need your input)_" if step.get("requires_input") else ""
        lines.append(f"{risk_em} *{i}.* {step['description']}{needs_input}")

    lines.append("")

    if is_dangerous:
        lines.append("🚨 *WARNING: This plan includes high-risk actions (payment/deletion).*")
        lines.append("Type `/confirm DANGEROUS` to proceed or `/cancel` to abort.\n")
    else:
        lines.append("_Reply /confirm to execute or /cancel to abort._")
        lines.append("_Plan expires in 5 minutes._")

    return "\n".join(lines)


# ── Executor ──────────────────────────────────────────────────────────────────

def execute_plan(chat_id: int, steps: list, url: str, send_fn, send_photo_fn) -> str:
    """Execute approved steps. Sends progress updates via send_fn."""
    if not _playwright_available():
        return "Playwright not installed. Run: `pip install playwright && playwright install chromium`"

    from playwright.sync_api import sync_playwright

    _audit(chat_id, "EXECUTE_START", f"url={url} steps={len(steps)}")
    results = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            for i, step in enumerate(steps, 1):
                action = step["action"]
                target = step["target"]
                value = step["value"]

                # Skip steps that need input but have placeholder values
                if step.get("requires_input") and value.startswith("["):
                    results.append(f"⏭ Skipped: {step['description']} (no value provided)")
                    continue

                try:
                    send_fn(chat_id, f"⚙️ Step {i}/{len(steps)}: {step['description']}")

                    if action == "navigate":
                        page.goto(value or target, timeout=30000)
                        page.wait_for_timeout(1500)
                        results.append(f"✅ Navigated to {value or target}")
                        _audit(chat_id, "NAVIGATE", value or target)

                    elif action == "fill":
                        # Try by name, placeholder, label
                        selectors = [
                            f"[name='{target}']",
                            f"[id='{target}']",
                            f"[placeholder*='{target}']",
                        ]
                        filled = False
                        for sel in selectors:
                            try:
                                if page.locator(sel).count() > 0:
                                    page.locator(sel).first.fill(value)
                                    filled = True
                                    break
                            except Exception:
                                continue
                        if filled:
                            results.append(f"✅ Filled '{target}'")
                            _audit(chat_id, "FILL", f"target={target} value_len={len(value)}")
                        else:
                            results.append(f"⚠️ Could not find field '{target}'")

                    elif action == "click":
                        try:
                            page.get_by_text(target, exact=False).first.click()
                            page.wait_for_timeout(1500)
                            results.append(f"✅ Clicked '{target}'")
                            _audit(chat_id, "CLICK", target)
                        except Exception:
                            results.append(f"⚠️ Could not click '{target}'")

                    elif action == "submit":
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(2000)
                        results.append(f"✅ Form submitted")
                        _audit(chat_id, "SUBMIT", url)

                    elif action == "scroll":
                        page.evaluate("window.scrollBy(0, 500)")
                        results.append(f"✅ Scrolled")

                    elif action == "screenshot":
                        results.append(f"✅ Screenshot taken")

                    # Screenshot after every write action
                    if action in ("fill", "click", "submit", "navigate"):
                        ss_path = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            f"_ss_exec_{int(time.time())}.png"
                        )
                        page.screenshot(path=ss_path)
                        try:
                            send_photo_fn(chat_id, None, caption=f"Step {i} complete", local_path=ss_path)
                        except Exception:
                            pass
                        try:
                            os.remove(ss_path)
                        except Exception:
                            pass

                except Exception as e:
                    results.append(f"❌ Error on step {i}: {str(e)[:100]}")
                    _audit(chat_id, "STEP_ERROR", str(e)[:100])

            browser.close()

    except Exception as e:
        _audit(chat_id, "EXECUTE_ERROR", str(e))
        return f"❌ Browser error: {str(e)[:200]}"

    _audit(chat_id, "EXECUTE_DONE", f"{len(results)} steps completed")

    summary = "\n".join(results)
    return (
        f"🤖 *NEXUS  |  Task Complete*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{summary}\n\n"
        f"_Full audit log saved to agent\\_audit.log_"
    )


# ── Pending action management ─────────────────────────────────────────────────

def store_pending(chat_id: int, task: str, url: str, steps: list, is_dangerous: bool = False):
    with _pending_lock:
        _pending[chat_id] = {
            "task": task,
            "url": url,
            "steps": steps,
            "is_dangerous": is_dangerous,
            "expires_at": time.time() + SESSION_TTL,
        }


def pop_pending(chat_id: int) -> dict | None:
    with _pending_lock:
        p = _pending.pop(chat_id, None)
        if p and p["expires_at"] < time.time():
            return None  # Expired
        return p


def cancel_pending(chat_id: int):
    with _pending_lock:
        _pending.pop(chat_id, None)


def has_pending(chat_id: int) -> bool:
    with _pending_lock:
        p = _pending.get(chat_id)
        if not p:
            return False
        if p["expires_at"] < time.time():
            _pending.pop(chat_id, None)
            return False
        return True
