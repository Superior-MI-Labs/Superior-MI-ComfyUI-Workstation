import { app } from "../../scripts/app.js";

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
        .smi-workstation-nav button {
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
    `;
    document.head.appendChild(style);
}

function paragraph(text) {
    const node = document.createElement("p");
    node.textContent = text;
    return node;
}

function renderSection(panel, section) {
    panel.replaceChildren();
    const title = document.createElement("h3");
    title.textContent = section;
    panel.appendChild(title);

    const copy = {
        Home: [
            "Superior MI Workstation operates around the real ComfyUI canvas.",
            "Assistant planning and approval checklists will live here without becoming a second execution authority.",
        ],
        Create: [
            "Simple controls will be derived from the active ComfyUI workflow and live node schema.",
            "The graph remains the value authority. Simple Mode is only a projection of that graph.",
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

    if (section === "Home") {
        const studio = document.createElement("div");
        studio.className = "smi-workstation-status";
        studio.dataset.ok = "true";

        const dot = document.createElement("span");
        dot.className = "smi-workstation-dot";
        const label = document.createElement("span");
        label.textContent = "Studio is the native ComfyUI canvas beside this panel.";

        studio.append(dot, label);
        panel.appendChild(studio);
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

    const activate = (section) => {
        for (const [name, button] of buttons) {
            button.dataset.active = name === section ? "true" : "false";
        }
        renderSection(panel, section);
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
        app.extensionManager?.toast?.add?.({
            severity: "error",
            summary: "Superior MI",
            detail: "Could not open the requested workflow.",
            life: 5000,
        });
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
