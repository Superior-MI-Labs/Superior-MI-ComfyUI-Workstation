import { app } from "../../scripts/app.js";
import {
    deriveGraphControls,
    readLiveControlValue,
    writeLiveControlValue,
} from "./smi-graph-controls.js";

const EXTENSION_NAME = "SuperiorMI.WorkstationBridge";
const SIDEBAR_ID = "superior-mi-workstation";
const STYLE_ID = "superior-mi-workstation-style";

function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
        .smi-workstation-shell {
            display: flex;
            flex-direction: column;
            height: 100%;
            min-height: 0;
            font-family: inherit;
        }
        .smi-workstation-header {
            padding: 14px 14px 10px;
            border-bottom: 1px solid var(--border-color, rgba(128,128,128,.25));
        }
        .smi-workstation-title {
            font-weight: 700;
            font-size: 1rem;
        }
        .smi-workstation-subtitle {
            margin-top: 4px;
            opacity: .72;
            font-size: .8rem;
            line-height: 1.35;
        }
        .smi-workstation-nav {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 6px;
            padding: 10px;
            border-bottom: 1px solid var(--border-color, rgba(128,128,128,.25));
        }
        .smi-workstation-nav button,
        .smi-workstation-button {
            min-width: 0;
            padding: 7px 8px;
            border-radius: 7px;
            border: 1px solid var(--border-color, rgba(128,128,128,.35));
            background: var(--comfy-input-bg, rgba(128,128,128,.08));
            color: inherit;
            cursor: pointer;
        }
        .smi-workstation-nav button[data-active="true"] {
            font-weight: 650;
            border-color: var(--p-primary-color, currentColor);
        }
        .smi-workstation-panel {
            overflow: auto;
            padding: 14px;
            flex: 1;
        }
        .smi-workstation-panel h3 {
            margin: 0 0 8px;
            font-size: .95rem;
        }
        .smi-workstation-panel p {
            margin: 0 0 10px;
            opacity: .8;
            line-height: 1.45;
        }
        .smi-workstation-status {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 12px;
            padding: 8px 10px;
            border-radius: 7px;
            background: var(--comfy-input-bg, rgba(128,128,128,.08));
            font-size: .8rem;
        }
        .smi-workstation-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: currentColor;
            opacity: .35;
            flex: 0 0 auto;
        }
        .smi-workstation-status[data-ok="true"] .smi-workstation-dot {
            opacity: 1;
        }
        .smi-create-toolbar {
            display: flex;
            justify-content: flex-end;
            gap: 6px;
            margin: 8px 0 12px;
        }
        .smi-control-group {
            margin: 0 0 16px;
        }
        .smi-control-group-title {
            margin: 0 0 7px;
            font-size: .76rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .04em;
            opacity: .65;
        }
        .smi-control {
            display: grid;
            gap: 5px;
            margin: 0 0 10px;
        }
        .smi-control-label {
            font-size: .78rem;
            font-weight: 600;
        }
        .smi-control input:not([type="checkbox"]),
        .smi-control select,
        .smi-control textarea {
            width: 100%;
            box-sizing: border-box;
            border-radius: 6px;
            border: 1px solid var(--border-color, rgba(128,128,128,.35));
            background: var(--comfy-input-bg, rgba(128,128,128,.08));
            color: inherit;
            padding: 7px;
            font: inherit;
        }
        .smi-control textarea {
            min-height: 78px;
            resize: vertical;
        }
        .smi-control-slider {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 82px;
            gap: 7px;
            align-items: center;
        }
        .smi-control-toggle {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .smi-control-readonly {
            padding: 7px;
            border-radius: 6px;
            background: var(--comfy-input-bg, rgba(128,128,128,.08));
            opacity: .72;
            font-size: .8rem;
            overflow-wrap: anywhere;
        }
        .smi-control-empty {
            opacity: .65;
            font-size: .82rem;
        }
        .smi-assistant-grid {
            display: grid;
            gap: 9px;
            margin: 10px 0 14px;
        }
        .smi-assistant-field {
            display: grid;
            gap: 4px;
        }
        .smi-assistant-field > span {
            font-size: .74rem;
            font-weight: 650;
            opacity: .72;
        }
        .smi-assistant-field input,
        .smi-assistant-field select,
        .smi-assistant-field textarea {
            width: 100%;
            box-sizing: border-box;
            border-radius: 6px;
            border: 1px solid var(--border-color, rgba(128,128,128,.35));
            background: var(--comfy-input-bg, rgba(128,128,128,.08));
            color: inherit;
            padding: 7px;
            font: inherit;
        }
        .smi-assistant-field textarea {
            min-height: 86px;
            resize: vertical;
        }
        .smi-assistant-actions {
            display: flex;
            gap: 7px;
            flex-wrap: wrap;
            margin: 8px 0 12px;
        }
        .smi-assistant-result {
            display: grid;
            gap: 8px;
            margin-top: 10px;
        }
        .smi-plan-card {
            border: 1px solid var(--border-color, rgba(128,128,128,.28));
            border-radius: 8px;
            padding: 10px;
            background: var(--comfy-input-bg, rgba(128,128,128,.05));
        }
        .smi-plan-title {
            font-weight: 700;
            font-size: .82rem;
            margin-bottom: 6px;
        }
        .smi-plan-row {
            display: flex;
            gap: 7px;
            align-items: flex-start;
            padding: 5px 0;
            font-size: .78rem;
            line-height: 1.35;
        }
        .smi-plan-row input {
            margin-top: 2px;
        }
        .smi-plan-meta {
            font-size: .72rem;
            opacity: .66;
            margin-top: 3px;
        }
        .smi-assistant-divider {
            height: 1px;
            background: var(--border-color, rgba(128,128,128,.25));
            margin: 14px 0;
        }
    `;
    document.head.appendChild(style);
}

function paragraph(text) {
    const node = document.createElement("p");
    node.textContent = text;
    return node;
}

function toastError(message) {
    app.extensionManager?.toast?.add?.({
        severity: "error",
        summary: "Superior MI",
        detail: String(message),
        life: 5000,
    });
}

const ASSISTANT_BASE_KEY = "smi.workstation.assistant.base";
const ASSISTANT_MODEL_KEY = "smi.workstation.assistant.model";
const ASSISTANT_KEY_KEY = "smi.workstation.assistant.key";

function safeStorageGet(storage, key) {
    try {
        return storage?.getItem?.(key) ?? "";
    } catch (_) {
        return "";
    }
}

function safeStorageSet(storage, key, value) {
    try {
        if (value) storage?.setItem?.(key, value);
        else storage?.removeItem?.(key);
    } catch (_) {
        // Storage is optional. The current UI session still works.
    }
}

async function postJson(path, payload) {
    const response = await app.api.fetchApi(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    let body = {};
    try {
        body = await response.json();
    } catch (_) {
        body = {};
    }
    if (!response.ok || body?.ok === false) {
        throw new Error(body?.error || `HTTP ${response.status}`);
    }
    return body;
}

function labeledField(labelText, element) {
    const label = document.createElement("label");
    label.className = "smi-assistant-field";
    const caption = document.createElement("span");
    caption.textContent = labelText;
    label.append(caption, element);
    return label;
}

function formatBytes(value) {
    const bytes = Number(value || 0);
    if (!Number.isFinite(bytes) || bytes <= 0) return "unknown";
    const units = ["B", "KiB", "MiB", "GiB", "TiB"];
    let amount = bytes;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
        amount /= 1024;
        index += 1;
    }
    return `${amount.toFixed(index >= 3 ? 1 : 0)} ${units[index]}`;
}

function renderHardwareSummary(host, payload) {
    const hardware = payload?.hardware;
    if (!hardware) return;
    const gpu = hardware.gpus?.[0];
    const line = document.createElement("div");
    line.className = "smi-plan-meta";
    if (gpu) {
        line.textContent = `Hardware: ${gpu.model || gpu.vendor || "GPU"} · ${formatBytes(gpu.vram_bytes)} VRAM`;
    } else {
        line.textContent = `Hardware: CPU · ${formatBytes(hardware.memory_total_bytes)} RAM`;
    }
    host.appendChild(line);
}

function renderSetupPlan(host, payload) {
    const resolution = payload?.resolution;
    if (!resolution) return;

    const card = document.createElement("div");
    card.className = "smi-plan-card";
    const title = document.createElement("div");
    title.className = "smi-plan-title";
    title.textContent = "Setup plan";
    card.appendChild(title);

    const selected = resolution.selected_candidate_ids || [];
    if (selected.length) {
        const selectedLine = document.createElement("div");
        selectedLine.className = "smi-plan-meta";
        selectedLine.textContent = `Selected: ${selected.join(", ")}`;
        card.appendChild(selectedLine);
    }

    const plan = resolution.plan;
    if (!plan) {
        const unresolved = resolution.unresolved_capabilities || [];
        const line = document.createElement("div");
        line.className = "smi-plan-row";
        line.textContent = unresolved.length
            ? `No qualified implementation currently resolves: ${unresolved.join(", ")}`
            : "No executable setup plan is available.";
        card.appendChild(line);

        for (const assessment of resolution.assessments || []) {
            const reasons = [
                ...(assessment.rejection_reasons || []),
                ...(assessment.setup_reasons || []),
                ...(assessment.warnings || []),
            ];
            if (!reasons.length) continue;
            const detail = document.createElement("div");
            detail.className = "smi-plan-meta";
            detail.textContent = `${assessment.candidate_id}: ${reasons.join(" ")}`;
            card.appendChild(detail);
        }
        host.appendChild(card);
        return;
    }

    for (const action of plan.actions || []) {
        const row = document.createElement("div");
        row.className = "smi-plan-row";
        const mark = document.createElement("span");
        mark.textContent = action.status === "complete"
            ? "✓"
            : action.requires_approval
                ? "⚠"
                : "□";
        const body = document.createElement("div");
        body.textContent = action.title;
        if (action.requires_approval) {
            const meta = document.createElement("div");
            meta.className = "smi-plan-meta";
            meta.textContent = "Requires explicit approval before mutation.";
            body.appendChild(meta);
        }
        row.append(mark, body);
        card.appendChild(row);
    }

    const boundary = document.createElement("div");
    boundary.className = "smi-plan-meta";
    boundary.textContent = "This sidebar reviews the setup plan only. Package/model mutation remains approval-gated outside the browser.";
    card.appendChild(boundary);
    host.appendChild(card);
}

function renderGraphChangePlan(host, proposal) {
    const changes = proposal?.graph_changes || {};
    const currentControls = new Map(
        deriveGraphControls(app.graph).map((control) => [control.id, control])
    );
    const rows = [];

    const card = document.createElement("div");
    card.className = "smi-plan-card";
    const title = document.createElement("div");
    title.className = "smi-plan-title";
    title.textContent = "Workflow changes";
    card.appendChild(title);

    for (const [controlId, nextValue] of Object.entries(changes)) {
        const control = currentControls.get(controlId);
        if (!control) continue;

        const row = document.createElement("label");
        row.className = "smi-plan-row";
        const checked = document.createElement("input");
        checked.type = "checkbox";
        checked.checked = true;

        const body = document.createElement("div");
        body.textContent = control.label || controlId;
        const meta = document.createElement("div");
        meta.className = "smi-plan-meta";
        meta.textContent = `${String(readLiveControlValue(app.graph, control))} → ${String(nextValue)}`;
        body.appendChild(meta);

        row.append(checked, body);
        card.appendChild(row);
        rows.push({checked, controlId, nextValue});
    }

    if (!rows.length) {
        card.appendChild(paragraph("No currently loaded graph controls match the proposed changes."));
        host.appendChild(card);
        return;
    }

    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "smi-workstation-button";
    apply.textContent = "Apply selected changes";
    apply.addEventListener("click", () => {
        const latest = new Map(
            deriveGraphControls(app.graph).map((control) => [control.id, control])
        );
        try {
            for (const row of rows) {
                if (!row.checked.checked) continue;
                const control = latest.get(row.controlId);
                if (!control) throw new Error(`Graph control no longer exists: ${row.controlId}`);
                writeLiveControlValue(
                    app.graph,
                    control,
                    row.nextValue,
                    () => app.canvas?.setDirty?.(true, true),
                );
            }
            apply.textContent = "Applied";
            window.setTimeout(() => { apply.textContent = "Apply selected changes"; }, 1200);
        } catch (error) {
            toastError(error);
        }
    });
    card.appendChild(apply);
    host.appendChild(card);
}

function renderAssistantResponse(host, payload) {
    host.replaceChildren();
    renderHardwareSummary(host, payload);

    const proposal = payload?.proposal;
    if (proposal?.message) {
        const card = document.createElement("div");
        card.className = "smi-plan-card";
        card.appendChild(paragraph(proposal.message));
        host.appendChild(card);
    }

    if (proposal?.kind === "graph_changes") {
        renderGraphChangePlan(host, proposal);
    }
    if (payload?.resolution) {
        renderSetupPlan(host, payload);
    }
}

async function loadCoreCapabilities(select, status) {
    try {
        const response = await app.api.fetchApi("/superior-mi/core/status");
        const payload = await response.json();
        if (!response.ok || !payload?.core_available) {
            throw new Error(payload?.error || "Core unavailable");
        }
        status.dataset.ok = "true";
        status.lastChild.textContent = "Workstation Core connected.";
        select.replaceChildren();
        for (const capability of payload.capabilities || []) {
            const option = document.createElement("option");
            option.value = capability.id;
            option.textContent = capability.title || capability.id;
            select.appendChild(option);
        }
        if (!select.options.length) {
            for (const capabilityId of payload.capability_ids || []) {
                const option = document.createElement("option");
                option.value = capabilityId;
                option.textContent = capabilityId;
                select.appendChild(option);
            }
        }
    } catch (error) {
        status.dataset.ok = "false";
        status.lastChild.textContent = `Core unavailable: ${error}`;
    }
}

function renderHomePanel(panel) {
    panel.replaceChildren();

    const title = document.createElement("h3");
    title.textContent = "Home";
    panel.appendChild(title);
    panel.appendChild(paragraph(
        "Tell Workstation what you want to make. The assistant can only propose registered capabilities or controls; Core validates everything before a checklist or graph change is shown."
    ));

    const coreStatus = document.createElement("div");
    coreStatus.className = "smi-workstation-status";
    coreStatus.dataset.ok = "false";
    const coreDot = document.createElement("span");
    coreDot.className = "smi-workstation-dot";
    const coreLabel = document.createElement("span");
    coreLabel.textContent = "Checking Workstation Core…";
    coreStatus.append(coreDot, coreLabel);
    panel.appendChild(coreStatus);

    const settings = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Assistant provider";
    settings.appendChild(summary);

    const settingsGrid = document.createElement("div");
    settingsGrid.className = "smi-assistant-grid";
    const baseUrl = document.createElement("input");
    baseUrl.placeholder = "Local OpenAI-compatible URL, e.g. http://127.0.0.1:1920";
    baseUrl.value = safeStorageGet(window.localStorage, ASSISTANT_BASE_KEY);
    const model = document.createElement("input");
    model.placeholder = "Model name";
    model.value = safeStorageGet(window.localStorage, ASSISTANT_MODEL_KEY);
    const apiKey = document.createElement("input");
    apiKey.type = "password";
    apiKey.placeholder = "API key (session only, optional for local models)";
    apiKey.value = safeStorageGet(window.sessionStorage, ASSISTANT_KEY_KEY);
    settingsGrid.append(
        labeledField("Endpoint", baseUrl),
        labeledField("Model", model),
        labeledField("API key", apiKey),
    );
    settings.appendChild(settingsGrid);
    panel.appendChild(settings);

    const chatGrid = document.createElement("div");
    chatGrid.className = "smi-assistant-grid";
    const request = document.createElement("textarea");
    request.placeholder = "Example: Make this image wider, use about 30 steps, and prioritize quality.";
    chatGrid.appendChild(labeledField("What do you want to make or change?", request));
    panel.appendChild(chatGrid);

    const actions = document.createElement("div");
    actions.className = "smi-assistant-actions";
    const ask = document.createElement("button");
    ask.type = "button";
    ask.className = "smi-workstation-button";
    ask.textContent = "Ask Workstation";
    actions.appendChild(ask);
    panel.appendChild(actions);

    const resultHost = document.createElement("div");
    resultHost.className = "smi-assistant-result";
    panel.appendChild(resultHost);

    ask.addEventListener("click", async () => {
        const text = request.value.trim();
        if (!text) {
            toastError("Describe what you want Workstation to do.");
            return;
        }
        safeStorageSet(window.localStorage, ASSISTANT_BASE_KEY, baseUrl.value.trim());
        safeStorageSet(window.localStorage, ASSISTANT_MODEL_KEY, model.value.trim());
        safeStorageSet(window.sessionStorage, ASSISTANT_KEY_KEY, apiKey.value);

        ask.disabled = true;
        ask.textContent = "Planning…";
        try {
            const payload = await postJson("/superior-mi/assistant/propose", {
                text,
                comfyui_url: window.location.origin,
                graph_controls: deriveGraphControls(app.graph),
                assistant: {
                    base_url: baseUrl.value.trim(),
                    model: model.value.trim(),
                    api_key: apiKey.value,
                },
            });
            renderAssistantResponse(resultHost, payload);
        } catch (error) {
            toastError(error);
            resultHost.replaceChildren(paragraph(String(error)));
        } finally {
            ask.disabled = false;
            ask.textContent = "Ask Workstation";
        }
    });

    const divider = document.createElement("div");
    divider.className = "smi-assistant-divider";
    panel.appendChild(divider);
    panel.appendChild(paragraph(
        "No AI is required for setup planning. Choose a capability and Core will build the same deterministic checklist directly."
    ));

    const quickGrid = document.createElement("div");
    quickGrid.className = "smi-assistant-grid";
    const capability = document.createElement("select");
    const quality = document.createElement("select");
    for (const value of ["balanced", "quality", "speed", "storage"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value[0].toUpperCase() + value.slice(1);
        quality.appendChild(option);
    }
    quickGrid.append(
        labeledField("Goal", capability),
        labeledField("Priority", quality),
    );
    panel.appendChild(quickGrid);

    const quickActions = document.createElement("div");
    quickActions.className = "smi-assistant-actions";
    const buildPlan = document.createElement("button");
    buildPlan.type = "button";
    buildPlan.className = "smi-workstation-button";
    buildPlan.textContent = "Build setup checklist";
    quickActions.appendChild(buildPlan);
    panel.appendChild(quickActions);

    buildPlan.addEventListener("click", async () => {
        if (!capability.value) {
            toastError("No Core capability is available.");
            return;
        }
        buildPlan.disabled = true;
        buildPlan.textContent = "Planning…";
        try {
            const payload = await postJson("/superior-mi/plan", {
                capabilities: [capability.value],
                quality_priority: quality.value,
                local_only: true,
                comfyui_url: window.location.origin,
            });
            renderAssistantResponse(resultHost, payload);
        } catch (error) {
            toastError(error);
            resultHost.replaceChildren(paragraph(String(error)));
        } finally {
            buildPlan.disabled = false;
            buildPlan.textContent = "Build setup checklist";
        }
    });

    loadCoreCapabilities(capability, coreStatus);
    return () => {};
}

function valueFromInput(control, element) {
    if (control.dataType === "BOOLEAN") return Boolean(element.checked);
    if (control.dataType === "INT") return Number.parseInt(element.value, 10);
    if (control.dataType === "FLOAT") return Number.parseFloat(element.value);
    if (control.dataType === "COMBO") {
        const match = control.choices.find((choice) => String(choice) === element.value);
        return match ?? element.value;
    }
    return element.value;
}

function createControlEditor(control, onCommit) {
    const row = document.createElement("div");
    row.className = "smi-control";

    const label = document.createElement("label");
    label.className = "smi-control-label";
    label.textContent = control.label;
    row.appendChild(label);

    const syncers = [];
    const commit = (element) => {
        try {
            onCommit(valueFromInput(control, element));
        } catch (error) {
            toastError(error);
        }
    };

    if (!control.editable) {
        const value = document.createElement("div");
        value.className = "smi-control-readonly";
        value.textContent = String(control.value ?? "");
        row.appendChild(value);
        syncers.push((next) => {
            const text = String(next ?? "");
            if (value.textContent !== text) value.textContent = text;
        });
        return { row, sync: (next) => syncers.forEach((fn) => fn(next)) };
    }

    if (control.widget === "dropdown") {
        const select = document.createElement("select");
        for (const choice of control.choices) {
            const option = document.createElement("option");
            option.value = String(choice);
            option.textContent = String(choice);
            select.appendChild(option);
        }
        select.value = String(control.value ?? "");
        select.addEventListener("change", () => commit(select));
        row.appendChild(select);
        syncers.push((next) => {
            const text = String(next ?? "");
            if (select.value !== text) select.value = text;
        });
    } else if (control.widget === "toggle") {
        const wrapper = document.createElement("div");
        wrapper.className = "smi-control-toggle";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(control.value);
        const caption = document.createElement("span");
        caption.textContent = checkbox.checked ? "On" : "Off";
        checkbox.addEventListener("change", () => {
            caption.textContent = checkbox.checked ? "On" : "Off";
            commit(checkbox);
        });
        wrapper.append(checkbox, caption);
        row.appendChild(wrapper);
        syncers.push((next) => {
            const checked = Boolean(next);
            checkbox.checked = checked;
            caption.textContent = checked ? "On" : "Off";
        });
    } else if (control.widget === "slider-number") {
        const wrapper = document.createElement("div");
        wrapper.className = "smi-control-slider";

        const range = document.createElement("input");
        range.type = "range";
        if (control.minimum != null) range.min = String(control.minimum);
        if (control.maximum != null) range.max = String(control.maximum);
        if (control.step != null) range.step = String(control.step);
        range.value = String(control.value ?? 0);

        const number = document.createElement("input");
        number.type = "number";
        if (control.minimum != null) number.min = String(control.minimum);
        if (control.maximum != null) number.max = String(control.maximum);
        if (control.step != null) number.step = String(control.step);
        number.value = String(control.value ?? 0);

        range.addEventListener("input", () => {
            number.value = range.value;
            commit(range);
        });
        number.addEventListener("change", () => {
            range.value = number.value;
            commit(number);
        });

        wrapper.append(range, number);
        row.appendChild(wrapper);
        syncers.push((next) => {
            const text = String(next ?? 0);
            if (range.value !== text) range.value = text;
            if (number.value !== text) number.value = text;
        });
    } else {
        const input = control.widget === "multiline"
            ? document.createElement("textarea")
            : document.createElement("input");
        if (input instanceof HTMLInputElement) {
            input.type = control.widget === "number" ? "number" : "text";
            if (control.minimum != null) input.min = String(control.minimum);
            if (control.maximum != null) input.max = String(control.maximum);
            if (control.step != null) input.step = String(control.step);
        }
        input.value = String(control.value ?? "");
        input.addEventListener(control.widget === "multiline" ? "change" : "change", () => commit(input));
        row.appendChild(input);
        syncers.push((next) => {
            const text = String(next ?? "");
            if (input.value !== text) input.value = text;
        });
    }

    return {
        row,
        sync: (next) => syncers.forEach((fn) => fn(next)),
    };
}

function controlSignature(controls) {
    return controls
        .map((control) => [
            control.id,
            control.widget,
            control.priority,
            control.editable ? "1" : "0",
            control.choices.join("\u001f"),
        ].join("\u001e"))
        .join("\u001d");
}

function renderCreatePanel(panel) {
    panel.replaceChildren();

    const title = document.createElement("h3");
    title.textContent = "Create";
    panel.appendChild(title);
    panel.appendChild(paragraph(
        "These controls are live projections of the current ComfyUI graph. The graph remains the only value authority."
    ));

    const toolbar = document.createElement("div");
    toolbar.className = "smi-create-toolbar";
    const advanced = document.createElement("button");
    advanced.type = "button";
    advanced.className = "smi-workstation-button";
    toolbar.appendChild(advanced);
    panel.appendChild(toolbar);

    const host = document.createElement("div");
    panel.appendChild(host);

    let showAdvanced = false;
    let signature = "";
    let bindings = new Map();

    const draw = () => {
        const controls = deriveGraphControls(app.graph);
        signature = controlSignature(controls);
        bindings = new Map();
        host.replaceChildren();

        const visible = controls.filter((control) =>
            control.priority === "primary" || showAdvanced
        );
        advanced.textContent = showAdvanced ? "Hide advanced" : "Show advanced";

        if (!visible.length) {
            const empty = document.createElement("div");
            empty.className = "smi-control-empty";
            empty.textContent = controls.length
                ? "No primary controls are available. Show advanced to inspect the remaining graph widgets."
                : "Load a workflow to expose graph-derived controls.";
            host.appendChild(empty);
            return;
        }

        const groups = new Map();
        for (const control of visible) {
            if (!groups.has(control.group)) groups.set(control.group, []);
            groups.get(control.group).push(control);
        }

        for (const [groupName, groupControls] of groups) {
            const group = document.createElement("section");
            group.className = "smi-control-group";
            const heading = document.createElement("div");
            heading.className = "smi-control-group-title";
            heading.textContent = groupName;
            group.appendChild(heading);

            for (const control of groupControls) {
                const editor = createControlEditor(control, (value) => {
                    const written = writeLiveControlValue(
                        app.graph,
                        control,
                        value,
                        () => app.canvas?.setDirty?.(true, true),
                    );
                    editor.sync(written);
                });
                bindings.set(control.id, editor);
                group.appendChild(editor.row);
            }
            host.appendChild(group);
        }
    };

    advanced.addEventListener("click", () => {
        showAdvanced = !showAdvanced;
        draw();
    });

    draw();

    const interval = window.setInterval(() => {
        if (!panel.isConnected) {
            window.clearInterval(interval);
            return;
        }

        const current = deriveGraphControls(app.graph);
        const nextSignature = controlSignature(current);
        if (nextSignature !== signature) {
            draw();
            return;
        }

        for (const control of current) {
            const binding = bindings.get(control.id);
            if (!binding) continue;
            binding.sync(readLiveControlValue(app.graph, control));
        }
    }, 400);

    return () => window.clearInterval(interval);
}

function renderSection(panel, section) {
    if (section === "Home") {
        return renderHomePanel(panel);
    }
    if (section === "Create") {
        return renderCreatePanel(panel);
    }

    panel.replaceChildren();
    const title = document.createElement("h3");
    title.textContent = section;
    panel.appendChild(title);

    const copy = {
        Home: [
            "Superior MI Workstation operates around the real ComfyUI canvas.",
            "Assistant planning and approval checklists will live here without becoming a second execution authority.",
        ],
        Activity: [
            "Queue, setup actions, outputs, failures, benchmarks, and qualification evidence will converge here.",
        ],
        System: [
            "Hardware, runtime, storage, installed components, health, and optimization evidence will converge here.",
        ],
    };

    for (const line of copy[section] || []) {
        panel.appendChild(paragraph(line));
    }

    if (section === "System") {
        const status = document.createElement("div");
        status.className = "smi-workstation-status";
        status.dataset.ok = "false";

        const dot = document.createElement("span");
        dot.className = "smi-workstation-dot";
        const label = document.createElement("span");
        label.textContent = "Checking Superior MI bridge…";

        status.append(dot, label);
        panel.appendChild(status);

        app.api.fetchApi("/superior-mi/bridge/status")
            .then(async (response) => {
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const payload = await response.json();
                status.dataset.ok = payload?.ok ? "true" : "false";
                label.textContent = payload?.ok
                    ? `Bridge connected · v${payload.version ?? "?"}`
                    : "Bridge reported unavailable.";
            })
            .catch((error) => {
                status.dataset.ok = "false";
                label.textContent = `Bridge unavailable: ${error}`;
            });
    }

    return () => {};
}

function renderWorkstationSidebar(element) {
    ensureStyles();
    const shell = document.createElement("div");
    shell.className = "smi-workstation-shell";

    const header = document.createElement("div");
    header.className = "smi-workstation-header";

    const title = document.createElement("div");
    title.className = "smi-workstation-title";
    title.textContent = "Superior MI Workstation";

    const subtitle = document.createElement("div");
    subtitle.className = "smi-workstation-subtitle";
    subtitle.textContent = "Simple guidance beside the real ComfyUI graph.";

    header.append(title, subtitle);

    const nav = document.createElement("div");
    nav.className = "smi-workstation-nav";

    const panel = document.createElement("div");
    panel.className = "smi-workstation-panel";

    const sections = ["Home", "Create", "Activity", "System"];
    const buttons = new Map();
    let cleanupSection = () => {};

    const activate = (section) => {
        cleanupSection();
        for (const [name, button] of buttons) {
            button.dataset.active = name === section ? "true" : "false";
        }
        cleanupSection = renderSection(panel, section);
    };

    for (const section of sections) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = section;
        button.dataset.active = "false";
        button.addEventListener("click", () => activate(section));
        buttons.set(section, button);
        nav.appendChild(button);
    }

    shell.append(header, nav, panel);
    element.replaceChildren(shell);
    activate("Home");
}

function registerWorkstationSidebar() {
    const manager = app.extensionManager;
    if (!manager?.registerSidebarTab) {
        console.warn("[Superior MI] ComfyUI sidebar extension API is unavailable.");
        return;
    }

    const existing = manager.getSidebarTabs?.() || [];
    if (existing.some((tab) => tab?.id === SIDEBAR_ID)) {
        return;
    }

    manager.registerSidebarTab({
        id: SIDEBAR_ID,
        icon: "pi pi-sparkles",
        title: "Superior MI",
        tooltip: "Superior MI Workstation",
        type: "custom",
        render: renderWorkstationSidebar,
    });
}

async function loadWorkflowPath(path) {
    if (!path) return;
    try {
        const response = await app.api.getUserData(path);
        if (!response.ok) {
            throw new Error(`Could not read ${path}: HTTP ${response.status}`);
        }
        const workflow = await response.json();
        await app.loadGraphData(workflow, true, true, true);
        console.info("[Superior MI] Opened workflow:", path);
    } catch (error) {
        console.error("[Superior MI] Could not open workflow", error);
        toastError("Could not open the requested workflow.");
    }
}

app.registerExtension({
    name: EXTENSION_NAME,
    async setup() {
        registerWorkstationSidebar();

        app.api.addEventListener("superior_mi.open_workflow", ({ detail }) => {
            loadWorkflowPath(detail?.path);
        });

        // Covers the case where Workstation requests a workflow before this
        // extension has finished connecting to the ComfyUI websocket.
        try {
            const response = await app.api.fetchApi("/superior-mi/pending-workflow?consume=1");
            if (response.ok) {
                const payload = await response.json();
                if (payload?.pending?.path) {
                    await loadWorkflowPath(payload.pending.path);
                }
            }
        } catch (error) {
            console.debug("[Superior MI] No pending workflow:", error);
        }
    },
});
