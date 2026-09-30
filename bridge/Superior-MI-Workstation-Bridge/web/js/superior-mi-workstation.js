import { app } from "../../scripts/app.js";

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
    }
}

app.registerExtension({
    name: "SuperiorMI.WorkstationBridge",
    async setup() {
        app.api.addEventListener("superior_mi.open_workflow", ({ detail }) => {
            loadWorkflowPath(detail?.path);
        });

        // Covers the case where the Workstation opens the browser before this
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
