import React from "react";

export function PageHeader({ title, subtitle, actions, testid }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 mb-6" data-testid={testid}>
      <div>
        <div className="overline">Módulo</div>
        <h1 className="font-head text-3xl md:text-[2.1rem] font-bold tracking-tight mt-1">{title}</h1>
        {subtitle && <p className="text-muted mt-2 max-w-2xl text-sm leading-relaxed">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ children, className = "", testid, lift = true }) {
  return (
    <div className={`card-surface ${lift ? "card-lift" : ""} p-6 ${className}`} data-testid={testid}>
      {children}
    </div>
  );
}

export function StatusTag({ status }) {
  const map = {
    active: ["tag-green", "Ativo"],
    draft: ["tag-muted", "Rascunho"],
    settled: ["tag-muted", "Liquidado"],
    cancelled: ["tag-red", "Cancelado"],
    pending: ["tag-yellow", "Pendente"],
    confirmed: ["tag-green", "Confirmado"],
    in_transit: ["tag-orange", "Em trânsito"],
    delivered: ["tag-green", "Entregue"],
    queue: ["tag-muted", "Pátio"],
    loading: ["tag-yellow", "Carregando"],
    open: ["tag-yellow", "Aberto"],
    in_progress: ["tag-orange", "Em andamento"],
    closed: ["tag-muted", "Fechado"],
    high: ["tag-red", "Alta"],
    medium: ["tag-yellow", "Média"],
    low: ["tag-muted", "Baixa"],
    critical: ["tag-red", "Crítica"],
    sell: ["tag-green", "Venda"],
    buy: ["tag-orange", "Compra"],
    barter: ["tag-yellow", "Barter"],
    sale: ["tag-green", "Venda"],
    purchase: ["tag-orange", "Compra"],
    producer: ["tag-green", "Produtor"],
    company: ["tag-yellow", "Empresa"],
    grain: ["tag-yellow", "Grão"],
    input: ["tag-orange", "Insumo"],
    A: ["tag-green", "Tier A"],
    B: ["tag-yellow", "Tier B"],
    C: ["tag-muted", "Tier C"],
  };
  const [cls, label] = map[status] || ["tag-muted", status || "—"];
  return <span className={`tag ${cls}`}>{label}</span>;
}

export function EmptyState({ title = "Sem registros", hint }) {
  return (
    <div className="text-center py-16">
      <div className="font-head text-xl font-semibold mb-2">{title}</div>
      {hint && <div className="text-muted text-sm">{hint}</div>}
    </div>
  );
}

export function Loading() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-7 h-7 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
