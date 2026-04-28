import "react-native-gesture-handler";
import React from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { ActivityIndicator, View } from "react-native";

import { AuthProvider, useAuth } from "./src/context/AuthContext";
import LoginScreen from "./src/screens/LoginScreen";
import HomeScreen from "./src/screens/HomeScreen";
import ClientsScreen from "./src/screens/ClientsScreen";
import { OpportunitiesScreen, ContractsScreen, OrdersScreen } from "./src/screens/ListScreens";
import { theme } from "./src/lib/theme";

const navTheme = {
  ...DefaultTheme,
  dark: true,
  colors: {
    ...DefaultTheme.colors,
    background: theme.bg,
    card: theme.surface2,
    text: theme.text,
    border: theme.border,
    primary: theme.primary,
    notification: theme.primary,
  },
};

const Stack = createNativeStackNavigator();

function Routes() {
  const { user, loading } = useAuth();
  if (loading) return <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}><ActivityIndicator color={theme.primary} /></View>;
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: theme.surface2 },
        headerTitleStyle: { color: theme.text, fontWeight: "700" },
        headerTintColor: theme.primary,
        contentStyle: { backgroundColor: theme.bg },
      }}>
      {user ? (
        <>
          <Stack.Screen name="Home" component={HomeScreen} options={{ title: "AgroCRM" }} />
          <Stack.Screen name="Clients" component={ClientsScreen} options={{ title: "Clientes" }} />
          <Stack.Screen name="Opportunities" component={OpportunitiesScreen} options={{ title: "Oportunidades" }} />
          <Stack.Screen name="Contracts" component={ContractsScreen} options={{ title: "Contratos" }} />
          <Stack.Screen name="Orders" component={OrdersScreen} options={{ title: "Pedidos" }} />
        </>
      ) : (
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
      )}
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <NavigationContainer theme={navTheme}>
        <StatusBar style="light" />
        <Routes />
      </NavigationContainer>
    </AuthProvider>
  );
}
