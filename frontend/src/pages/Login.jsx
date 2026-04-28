import React, { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Wheat, KeyRound } from "lucide-react";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { user, login, loading } = useAuth();
  const [email, setEmail] = useState("admin@agrocrm.com");
  const [password, setPassword] = useState("Admin@123");
  const [err, setErr] = useState("");
  const nav = useNavigate();

  if (user) return <Navigate to="/dashboard" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    const r = await login(email, password);
    if (r.ok) nav("/dashboard");
    else setErr(r.error);
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-app-bg">
      {/* Left — Brand panel */}
      <div className="hidden lg:flex flex-col justify-between p-10 relative overflow-hidden border-r border-border-subtle">
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              "url('https://static.prod-images.emergentagent.com/jobs/5235ba3d-5fb3-48c4-85ea-ed7b9eb35f96/images/2fe2d8896839e1d00557f8818e7571e894d479d4ebe7d0f3f5faccbe3d859f48.png')",
            backgroundSize: "cover", backgroundPosition: "center",
          }}
        />
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-primary/10 border border-primary/40 flex items-center justify-center">
            <Wheat className="text-primary" size={22} strokeWidth={1.8} />
          </div>
          <div>
            <div className="font-head font-bold text-2xl tracking-tight">Agro<span className="text-primary">CRM</span></div>
            <div className="overline">Trading Terminal — Grãos · Insumos · Barter</div>
          </div>
        </div>
        <div className="relative z-10">
          <h1 className="font-head text-5xl font-bold tracking-tight leading-tight">
            O command center
            <br />
            do <span className="text-primary">agronegócio</span>
            <br />
            em tempo real.
          </h1>
          <p className="text-muted mt-5 max-w-md leading-relaxed">
            CRM standalone para trading de grãos com pipeline, contratos, barter,
            logística e <span className="text-accent-yellow">3 agentes de IA</span> — operável em pátio
            offline-first.
          </p>
          <div className="flex gap-2 mt-8">
            <span className="tag tag-green">Offline-first</span>
            <span className="tag tag-yellow">GPT-5.2</span>
            <span className="tag tag-orange">SAP / Oracle</span>
          </div>
        </div>
        <div className="relative z-10 text-xs text-muted font-mono">
          v1.0.0 · POSIX · TLS · TENANT-DEFAULT
        </div>
      </div>

      {/* Right — Form */}
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm card-surface p-8" data-testid="login-form">
          <div className="flex items-center gap-2 mb-6 lg:hidden">
            <Wheat className="text-primary" size={22} strokeWidth={1.8} />
            <div className="font-head font-bold text-xl">Agro<span className="text-primary">CRM</span></div>
          </div>
          <div className="overline mb-1">Acesso</div>
          <h2 className="font-head text-3xl font-bold tracking-tight mb-1">Entrar</h2>
          <p className="text-muted text-sm mb-6">Use sua conta do trading desk.</p>

          <label className="overline block mb-2">E-mail</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input-field mb-4 font-mono"
            data-testid="login-email"
            required
          />

          <label className="overline block mb-2">Senha</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input-field mb-2 font-mono"
            data-testid="login-password"
            required
          />

          {err && <div className="text-accent-red text-sm mb-3" data-testid="login-error">{err}</div>}

          <button type="submit" disabled={loading} className="btn-primary w-full mt-4 flex items-center justify-center gap-2" data-testid="login-submit">
            <KeyRound size={16} strokeWidth={1.8} />
            {loading ? "Autenticando..." : "Entrar"}
          </button>

          <div className="mt-6 text-xs text-muted text-center font-mono">
            <div><span className="text-accent-yellow">DEMO</span> admin@agrocrm.com · Admin@123</div>
            <div>trader@agrocrm.com · Trader@123</div>
          </div>
        </form>
      </div>
    </div>
  );
}
