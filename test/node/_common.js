"use strict";
// Shared helpers for the node test scripts. Not meant to be run directly.
// Requires Node 18+ (uses the built-in global `fetch`), no npm deps needed.

const fs = require("fs");
const path = require("path");

const ROOT_DIR = path.join(__dirname, "..", "..");
const ENV_FILE = path.join(ROOT_DIR, ".env");

function loadEnvFile() {
  const env = {};
  if (fs.existsSync(ENV_FILE)) {
    for (const line of fs.readFileSync(ENV_FILE, "utf8").split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const idx = trimmed.indexOf("=");
      if (idx === -1) continue;
      env[trimmed.slice(0, idx).trim()] = trimmed.slice(idx + 1).trim();
    }
  }
  return env;
}

function getConfig() {
  const env = loadEnvFile();
  return {
    baseUrl: process.env.BASE_URL || "http://localhost:8000",
    apiToken: process.env.API_TOKEN || env.API_TOKEN || "your-secret-token-here",
    ollamaDefaultModel:
      process.env.OLLAMA_DEFAULT_MODEL || env.OLLAMA_DEFAULT_MODEL || "llama3.2",
  };
}

async function postChat(endpoint, body, token) {
  const { baseUrl, apiToken } = getConfig();
  const res = await fetch(`${baseUrl}${endpoint}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token || apiToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  return { status: res.status, json };
}

async function getJson(endpoint) {
  const { baseUrl } = getConfig();
  const res = await fetch(`${baseUrl}${endpoint}`);
  const json = await res.json().catch(() => ({}));
  return { status: res.status, json };
}

function printResult({ status, json }) {
  console.log(`HTTP ${status}`);
  console.log(JSON.stringify(json, null, 2));
}

module.exports = { getConfig, postChat, getJson, printResult };
