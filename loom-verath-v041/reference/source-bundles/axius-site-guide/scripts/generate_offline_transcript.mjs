#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  console.error("Usage: node generate_offline_transcript.mjs <input.json> <output.txt>");
  process.exit(1);
}

const input = JSON.parse(await readFile(inputPath, "utf8"));
for (const key of ["title", "status", "transcript"]) {
  if (typeof input[key] !== "string" || !input[key].trim()) throw new Error(`Missing required string: ${key}`);
}

const output = [
  "AXIUS SITE GUIDE — OFFLINE TRANSCRIPT",
  "",
  `Title: ${input.title.trim()}`,
  `Evidence status: ${input.status.trim()}`,
  "Source: Public Site Guide context",
  "Privacy: This local file contains no visitor responses or personal data.",
  "",
  "TRANSCRIPT",
  input.transcript.trim(),
  "",
  "Read this transcript with its evidence-status context; it does not elevate research material into verified capability.",
].join("\n");

await writeFile(outputPath, `${output}\n`, "utf8");
console.log(`Wrote ${outputPath}`);
