import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/silkscreen/400.css";

import { App } from "./app/App";
import { applyTheme, readStoredTheme } from "./lib/theme";
import "./styles/index.css";

applyTheme(readStoredTheme());

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element #root was not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
