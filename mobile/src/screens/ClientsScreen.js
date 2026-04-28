import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, TextInput, Modal, ActivityIndicator } from "react-native";
import { theme } from "../lib/theme";
import { listEntity, upsertEntity } from "../db/sqlite";
import { enqueueEvent } from "../db/eventQueue";

function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export default function ClientsScreen() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", region: "", culture: "soja", classification: "B", potential: "medio", area_ha: 0 });

  const load = useCallback(async () => {
    const where = q ? `deleted_at IS NULL AND name LIKE ?` : `deleted_at IS NULL`;
    const params = q ? [`%${q}%`] : [];
    setItems(await listEntity("clients", where, params));
  }, [q]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    setBusy(true);
    try {
      const now = new Date().toISOString();
      const row = {
        id: uuid(),
        seq_id: 0, // server will assign
        tenant_id: "tenant-default",
        type: "producer",
        name: form.name,
        doc: null,
        region: form.region,
        culture: form.culture.split(",").map((s) => s.trim()).filter(Boolean),
        classification: form.classification,
        potential: form.potential,
        area_ha: Number(form.area_ha) || 0,
        contacts: [],
        notes: null,
        created_at: now,
        updated_at: now,
        deleted_at: null,
        _dirty: 1,
      };
      await upsertEntity("clients", row);
      await enqueueEvent("clients", "upsert", row);
      setOpen(false);
      setForm({ name: "", region: "", culture: "soja", classification: "B", potential: "medio", area_ha: 0 });
      load();
    } finally { setBusy(false); }
  };

  return (
    <View style={s.root}>
      <View style={s.searchRow}>
        <TextInput style={s.input} placeholder="Buscar cliente..." placeholderTextColor={theme.muted}
                   value={q} onChangeText={setQ} />
        <TouchableOpacity style={s.add} onPress={() => setOpen(true)}>
          <Text style={s.addText}>+ NOVO</Text>
        </TouchableOpacity>
      </View>
      <FlatList
        data={items}
        keyExtractor={(it) => it.id}
        contentContainerStyle={{ padding: 12 }}
        renderItem={({ item }) => (
          <View style={s.row}>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <Text style={s.seq}>#{item.seq_id || "—"}</Text>
                <Text style={s.name}>{item.name}</Text>
                {item._dirty ? <View style={s.dirtyBadge}><Text style={s.dirtyTxt}>SYNC</Text></View> : null}
              </View>
              <Text style={s.meta}>{item.region || "—"} · {(item.culture || []).join(", ") || "—"}</Text>
            </View>
            <Text style={[s.tier, { color: item.classification === "A" ? theme.primary : item.classification === "B" ? theme.yellow : theme.muted }]}>
              {item.classification || "—"}
            </Text>
          </View>
        )}
        ListEmptyComponent={<Text style={s.empty}>Nenhum cliente local. Sincronize ou crie um novo.</Text>}
      />

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <View style={s.modalRoot}>
          <View style={s.modal}>
            <Text style={s.modalTitle}>Novo cliente (offline)</Text>
            <Text style={s.label}>Nome</Text>
            <TextInput style={s.input} value={form.name} onChangeText={(v) => setForm({ ...form, name: v })} placeholderTextColor={theme.muted} />
            <Text style={s.label}>Região</Text>
            <TextInput style={s.input} value={form.region} onChangeText={(v) => setForm({ ...form, region: v })} placeholderTextColor={theme.muted} />
            <Text style={s.label}>Culturas (vírgula)</Text>
            <TextInput style={s.input} value={form.culture} onChangeText={(v) => setForm({ ...form, culture: v })} placeholderTextColor={theme.muted} />
            <Text style={s.label}>Área (ha)</Text>
            <TextInput style={s.input} value={String(form.area_ha)} onChangeText={(v) => setForm({ ...form, area_ha: v })} keyboardType="numeric" placeholderTextColor={theme.muted} />
            <View style={{ flexDirection: "row", marginTop: 18 }}>
              <TouchableOpacity style={[s.btn, { flex: 1, marginRight: 8, backgroundColor: theme.surface2, borderColor: theme.border, borderWidth: 1 }]} onPress={() => setOpen(false)}>
                <Text style={[s.btnText, { color: theme.muted }]}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.btn, { flex: 1, backgroundColor: theme.primary }]} onPress={create} disabled={busy || !form.name}>
                {busy ? <ActivityIndicator color={theme.bg} /> : <Text style={[s.btnText, { color: theme.bg }]}>Salvar offline</Text>}
              </TouchableOpacity>
            </View>
            <Text style={s.hint}>Será enviado ao servidor na próxima sincronização.</Text>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg },
  searchRow: { flexDirection: "row", padding: 12, gap: 8 },
  input: { flex: 1, color: theme.text, borderColor: theme.border, borderWidth: 1, borderRadius: 8, padding: 12, fontSize: 14 },
  add: { backgroundColor: theme.primary, paddingHorizontal: 14, borderRadius: 8, justifyContent: "center" },
  addText: { color: theme.bg, fontWeight: "700", fontSize: 12, letterSpacing: 1 },
  row: { flexDirection: "row", alignItems: "center", padding: 14, borderBottomColor: theme.border, borderBottomWidth: 1 },
  seq: { color: theme.muted, fontSize: 12, marginRight: 8 },
  name: { color: theme.text, fontSize: 15, fontWeight: "600" },
  meta: { color: theme.muted, fontSize: 12, marginTop: 4 },
  tier: { fontSize: 18, fontWeight: "800" },
  empty: { color: theme.muted, textAlign: "center", marginTop: 60, paddingHorizontal: 24 },
  dirtyBadge: { backgroundColor: theme.yellow, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, marginLeft: 8 },
  dirtyTxt: { color: theme.bg, fontSize: 9, fontWeight: "700", letterSpacing: 1 },
  modalRoot: { flex: 1, backgroundColor: "rgba(0,0,0,0.7)", justifyContent: "flex-end" },
  modal: { backgroundColor: theme.surface, padding: 20, borderTopLeftRadius: 20, borderTopRightRadius: 20 },
  modalTitle: { color: theme.text, fontSize: 20, fontWeight: "700", marginBottom: 14 },
  label: { color: theme.muted, fontSize: 11, letterSpacing: 2, marginTop: 10, marginBottom: 4 },
  btn: { padding: 12, borderRadius: 8, alignItems: "center" },
  btnText: { fontWeight: "700", fontSize: 14 },
  hint: { color: theme.muted, textAlign: "center", marginTop: 12, fontSize: 11 },
});
