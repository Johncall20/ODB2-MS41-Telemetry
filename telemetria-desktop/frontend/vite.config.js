import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento a UI roda na 5173 e o backend na 8000.
// O proxy evita CORS e faz o codigo do frontend usar caminhos relativos,
// os mesmos que valem depois do build, quando o FastAPI serve o dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  // Classe fica kebab-case no .module.css e chega camelCase no JS.
  css: { modules: { localsConvention: "camelCase" } },
  build: { outDir: "dist" },
});
