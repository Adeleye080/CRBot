// eslint.config.js
import { defineConfig } from "eslint-define-config";
import js from "@eslint/js";

export default defineConfig([
  {
    languageOptions: {
      globals: {
        node: "readonly",
        browser: "readonly",
      },
    },
    rules: {
        'no-unused-vars': 'warn',
    },
  },
]);
