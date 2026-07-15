#!/usr/bin/env node
"use strict";
// TC-style test suite: runs a fixed set of numbered test cases against a live
// bridge instance and reports PASS/FAIL per case plus a summary. Exit code is
// 0 only if every case passed -- safe to use as a CI/smoke-test gate.
//
// Usage: node suite.js
// Config: same as the other test/ scripts -- reads API_TOKEN/OLLAMA_DEFAULT_MODEL
//         from ../../.env, overridable via API_TOKEN/BASE_URL env vars.

const { getConfig, postChat, getJson } = require("./_common");

let pass = 0;
let fail = 0;

function tc(id, desc, ok, detail) {
  if (ok) {
    pass += 1;
    console.log(`[PASS] ${id}: ${desc}`);
  } else {
    fail += 1;
    console.log(`[FAIL] ${id}: ${desc}${detail ? ` -- ${detail}` : ""}`);
  }
}

async function main() {
  // TC01: GET /health -> 200 + {"status":"ok"}
  {
    const { status, json } = await getJson("/health");
    tc("TC01", "GET /health returns 200 + status ok", status === 200 && json.status === "ok", `HTTP ${status} body=${JSON.stringify(json)}`);
  }

  // TC02: valid token -> 200
  {
    const { status } = await postChat("/v1/claude/chat", { prompt: "hi" });
    tc("TC02", "valid token on /v1/claude/chat -> 200", status === 200, `HTTP ${status}`);
  }

  // TC03: invalid token -> 401
  {
    const { status } = await postChat("/v1/claude/chat", { prompt: "hi" }, "wrong-token-xyz");
    tc("TC03", "invalid token on /v1/claude/chat -> 401", status === 401, `HTTP ${status}`);
  }

  // TC04: claude basic chat -> success:true
  {
    const { status, json } = await postChat("/v1/claude/chat", {
      prompt: "What is 2+2? Answer in one short sentence.",
    });
    tc("TC04", "claude basic chat -> success:true", status === 200 && json.success === true, `HTTP ${status} body=${JSON.stringify(json)}`);
  }

  // TC05: gemini/agy basic chat -> success:true
  {
    const { status, json } = await postChat("/v1/gemini/chat", {
      prompt: "What is 2+2? Answer in one short sentence.",
    });
    tc("TC05", "gemini/agy basic chat -> success:true", status === 200 && json.success === true, `HTTP ${status} body=${JSON.stringify(json)}`);
  }

  // TC06: claude skill listing -> success + at least 5 skills reported.
  // Loose on purpose: installed skills vary by machine, and the model
  // doesn't always list every single one deterministically.
  {
    const { status, json } = await postChat(
      "/v1/claude/chat",
      {
        prompt: "List every Skill name you have available via the Skill tool, one per line, nothing else.",
        interactive_mode: "accept",
        timeout: 60,
      }
    );
    const lineCount = status === 200 && json.success ? String(json.response).split("\n").filter((l) => l.trim()).length : 0;
    tc("TC06", "claude skill listing -> success + >=5 skills reported", status === 200 && json.success === true && lineCount >= 5, `HTTP ${status} lines=${lineCount}`);
  }

  // TC07/TC08: interactive_mode actually gates tool use (Write tool),
  // verified by asking claude to write a marker string to a file and read
  // it straight back in the same request -- no filesystem inspection needed.
  const marker = `TC_MARKER_${process.pid}_${Date.now()}`;
  const writePrompt = `Use the Write tool to create /tmp/tc_probe_${process.pid}.txt containing exactly: ${marker} -- then use the Read tool to read that file back and print its exact contents.`;

  // TC07: reject -> the write should be denied, so the marker must NOT appear
  {
    const { status, json } = await postChat("/v1/claude/chat", {
      prompt: writePrompt,
      interactive_mode: "reject",
      timeout: 30,
    });
    const containsMarker = String(json.response || "").includes(marker);
    tc("TC07", "claude interactive_mode=reject blocks Write tool", status === 200 && !containsMarker, `HTTP ${status} body=${JSON.stringify(json)}`);
  }

  // TC08: accept -> the write should succeed, so the marker must appear back
  {
    const { status, json } = await postChat("/v1/claude/chat", {
      prompt: writePrompt,
      interactive_mode: "accept",
      timeout: 30,
    });
    const containsMarker = String(json.response || "").includes(marker);
    tc("TC08", "claude interactive_mode=accept allows Write tool", status === 200 && containsMarker, `HTTP ${status} body=${JSON.stringify(json)}`);
  }

  // TC09: ollama endpoint returns well-formed JSON regardless of whether a
  // real ollama server is reachable on this host (that's an environment
  // concern, not something this bridge's own test suite should assert on).
  {
    const { status, json } = await postChat("/v1/ollama/chat", {
      prompt: "What is the capital of France?",
      timeout: 15,
    });
    tc("TC09", "ollama endpoint responds with well-formed JSON", status === 200 && "model" in json, `HTTP ${status} body=${JSON.stringify(json)}`);
  }

  // TC10: a short timeout bounds the request's wall-clock time (regression
  // guard against the bridge hanging indefinitely on a slow CLI response).
  {
    const start = Date.now();
    const { status } = await postChat("/v1/claude/chat", {
      prompt: "Write a 5000 word essay about the history of computing.",
      timeout: 3,
    });
    const elapsed = (Date.now() - start) / 1000;
    tc("TC10", `claude respects a short timeout (responded in ${elapsed.toFixed(1)}s)`, status === 200 && elapsed <= 25, `HTTP ${status} elapsed=${elapsed.toFixed(1)}s`);
  }

  console.log();
  console.log("===================================================");
  console.log(`Passed: ${pass}  Failed: ${fail}  Total: ${pass + fail}`);
  process.exit(fail === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error("Suite crashed:", err.message);
  process.exit(1);
});
