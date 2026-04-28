import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator } from "react-native";
import { useAuth } from "../context/AuthContext";
import { theme } from "../lib/theme";

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("admin@agrocrm.com");
  const [password, setPassword] = useState("Admin@123");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setErr(""); setBusy(true);
    try { await signIn(email, password); }
    catch (e) { setErr(e?.response?.data?.detail || "Falha no login"); }
    finally { setBusy(false); }
  };

  return (
    <View style={s.root}>
      <View style={s.brand}>
        <Text style={s.logo}>Agro<Text style={{ color: theme.primary }}>CRM</Text></Text>
        <Text style={s.tag}>Trading Terminal · Mobile</Text>
      </View>
      <View style={s.card}>
        <Text style={s.label}>EMAIL</Text>
        <TextInput style={s.input} value={email} onChangeText={setEmail}
                   autoCapitalize="none" keyboardType="email-address" placeholderTextColor={theme.muted} />
        <Text style={s.label}>SENHA</Text>
        <TextInput style={s.input} value={password} onChangeText={setPassword} secureTextEntry placeholderTextColor={theme.muted} />
        {err ? <Text style={s.err}>{err}</Text> : null}
        <TouchableOpacity style={s.btn} onPress={submit} disabled={busy}>
          {busy ? <ActivityIndicator color={theme.bg} /> : <Text style={s.btnText}>Entrar</Text>}
        </TouchableOpacity>
        <Text style={s.hint}>admin@agrocrm.com · Admin@123</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg, padding: 24, justifyContent: "center" },
  brand: { alignItems: "center", marginBottom: 32 },
  logo: { color: theme.text, fontSize: 36, fontWeight: "800", letterSpacing: -0.5 },
  tag: { color: theme.muted, marginTop: 6, letterSpacing: 2, fontSize: 11 },
  card: { backgroundColor: theme.surface, borderColor: theme.border, borderWidth: 1, borderRadius: 16, padding: 20 },
  label: { color: theme.muted, fontSize: 11, letterSpacing: 2, marginBottom: 6, marginTop: 10 },
  input: { color: theme.text, borderColor: theme.border, borderWidth: 1, borderRadius: 8, padding: 12, fontFamily: theme.font.mono },
  err: { color: theme.red, marginTop: 10 },
  btn: { backgroundColor: theme.primary, padding: 14, borderRadius: 10, marginTop: 18, alignItems: "center" },
  btnText: { color: theme.bg, fontWeight: "700", fontSize: 15 },
  hint: { color: theme.muted, fontSize: 11, textAlign: "center", marginTop: 16, fontFamily: theme.font.mono },
});
