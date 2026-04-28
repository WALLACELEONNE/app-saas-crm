import React, { useEffect, useState } from "react";
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator } from "react-native";
import { theme } from "../lib/theme";
import { useAutoSync } from "../sync/useAutoSync";
import { useAuth } from "../context/AuthContext";
import { listEntity } from "../db/sqlite";

export default function HomeScreen({ navigation }) {
  const { user, signOut } = useAuth();
  const { online, last, busy, pending, error, syncNow } = useAutoSync(60000);
  const [counts, setCounts] = useState({ clients: 0, contracts: 0, orders: 0, opportunities: 0 });

  const loadCounts = async () => {
    const [c, ct, o, op] = await Promise.all([
      listEntity("clients"), listEntity("contracts"), listEntity("orders"), listEntity("opportunities"),
    ]);
    setCounts({ clients: c.length, contracts: ct.length, orders: o.length, opportunities: op.length });
  };

  useEffect(() => { loadCounts(); }, [last]);

  return (
    <ScrollView style={s.root} contentContainerStyle={{ padding: 16 }}
                refreshControl={<RefreshControl refreshing={busy} onRefresh={syncNow} tintColor={theme.primary} />}>
      <View style={s.header}>
        <View>
          <Text style={s.greeting}>Olá,</Text>
          <Text style={s.name}>{user?.name || "—"}</Text>
        </View>
        <TouchableOpacity onPress={signOut}><Text style={s.signOut}>SAIR</Text></TouchableOpacity>
      </View>

      {/* Sync status card */}
      <View style={[s.card, { borderColor: online ? theme.primary : theme.red }]}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <View>
            <Text style={s.overline}>Status</Text>
            <Text style={[s.statusText, { color: online ? theme.primary : theme.red }]}>
              {online ? "● Online" : "○ Offline"}
            </Text>
          </View>
          <TouchableOpacity onPress={syncNow} style={s.syncBtn} disabled={busy}>
            {busy ? <ActivityIndicator color={theme.bg} /> : <Text style={s.syncBtnText}>SINCRONIZAR</Text>}
          </TouchableOpacity>
        </View>
        <View style={{ flexDirection: "row", marginTop: 14 }}>
          <Stat label="Pendentes" value={pending} color={pending > 0 ? theme.yellow : theme.muted} />
          <Stat label="Última sync" value={last?.at ? new Date(last.at).toLocaleTimeString("pt-BR") : "—"} />
          <Stat label="Recebidos" value={last?.pulled ?? 0} />
          <Stat label="Enviados" value={last?.pushed ?? 0} />
        </View>
        {error ? <Text style={[s.err, { marginTop: 8 }]}>{error}</Text> : null}
      </View>

      <Text style={s.section}>OPERAÇÃO</Text>
      <View style={s.grid}>
        <Tile label="Clientes" count={counts.clients} onPress={() => navigation.navigate("Clients")} accent={theme.primary} />
        <Tile label="Oportunidades" count={counts.opportunities} onPress={() => navigation.navigate("Opportunities")} accent={theme.yellow} />
        <Tile label="Contratos" count={counts.contracts} onPress={() => navigation.navigate("Contracts")} accent={theme.orange} />
        <Tile label="Pedidos" count={counts.orders} onPress={() => navigation.navigate("Orders")} accent={theme.primary} />
      </View>

      <Text style={s.footer}>Offline-first · LWW · device sync via /api/sync</Text>
    </ScrollView>
  );
}

const Stat = ({ label, value, color }) => (
  <View style={{ flex: 1 }}>
    <Text style={s.overline}>{label}</Text>
    <Text style={{ color: color || theme.text, fontSize: 14, fontWeight: "600", marginTop: 2 }}>{String(value)}</Text>
  </View>
);

const Tile = ({ label, count, onPress, accent }) => (
  <TouchableOpacity style={s.tile} onPress={onPress}>
    <Text style={[s.overline, { color: accent }]}>{label.toUpperCase()}</Text>
    <Text style={s.tileCount}>{count}</Text>
  </TouchableOpacity>
);

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", marginTop: 8, marginBottom: 18 },
  greeting: { color: theme.muted, fontSize: 13 },
  name: { color: theme.text, fontSize: 26, fontWeight: "700" },
  signOut: { color: theme.muted, letterSpacing: 2, fontSize: 11 },
  card: { backgroundColor: theme.surface, borderColor: theme.border, borderWidth: 1, borderRadius: 14, padding: 16 },
  overline: { color: theme.muted, fontSize: 10, letterSpacing: 2, fontWeight: "600" },
  statusText: { fontSize: 18, fontWeight: "700", marginTop: 4 },
  syncBtn: { backgroundColor: theme.primary, paddingVertical: 10, paddingHorizontal: 14, borderRadius: 8 },
  syncBtnText: { color: theme.bg, fontWeight: "700", fontSize: 12, letterSpacing: 1 },
  err: { color: theme.red, fontSize: 12 },
  section: { color: theme.muted, letterSpacing: 2, marginTop: 22, marginBottom: 10, fontSize: 11 },
  grid: { flexDirection: "row", flexWrap: "wrap", marginHorizontal: -6 },
  tile: {
    width: "50%", padding: 6,
  },
  tileCount: { color: theme.text, fontSize: 32, fontWeight: "800", marginTop: 8 },
  footer: { color: theme.muted, fontSize: 10, letterSpacing: 1.5, marginTop: 30, textAlign: "center" },
});

s.tile = {
  ...s.tile,
};
