/**
 * Auto-sync hook — pulls/pushes on connectivity changes and on a timer.
 */
import { useEffect, useState, useCallback } from "react";
import NetInfo from "@react-native-community/netinfo";
import { syncAll } from "./syncEngine";
import { queueSize } from "../db/eventQueue";

export function useAutoSync(intervalMs = 60000) {
  const [online, setOnline] = useState(true);
  const [last, setLast] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setPending(await queueSize());
  }, []);

  const run = useCallback(async () => {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const r = await syncAll();
      setLast({ ...r, at: new Date().toISOString() });
    } catch (e) {
      setError(e?.message || "sync error");
    } finally { setBusy(false); refresh(); }
  }, [busy, refresh]);

  useEffect(() => {
    refresh();
    const unsub = NetInfo.addEventListener((s) => {
      const isOnline = !!s.isConnected;
      setOnline(isOnline);
      if (isOnline) run();
    });
    const t = setInterval(() => { if (online) run(); }, intervalMs);
    return () => { unsub(); clearInterval(t); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { online, last, busy, pending, error, syncNow: run };
}
