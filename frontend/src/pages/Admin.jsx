import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card, EmptyState, Loading, PageHeader, PaginationBar, StatusTag } from "../components/UI";
import { Download, Plus, Save, Shield, UserPlus } from "lucide-react";

const EMPTY_USER = {
  email: "",
  name: "",
  password: "",
  role: "trader",
  branch_scope: "selected",
  branch_ids: [],
};

const EMPTY_BRANCH = {
  name: "",
  code: "",
  city: "",
  state: "",
  document: "",
  is_headquarters: false,
  status: "active",
};

export default function Admin() {
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState({ items: [], total: 0, skip: 0, limit: 20 });
  const [branches, setBranches] = useState([]);
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [clients, setClients] = useState([]);
  const [aiUsage, setAiUsage] = useState(null);
  const [aiPolicy, setAiPolicy] = useState({});
  const [selectedClientId, setSelectedClientId] = useState("");
  const [loading, setLoading] = useState(true);
  const [userForm, setUserForm] = useState(EMPTY_USER);
  const [branchForm, setBranchForm] = useState(EMPTY_BRANCH);
  const [drafts, setDrafts] = useState({});
  const [err, setErr] = useState("");

  const roleIds = useMemo(() => roles.map((r) => r.id), [roles]);

  const load = useCallback(async (nextSkip = 0, nextLimit = 20) => {
    setLoading(true);
    setErr("");
    try {
      const [u, b, r] = await Promise.all([
        api.get("/admin/users", { params: { skip: nextSkip, limit: nextLimit } }),
        api.get("/admin/branches"),
        api.get("/admin/roles"),
      ]);
      setUsers({ ...u.data, skip: nextSkip, limit: nextLimit });
      setBranches(b.data.items);
      setRoles(r.data.roles);
      setPermissions(r.data.permissions);
      api.get("/clients", { params: { limit: 200 } }).then((c) => {
        setClients(c.data.items || []);
        setSelectedClientId((current) => current || c.data.items?.[0]?.id || "");
      }).catch(() => {});
      api.get("/ai/usage").then((a) => {
        setAiUsage(a.data);
        setAiPolicy(a.data.policy || {});
      }).catch(() => {});
      setDrafts(Object.fromEntries(u.data.items.map((item) => [item.id, {
        role: item.role,
        branch_scope: item.branch_scope,
        branch_ids: item.branch_ids || [],
      }])));
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(0, 20); }, [load]);

  const createUser = async (e) => {
    e.preventDefault();
    const payload = {
      ...userForm,
      branch_ids: userForm.branch_scope === "selected" ? (userForm.branch_ids.length ? userForm.branch_ids : [firstBranch]) : [],
    };
    await api.post("/admin/users", payload);
    setUserForm(EMPTY_USER);
    load(0, users.limit);
  };

  const createBranch = async (e) => {
    e.preventDefault();
    await api.post("/admin/branches", branchForm);
    setBranchForm(EMPTY_BRANCH);
    load(users.skip, users.limit);
  };

  const saveUser = async (row) => {
    await api.patch(`/admin/users/${row.id}`, drafts[row.id]);
    load(users.skip, users.limit);
  };

  const toggleUser = async (row) => {
    const suspended = row.status === "suspended" || row.membership_status === "suspended";
    await api.patch(`/admin/users/${row.id}`, {
      status: suspended ? "active" : "suspended",
      user_status: suspended ? "active" : "suspended",
    });
    load(users.skip, users.limit);
  };

  const toggleBranch = async (branch) => {
    await api.patch(`/admin/branches/${branch.id}`, {
      status: branch.status === "active" ? "inactive" : "active",
    });
    load(users.skip, users.limit);
  };

  const exportLgpd = async () => {
    const { data } = await api.get("/admin/lgpd/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tenant-${data.tenant_id}-export.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const anonymizeClient = async () => {
    if (!selectedClientId) return;
    if (!window.confirm("Confirmar anonimizacao LGPD deste cliente? Esta acao altera dados pessoais.")) return;
    await api.post(`/admin/lgpd/clients/${selectedClientId}/anonymize`);
    load(users.skip, users.limit);
  };

  const saveAiPolicy = async () => {
    const payload = Object.fromEntries(
      Object.entries(aiPolicy).map(([k, v]) => [k, Number(v)])
    );
    const { data } = await api.patch("/ai/settings", payload);
    setAiPolicy(data.ai_policy || {});
    const usage = await api.get("/ai/usage");
    setAiUsage(usage.data);
  };

  const updateDraft = (userId, patch) => {
    setDrafts((cur) => ({ ...cur, [userId]: { ...(cur[userId] || {}), ...patch } }));
  };

  const firstBranch = branches[0]?.id || "";

  return (
    <div data-testid="admin-page">
      <PageHeader
        title="Administracao"
        subtitle="Usuarios, filiais, roles e permissoes efetivas do tenant atual."
      />

      <div className="flex gap-2 mb-4 overflow-x-auto max-w-full pb-1">
        {[
          ["users", "Usuarios"],
          ["branches", "Filiais"],
          ["roles", "Roles"],
          ["ai", "IA"],
          ["lgpd", "LGPD"],
        ].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} className={`${tab === id ? "btn-primary" : "btn-ghost"} shrink-0 !px-3 text-sm sm:!px-4 sm:text-base`}>
            {label}
          </button>
        ))}
      </div>

      {err && <div className="text-accent-red text-sm mb-3">{err}</div>}
      {loading ? <Loading /> : (
        <>
          {tab === "users" && (
            <div className="space-y-4">
              <Card lift={false}>
                <form onSubmit={createUser} className="grid grid-cols-1 lg:grid-cols-6 gap-3 items-end">
                  <div>
                    <label className="overline">Nome</label>
                    <input className="input-field" required value={userForm.name} onChange={(e) => setUserForm({ ...userForm, name: e.target.value })} />
                  </div>
                  <div>
                    <label className="overline">E-mail</label>
                    <input className="input-field font-mono" type="email" required value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} />
                  </div>
                  <div>
                    <label className="overline">Senha inicial</label>
                    <input className="input-field font-mono" type="password" required minLength={8} value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} />
                  </div>
                  <div>
                    <label className="overline">Role</label>
                    <select className="input-field" value={userForm.role} onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}>
                      {roleIds.map((role) => <option key={role} value={role}>{role}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="overline">Filial</label>
                    <select
                      className="input-field"
                      value={userForm.branch_ids[0] || firstBranch}
                      onChange={(e) => setUserForm({ ...userForm, branch_scope: "selected", branch_ids: [e.target.value] })}
                    >
                      {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                    </select>
                  </div>
                  <button type="submit" className="btn-primary flex items-center justify-center gap-2">
                    <UserPlus size={16} /> Convidar
                  </button>
                </form>
              </Card>

              <Card lift={false} className="!p-0 overflow-hidden">
                {users.items.length === 0 ? <EmptyState /> : (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead><tr>
                        <th>Usuario</th><th>Status</th><th>Role</th><th>Escopo</th><th>Filial</th><th>Perms</th><th></th>
                      </tr></thead>
                      <tbody>
                        {users.items.map((row) => {
                          const draft = drafts[row.id] || {};
                          const suspended = row.status === "suspended" || row.membership_status === "suspended";
                          return (
                            <tr key={row.id}>
                              <td>
                                <div className="font-medium">{row.name}</div>
                                <div className="text-xs text-muted font-mono">{row.email}</div>
                              </td>
                              <td><StatusTag status={suspended ? "suspended" : "active"} /></td>
                              <td>
                                <select className="input-field !py-1 !text-xs min-w-44" value={draft.role || row.role}
                                        onChange={(e) => updateDraft(row.id, { role: e.target.value })}>
                                  {roleIds.map((role) => <option key={role} value={role}>{role}</option>)}
                                </select>
                              </td>
                              <td>
                                <select className="input-field !py-1 !text-xs min-w-32" value={draft.branch_scope || row.branch_scope}
                                        onChange={(e) => updateDraft(row.id, { branch_scope: e.target.value, branch_ids: e.target.value === "all" ? [] : (draft.branch_ids?.length ? draft.branch_ids : [firstBranch]) })}>
                                  <option value="selected">selected</option>
                                  <option value="all">all</option>
                                </select>
                              </td>
                              <td>
                                {(draft.branch_scope || row.branch_scope) === "all" ? (
                                  <span className="tag tag-green">Todas</span>
                                ) : (
                                  <select className="input-field !py-1 !text-xs min-w-40" value={(draft.branch_ids || row.branch_ids || [])[0] || firstBranch}
                                          onChange={(e) => updateDraft(row.id, { branch_ids: [e.target.value] })}>
                                    {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                                  </select>
                                )}
                              </td>
                              <td className="font-mono text-xs">{row.effective_permissions?.length || 0}</td>
                              <td>
                                <div className="flex gap-2 justify-end">
                                  <button className="btn-ghost !py-1 !px-2 text-xs" onClick={() => saveUser(row)}>
                                    <Save size={12} className="inline mr-1" /> Salvar
                                  </button>
                                  <button className="btn-ghost !py-1 !px-2 text-xs" onClick={() => toggleUser(row)}>
                                    {suspended ? "Ativar" : "Suspender"}
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                {users.items.length > 0 && (
                  <PaginationBar
                    total={users.total}
                    skip={users.skip}
                    limit={users.limit}
                    onPageChange={(nextSkip) => load(nextSkip, users.limit)}
                    onLimitChange={(nextLimit) => load(0, nextLimit)}
                  />
                )}
              </Card>
            </div>
          )}

          {tab === "branches" && (
            <div className="space-y-4">
              <Card lift={false}>
                <form onSubmit={createBranch} className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
                  <div className="md:col-span-2">
                    <label className="overline">Nome</label>
                    <input className="input-field" required value={branchForm.name} onChange={(e) => setBranchForm({ ...branchForm, name: e.target.value })} />
                  </div>
                  <div>
                    <label className="overline">Codigo</label>
                    <input className="input-field font-mono" required value={branchForm.code} onChange={(e) => setBranchForm({ ...branchForm, code: e.target.value })} />
                  </div>
                  <div>
                    <label className="overline">Cidade</label>
                    <input className="input-field" value={branchForm.city} onChange={(e) => setBranchForm({ ...branchForm, city: e.target.value })} />
                  </div>
                  <div>
                    <label className="overline">UF</label>
                    <input className="input-field" maxLength={2} value={branchForm.state} onChange={(e) => setBranchForm({ ...branchForm, state: e.target.value.toUpperCase() })} />
                  </div>
                  <button type="submit" className="btn-primary flex items-center justify-center gap-2">
                    <Plus size={16} /> Filial
                  </button>
                </form>
              </Card>
              <Card lift={false} className="!p-0 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="data-table">
                    <thead><tr><th>Codigo</th><th>Nome</th><th>Cidade</th><th>Status</th><th></th></tr></thead>
                    <tbody>
                      {branches.map((b) => (
                        <tr key={b.id}>
                          <td className="font-mono text-muted">{b.code}</td>
                          <td className="font-medium">{b.name}</td>
                          <td>{[b.city, b.state].filter(Boolean).join(" / ") || "-"}</td>
                          <td><StatusTag status={b.status} /></td>
                          <td className="text-right">
                            <button className="btn-ghost !py-1 !px-2 text-xs" onClick={() => toggleBranch(b)}>
                              {b.status === "active" ? "Inativar" : "Ativar"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {tab === "roles" && (
            <Card lift={false} className="!p-0 overflow-hidden">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 p-4">
                {roles.map((role) => (
                  <div key={role.id} className="border border-border-subtle rounded-lg p-4">
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <div className="flex items-center gap-2">
                        <Shield size={15} className="text-primary" />
                        <div className="font-head font-semibold">{role.id}</div>
                      </div>
                      <span className="tag tag-muted font-mono">{role.permissions.length}/{permissions.length}</span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {role.permissions.slice(0, 18).map((p) => <span key={p} className="tag tag-muted !text-[0.65rem]">{p}</span>)}
                      {role.permissions.length > 18 && <span className="tag tag-yellow !text-[0.65rem]">+{role.permissions.length - 18}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {tab === "ai" && (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <Card lift={false}>
                <div className="overline mb-2">Provider</div>
                <div className="font-head font-semibold text-xl">{aiUsage?.provider || "-"}</div>
                <div className="text-muted text-sm font-mono mt-1">{aiUsage?.model || "-"}</div>
              </Card>
              <Card lift={false}>
                <div className="overline mb-2">Hoje / usuario</div>
                <div className="font-head font-semibold text-xl">{aiUsage?.user_day?.calls || 0} chamadas</div>
                <div className="text-muted text-sm font-mono mt-1">{aiUsage?.user_day?.tokens || 0} tokens</div>
                <div className="text-muted text-xs font-mono mt-1">{aiUsage?.user_day?.blocked || 0} bloqueadas</div>
              </Card>
              <Card lift={false}>
                <div className="overline mb-2">Mes / tenant</div>
                <div className="font-head font-semibold text-xl">{aiUsage?.tenant_month?.calls || 0} chamadas</div>
                <div className="text-muted text-sm font-mono mt-1">{aiUsage?.tenant_month?.tokens || 0} tokens</div>
                <div className="text-muted text-xs font-mono mt-1">{aiUsage?.tenant_month?.blocked || 0} bloqueadas</div>
              </Card>
              <Card lift={false} className="xl:col-span-3">
                <div className="overline mb-3">Rate limit e orcamento</div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
                  {[
                    ["user_per_minute", "Usuario/min"],
                    ["user_daily_limit", "Usuario/dia"],
                    ["tenant_daily_limit", "Tenant/dia"],
                    ["monthly_token_budget", "Tokens/mes"],
                    ["max_input_chars", "Chars entrada"],
                    ["max_output_tokens", "Tokens saida"],
                    ["cache_ttl_seconds", "Cache TTL"],
                  ].map(([key, label]) => (
                    <div key={key}>
                      <label className="overline">{label}</label>
                      <input
                        className="input-field font-mono"
                        type="number"
                        min={1}
                        value={aiPolicy[key] || ""}
                        onChange={(e) => setAiPolicy({ ...aiPolicy, [key]: e.target.value })}
                      />
                    </div>
                  ))}
                  <button className="btn-primary" onClick={saveAiPolicy}>Salvar IA</button>
                </div>
              </Card>
            </div>
          )}

          {tab === "lgpd" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card lift={false}>
                <div className="overline mb-2">Exportacao</div>
                <div className="font-head font-semibold text-lg mb-2">Dados do tenant</div>
                <p className="text-muted text-sm mb-4">Gera um pacote JSON tenant-scoped sem hashes de senha.</p>
                <button className="btn-primary flex items-center gap-2" onClick={exportLgpd}>
                  <Download size={16} /> Exportar JSON
                </button>
              </Card>
              <Card lift={false}>
                <div className="overline mb-2">Anonimizacao</div>
                <div className="font-head font-semibold text-lg mb-2">Cliente/produtor</div>
                <p className="text-muted text-sm mb-4">Remove campos pessoais e atualiza nomes denormalizados vinculados.</p>
                <div className="flex flex-col md:flex-row gap-3">
                  <select className="input-field" value={selectedClientId} onChange={(e) => setSelectedClientId(e.target.value)}>
                    {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
                  </select>
                  <button className="btn-ghost shrink-0" onClick={anonymizeClient}>Anonimizar</button>
                </div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
