"use client";

import { FormEvent, useState } from "react";
import { X } from "lucide-react";

import { loginUser, registerUser } from "@/shared/api/client";

import type { AuthMode } from "../model/types";

type AuthModalProps = {
  mode: AuthMode;
  onClose: () => void;
  onModeChange: (mode: AuthMode) => void;
  onAuthenticated: (email: string) => void;
};

export function AuthModal({
  mode,
  onClose,
  onModeChange,
  onAuthenticated,
}: AuthModalProps) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const isRegister = mode === "register";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      if (isRegister) {
        await registerUser({ full_name: fullName, email, password });
      }

      const auth = await loginUser({ email, password });
      window.localStorage.setItem("cashflow_access_token", auth.access_token);
      onAuthenticated(email);
      onClose();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Ошибка входа");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-topline">
          <span className="modal-kicker">Доступ к контуру</span>
          <button className="icon-button" type="button" aria-label="Закрыть" onClick={onClose}>
            <X aria-hidden="true" />
          </button>
        </div>

        <h2 id="auth-modal-title">{isRegister ? "Создать рабочий профиль" : "Войти в систему"}</h2>
        <p className="modal-description">
          {isRegister
            ? "Начните с доступа казначея. Роль CFO назначается отдельно."
            : "Введите рабочий email и пароль для доступа к данным компании."}
        </p>

        <div className="auth-tabs" role="tablist" aria-label="Тип операции">
          <button
            className={mode === "login" ? "auth-tab auth-tab--active" : "auth-tab"}
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            onClick={() => onModeChange("login")}
          >
            Вход
          </button>
          <button
            className={mode === "register" ? "auth-tab auth-tab--active" : "auth-tab"}
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            onClick={() => onModeChange("register")}
          >
            Регистрация
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegister && (
            <label>
              <span>Имя</span>
              <input
                required
                minLength={1}
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Иван Петров"
              />
            </label>
          )}
          <label>
            <span>Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.ru"
            />
          </label>
          <label>
            <span>Пароль</span>
            <input
              required
              minLength={8}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Минимум 8 символов"
            />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}

          <button className="submit-button" type="submit" disabled={isLoading}>
            {isLoading ? "Проверяем данные…" : isRegister ? "Создать профиль" : "Войти"}
          </button>
        </form>
      </section>
    </div>
  );
}
