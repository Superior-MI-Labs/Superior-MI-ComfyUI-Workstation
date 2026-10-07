import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const modulePath = process.argv[2];
if (!modulePath) throw new Error("graph-controls module path is required");

const {
  deriveGraphControls,
  readLiveControlValue,
  validateControlValue,
  writeLiveControlValue,
} = await import(modulePath.startsWith("file:") ? modulePath : pathToFileURL(modulePath).href);

let graphChanges = 0;
let dirtyCalls = 0;
let callbackValues = [];

const graph = {
  _nodes: [
    {
      id: 1,
      type: "KSampler",
      graph: { change() { graphChanges += 1; } },
      widgets: [
        {
          name: "steps",
          type: "number",
          value: 24,
          options: { min: 1, max: 100, step: 1 },
          callback(value) { callbackValues.push(["steps", value]); },
        },
        {
          name: "cfg",
          type: "number",
          value: 3,
          options: { min: 0, max: 20, step: 0.1 },
        },
        {
          name: "sampler_name",
          type: "combo",
          value: "euler",
          options: { values: ["euler", "dpmpp_2m"] },
          callback(value) { callbackValues.push(["sampler", value]); },
        },
        {
          name: "seed",
          type: "number",
          value: 1234,
          options: { min: 0, max: 999999999, step: 1 },
        },
        {
          name: "queue_button",
          type: "button",
          value: null,
        },
      ],
    },
    {
      id: 2,
      type: "CLIPTextEncode",
      graph: { change() { graphChanges += 1; } },
      widgets: [
        {
          name: "prompt",
          type: "customtext",
          value: "a lighthouse",
          options: { multiline: true },
          callback(value) { callbackValues.push(["prompt", value]); },
        },
        {
          name: "mystery_control",
          type: "third_party_magic",
          value: { opaque: true },
        },
        {
          name: "internal",
          type: "text",
          value: "hidden",
          options: { serialize: false },
        },
      ],
    },
  ],
};

const controls = deriveGraphControls(graph);
const byId = Object.fromEntries(controls.map((control) => [control.id, control]));

assert.equal(controls.length, 6);
assert.equal(byId["1.steps"].widget, "slider-number");
assert.equal(byId["1.steps"].group, "Sampling");
assert.equal(byId["1.steps"].priority, "primary");
assert.equal(byId["1.cfg"].priority, "advanced");
assert.equal(byId["1.cfg"].dataType, "FLOAT");
assert.equal(byId["1.sampler_name"].widget, "dropdown");
assert.deepEqual(byId["1.sampler_name"].choices, ["euler", "dpmpp_2m"]);
assert.equal(byId["2.prompt"].widget, "multiline");
assert.equal(byId["2.prompt"].group, "Prompt");
assert.equal(byId["2.mystery_control"].widget, "unsupported");
assert.equal(byId["2.mystery_control"].editable, false);
assert.equal(byId["1.queue_button"], undefined);
assert.equal(byId["2.internal"], undefined);

const writtenSteps = writeLiveControlValue(
  graph,
  byId["1.steps"],
  32,
  () => { dirtyCalls += 1; },
);
assert.equal(writtenSteps, 32);
assert.equal(graph._nodes[0].widgets[0].value, 32);
assert.deepEqual(callbackValues[0], ["steps", 32]);
assert.equal(graphChanges, 1);
assert.equal(dirtyCalls, 1);

writeLiveControlValue(
  graph,
  byId["1.sampler_name"],
  "dpmpp_2m",
  () => { dirtyCalls += 1; },
);
assert.equal(graph._nodes[0].widgets[2].value, "dpmpp_2m");
assert.deepEqual(callbackValues.at(-1), ["sampler", "dpmpp_2m"]);

assert.throws(
  () => validateControlValue(byId["1.steps"], 101),
  /maximum/,
);
assert.throws(
  () => validateControlValue(byId["1.steps"], 10.5),
  /integer/,
);
assert.throws(
  () => validateControlValue(byId["1.sampler_name"], "invented"),
  /does not accept/,
);
assert.throws(
  () => writeLiveControlValue(graph, byId["2.mystery_control"], "bad"),
  /not editable/,
);

graph._nodes[0].widgets[0].value = 48;
assert.equal(readLiveControlValue(graph, byId["1.steps"]), 48);

graph._nodes[1].widgets[0].value = "changed in Studio";
assert.equal(readLiveControlValue(graph, byId["2.prompt"]), "changed in Studio");

console.log(`js_graph_controls=PASS controls=${controls.length}`);
