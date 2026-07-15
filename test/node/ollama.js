#!/usr/bin/env node
"use strict";
// Test POST /v1/ollama/chat
//
// Usage: node ollama.js ["prompt"] [model] [interactive_mode] [timeout]
//   prompt            default: "What is the capital of France?"
//   model             default: OLLAMA_DEFAULT_MODEL from .env, else llama3.2
//   interactive_mode  accept | reject (default: reject)
//   timeout           seconds (default: 30)

const { getConfig, postChat, printResult } = require("./_common");

async function main() {
  const prompt = process.argv[2] || "What is the capital of France?";
  const model = process.argv[3] || getConfig().ollamaDefaultModel;
  const interactiveMode = process.argv[4] || "reject";
  const timeout = Number(process.argv[5] || 30);

  const result = await postChat("/v1/ollama/chat", {
    prompt,
    model,
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
