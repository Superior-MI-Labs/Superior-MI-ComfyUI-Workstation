const NUMERIC_TYPES = new Set(["number", "slider"]);
const BOOLEAN_TYPES = new Set(["toggle", "boolean"]);
const TEXT_TYPES = new Set(["text", "string", "customtext"]);

function humanize(name) {
    return String(name ?? "")
        .replace(/[-_]+/g, " ")
        .trim()
        .replace(/\b\w/g, (match) => match.toUpperCase());
}

function classify(name, type) {
    const lower = String(name ?? "").toLowerCase();

    if (lower.includes("prompt")) return { group: "Prompt", priority: "primary" };
    if (["width", "height", "resolution", "aspect_ratio", "aspect"].includes(lower)) {
        return { group: "Resolution", priority: "primary" };
    }
    if (["steps", "seed"].includes(lower)) {
        return { group: "Sampling", priority: "primary" };
    }
    if (["cfg", "guidance", "sampler_name", "sampler", "scheduler", "denoise"].includes(lower)) {
        return { group: "Sampling", priority: "advanced" };
    }
    if (["image", "video", "audio"].includes(type)) {
        return { group: "Inputs", priority: "primary" };
    }
    if (/(model|checkpoint|vae|clip|lora)/.test(lower)) {
        return { group: "Model", priority: "advanced" };
    }
    if (/(filename|output|format|compression)/.test(lower)) {
        return { group: "Output", priority: "advanced" };
    }
    return { group: "Advanced", priority: "advanced" };
}

function choicesFor(widget) {
    const values = widget?.options?.values;
    return Array.isArray(values) ? [...values] : [];
}

function widgetKind(widget) {
    const type = String(widget?.type ?? "").toLowerCase();
    if (type === "combo") return "dropdown";
    if (BOOLEAN_TYPES.has(type)) return "toggle";
    if (NUMERIC_TYPES.has(type)) {
        const options = widget?.options ?? {};
        return options.min != null && options.max != null ? "slider-number" : "number";
    }
    if (TEXT_TYPES.has(type)) {
        return widget?.options?.multiline ? "multiline" : "text";
    }
    if (["image", "video", "audio"].includes(type)) return "file";
    return "text";
}

function dataType(widget) {
    const type = String(widget?.type ?? "").toLowerCase();
    if (type === "combo") return "COMBO";
    if (BOOLEAN_TYPES.has(type)) return "BOOLEAN";
    if (NUMERIC_TYPES.has(type)) {
        return Number.isInteger(widget?.value) ? "INT" : "FLOAT";
    }
    if (TEXT_TYPES.has(type)) return "STRING";
    if (["image", "video", "audio"].includes(type)) return type.toUpperCase();
    return type.toUpperCase() || "*";
}

function controlId(node, widget) {
    return `${node.id}.${widget.name}`;
}

export function deriveGraphControls(graph) {
    const controls = [];
    for (const node of graph?._nodes ?? []) {
        for (const widget of node?.widgets ?? []) {
            if (!widget?.name) continue;
            const type = String(widget.type ?? "").toLowerCase();
            if (type === "button" || widget?.options?.serialize === false) continue;

            const classification = classify(widget.name, type);
            const options = widget.options ?? {};
            controls.push({
                id: controlId(node, widget),
                nodeId: String(node.id),
                nodeType: String(node.type ?? node.comfyClass ?? ""),
                inputName: String(widget.name),
                dataType: dataType(widget),
                value: widget.value,
                widget: widgetKind(widget),
                label: String(widget.label ?? humanize(widget.name)),
                group: classification.group,
                priority: classification.priority,
                minimum: options.min ?? null,
                maximum: options.max ?? null,
                step: options.step ?? null,
                choices: choicesFor(widget),
            });
        }
    }
    return controls;
}

export function findLiveWidget(graph, control) {
    const node = (graph?._nodes ?? []).find((candidate) => String(candidate?.id) === String(control.nodeId));
    if (!node) return null;
    const widget = (node.widgets ?? []).find((candidate) => String(candidate?.name) === String(control.inputName));
    return widget ? { node, widget } : null;
}

export function readLiveControlValue(graph, control) {
    return findLiveWidget(graph, control)?.widget?.value;
}

export function validateControlValue(control, value) {
    if (control.choices?.length && !control.choices.includes(value)) {
        throw new Error(`${control.id} does not accept value ${value}`);
    }

    if (control.dataType === "INT" && (!Number.isInteger(value) || typeof value === "boolean")) {
        throw new Error(`${control.id} requires an integer`);
    }
    if (control.dataType === "FLOAT" && (typeof value !== "number" || !Number.isFinite(value))) {
        throw new Error(`${control.id} requires a finite number`);
    }
    if (control.dataType === "BOOLEAN" && typeof value !== "boolean") {
        throw new Error(`${control.id} requires a boolean`);
    }
    if (control.minimum != null && typeof value === "number" && value < control.minimum) {
        throw new Error(`${control.id} is below its minimum`);
    }
    if (control.maximum != null && typeof value === "number" && value > control.maximum) {
        throw new Error(`${control.id} is above its maximum`);
    }
}

export function writeLiveControlValue(graph, control, value, markDirty = () => {}) {
    validateControlValue(control, value);
    const live = findLiveWidget(graph, control);
    if (!live) {
        throw new Error(`Graph control no longer exists: ${control.id}`);
    }

    live.widget.value = value;
    live.widget.callback?.(value);
    live.node.graph?.change?.();
    markDirty();
    return live.widget.value;
}
