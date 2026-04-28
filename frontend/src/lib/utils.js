export const fmtBRL = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);

export const fmtNum = (v, opts = {}) =>
  new Intl.NumberFormat("pt-BR", opts).format(v || 0);

export const fmtTon = (v) => `${fmtNum(v, { maximumFractionDigits: 0 })} ton`;

export const fmtDate = (s) => {
  if (!s) return "—";
  try {
    const d = typeof s === "string" ? new Date(s) : s;
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(d);
  } catch (e) { return String(s); }
};

export const cn = (...c) => c.filter(Boolean).join(" ");
