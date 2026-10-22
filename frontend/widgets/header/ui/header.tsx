"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

import { AuthModal } from "@/features/auth/ui/auth-modal";

import type { AuthMode } from "@/features/auth/model/types";

export function Header() {
  const [authMode, setAuthMode] = useState<AuthMode | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    setUserEmail(window.localStorage.getItem("cashflow_user_email"));
    const savedTheme = window.localStorage.getItem("cashflow_theme");
    if (savedTheme === "dark" || savedTheme === "light") {
      setTheme(savedTheme);
      document.documentElement.dataset.theme = savedTheme;
    }
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    window.localStorage.setItem("cashflow_theme", nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  }

  function handleAuthenticated(email: string) {
    window.localStorage.setItem("cashflow_user_email", email);
    setUserEmail(email);
  }

  function logout() {
    window.localStorage.removeItem("cashflow_access_token");
    window.localStorage.removeItem("cashflow_user_email");
    setUserEmail(null);
  }

  return (
    <header className="site-header">
      <a className="brand" href="/" aria-label="CashFlow Radar, на главную">
        CashFlow Radar
      </a>

      <div className="header-actions">
        <button
          className="theme-button"
          type="button"
          aria-label={theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
          title={theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
          onClick={toggleTheme}
        >
          {theme === "light" ? <Sun className="theme-icon" aria-hidden="true" /> : <Moon className="theme-icon" aria-hidden="true" />}
        </button>
        {userEmail ? (
          <>
            <span className="user-chip">{userEmail}</span>
            <button className="text-button" type="button" onClick={logout}>
              Выйти
            </button>
          </>
        ) : (
          <>
            <button className="text-button" type="button" onClick={() => setAuthMode("login")}>
              Войти
            </button>
            <button className="header-cta" type="button" onClick={() => setAuthMode("register")}>
              Создать профиль
            </button>
          </>
        )}
      </div>

      {authMode && (
        <AuthModal
          mode={authMode}
          onClose={() => setAuthMode(null)}
          onModeChange={setAuthMode}
          onAuthenticated={handleAuthenticated}
        />
      )}
    </header>
  );
}
