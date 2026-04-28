import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

const BASE = Constants.expoConfig?.extra?.BACKEND_URL || "http://localhost:8001";
export const API_BASE = `${BASE}/api`;

export const api = axios.create({ baseURL: API_BASE, timeout: 20000 });

api.interceptors.request.use(async (config) => {
  const t = await AsyncStorage.getItem("auth_token");
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export async function login(email, password) {
  const { data } = await api.post("/auth/login", { email, password });
  await AsyncStorage.setItem("auth_token", data.access_token);
  await AsyncStorage.setItem("auth_refresh", data.refresh_token);
  await AsyncStorage.setItem("auth_user", JSON.stringify(data.user));
  return data;
}

export async function logout() {
  await AsyncStorage.multiRemove(["auth_token", "auth_refresh", "auth_user"]);
}

export async function currentUser() {
  const u = await AsyncStorage.getItem("auth_user");
  return u ? JSON.parse(u) : null;
}
