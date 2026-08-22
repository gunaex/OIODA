import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import App from "./App";
import "./index.css";

const app = (
  <BrowserRouter>
    <AuthProvider>
      <App />
    </AuthProvider>
  </BrowserRouter>
);

// Keep effect replay as a development diagnostic without duplicating every
// authenticated owner read in the production application.
createRoot(document.getElementById("root")).render(
  import.meta.env.DEV ? <React.StrictMode>{app}</React.StrictMode> : app
);
