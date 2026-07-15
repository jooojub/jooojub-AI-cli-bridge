#!/usr/bin/env node
"use strict";
// Test POST /v1/claude/chat
//
// Usage: node claude.js ["prompt"] [interactive_mode] [timeout]
//   prompt            default: "What is 2+2? Answer in one short sentence."
//   interactive_mode  accept | reject (default: reject)
//   timeout           seconds (default: 30)

const { postChat, printResult } = require("./_common");

async function main() {
  const prompt = process.argv[2] || "What is 2+2? Answer in one short sentence.";
  const interactiveMode = process.argv[3] || "reject";
  const timeout = Number(process.argv[4] || 30);

  const result = await postChat("/v1/claude/chat", {
    prompt,
    interactive_mode: interactiveMode,
    timeout,
  });
  printResult(result);
  process.exit(result.json.success ? 0 : 1);
}

main().catch((err) => {
  console.error("Request failed:", err.message);
  process.exit(1);
});
