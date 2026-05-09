import { useEffect, useRef } from "react";
import { buildProgressWsUrl } from "../api/client";
import type { ProgressMessage } from "../api/types";

/**
 * 订阅后端进度 WebSocket。
 * - 自动重连（指数退避，最多 5 次）
 * - 自动心跳（每 25s ping）
 */
export function useProgressSocket(onMessage: (msg: ProgressMessage) => void, jobId?: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    let retries = 0;
    let cancelled = false;
    let pingTimer: number | null = null;

    function connect() {
      if (cancelled) return;
      const url = buildProgressWsUrl(jobId);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        retries = 0;
        if (pingTimer) window.clearInterval(pingTimer);
        pingTimer = window.setInterval(() => {
          try {
            ws.send(JSON.stringify({ type: "ping" }));
          } catch {
            /* ignore */
          }
        }, 25_000);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data && data.type !== "pong") {
            handlerRef.current(data as ProgressMessage);
          }
        } catch {
          /* ignore */
        }
      };

      ws.onclose = () => {
        if (pingTimer) window.clearInterval(pingTimer);
        if (cancelled) return;
        retries += 1;
        if (retries <= 5) {
          const delay = Math.min(1000 * 2 ** retries, 15_000);
          window.setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        // 关闭即可触发重连
        ws.close();
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (pingTimer) window.clearInterval(pingTimer);
      try {
        wsRef.current?.close();
      } catch {
        /* ignore */
      }
    };
  }, [jobId]);
}
