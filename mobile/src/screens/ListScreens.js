import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, StyleSheet } from "react-native";
import { theme } from "../lib/theme";
import { listEntity } from "../db/sqlite";

function fmtBRL(v) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);
}

export function makeListScreen({ entity, title, renderRight, renderMeta }) {
  return function Screen() {
    const [items, setItems] = useState([]);
    const load = useCallback(async () => setItems(await listEntity(entity)), []);
    useEffect(() => { load(); }, [load]);
    return (
      <FlatList
        style={{ backgroundColor: theme.bg }}
        data={items}
        keyExtractor={(it) => it.id}
        contentContainerStyle={{ padding: 12 }}
        renderItem={({ item }) => (
          <View style={s.row}>
            <View style={{ flex: 1 }}>
              <Text style={s.title}>#{item.seq_id || "—"} · {renderMeta?.(item)?.title || item.title || item.name || item.client_name || "—"}</Text>
              <Text style={s.meta}>{renderMeta?.(item)?.sub || ""}</Text>
            </View>
            <Text style={s.right}>{renderRight ? renderRight(item) : ""}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={s.empty}>Sem registros locais. Puxe para sincronizar.</Text>}
      />
    );
  };
}

const s = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", padding: 14, borderBottomColor: theme.border, borderBottomWidth: 1 },
  title: { color: theme.text, fontSize: 14, fontWeight: "600" },
  meta: { color: theme.muted, fontSize: 12, marginTop: 4 },
  right: { color: theme.yellow, fontSize: 13, fontWeight: "700" },
  empty: { color: theme.muted, textAlign: "center", marginTop: 60, paddingHorizontal: 24 },
});

export const OpportunitiesScreen = makeListScreen({
  entity: "opportunities",
  renderMeta: (i) => ({ title: i.title, sub: `${i.client_name || ""} · ${i.stage_name || ""} · ${i.probability || 0}%` }),
  renderRight: (i) => fmtBRL(i.value),
});

export const ContractsScreen = makeListScreen({
  entity: "contracts",
  renderMeta: (i) => ({ title: `${i.type?.toUpperCase()} · ${i.client_name}`, sub: `${i.product_name || ""} · ${i.volume || 0} ${i.unit || "ton"} · ${i.status}` }),
  renderRight: (i) => i.type === "barter" ? "BARTER" : fmtBRL((i.volume || 0) * (i.price || 0)),
});

export const OrdersScreen = makeListScreen({
  entity: "orders",
  renderMeta: (i) => ({ title: `${i.type?.toUpperCase()} · ${i.client_name}`, sub: `${i.status} · LOG: ${i.logistic_status}` }),
  renderRight: (i) => fmtBRL(i.total),
});
