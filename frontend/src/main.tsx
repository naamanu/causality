import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import LandingPage from "./LandingPage";
import "./index.css";

const isProductRoute = window.location.pathname === "/app" || window.location.pathname.startsWith("/app/");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {isProductRoute ? <App /> : <LandingPage />}
  </React.StrictMode>,
);
