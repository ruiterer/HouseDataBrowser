// Golden-template ESLint-config (flat config) voor Node-projecten
// (D-027 in Portfolio_Manager).
//
// Adoptie:
// 1. Kopieer dit bestand naar de projectroot als eslint.config.js.
// 2. npm install --save-dev eslint @eslint/js
// 3. Prettier hoort erbij: kopieer .prettierrc.json uit dezelfde
//    templatemap mee en npm install --save-dev prettier
// 4. Commando (samen ook geschikt als LINT_CMD in scripts/hooks/pre-commit):
//      npx eslint . && npx prettier --check .
// TypeScript-projecten: voeg typescript-eslint toe volgens hun docs.
//
// Bescheiden regelset: alleen eslint:recommended. Per project uitbreiden
// mag; leg bewuste afwijkingen uit in CLAUDE.md.
//
// HouseDataBrowser-uitbreidingen (conform stap TypeScript hierboven):
// typescript-eslint recommended voor de .ts/.tsx-bronnen, en
// browser-globals voor de plain-JS public/platform-header.js.

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import globals from "globals";

export default [
  { ignores: ["dist/", "build/", "node_modules/"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  { languageOptions: { globals: globals.browser } },
  {
    // Deliberate per-file ignore (approved by Erik, 2026-08-22, D-027
    // pilot lesson 5): these files carry the dynamic agent-data pattern —
    // InfluxDB rows with per-query columns, LLM-built Plotly chart specs,
    // SSE event payloads. Proper typing means an unknown+narrowing
    // refactor across components; new files stay fully guarded.
    files: [
      "src/api/chat.ts",
      "src/api/pins.ts",
      "src/components/ChartRenderer.tsx",
      "src/components/ChatMessage.tsx",
      "src/components/DataTable.tsx",
      "src/pages/Chat.tsx",
    ],
    rules: { "@typescript-eslint/no-explicit-any": "off" },
  },
];
