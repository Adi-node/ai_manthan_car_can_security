import { useEffect, useRef, useState } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/dashboard';
const MIN_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 10000;

// Maps a backend `dashboard_frame` onto the shape the UI components read.
// `is_attack` uses the debounced fail-safe (k consecutive windows + hold),
// so the UI does not flicker on single-window predictions.
function adaptFrame(frame) {
  const latest = frame.latest;
  if (!latest) return null;
  return {
    v2x: { vehicle_speed_kph: latest.v2x?.vehicle_speed_kph ?? 0 },
    prediction: {
      is_attack: Boolean(frame.failsafe?.triggered),
      latency_ms: latest.latency?.inference_ms ?? 0,
      attack_probability: latest.prediction?.attack_probability ?? 0,
    },
    failsafe_reason: frame.failsafe?.reason ?? null,
    stats: frame.stats ?? null,
  };
}

/**
 * Live feed from the backend `WS /ws/dashboard`. Reconnects with exponential
 * backoff. `onMessage` receives the adapted payload; returns the socket status
 * ('connecting' | 'open' | 'closed').
 */
export default function useDashboardSocket(onMessage) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;
  const [status, setStatus] = useState('connecting');

  useEffect(() => {
    let ws = null;
    let timer = null;
    let backoff = MIN_BACKOFF_MS;
    let disposed = false;

    const connect = () => {
      setStatus('connecting');
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        backoff = MIN_BACKOFF_MS;
        setStatus('open');
      };

      ws.onmessage = (event) => {
        let frame;
        try {
          frame = JSON.parse(event.data);
        } catch {
          return;
        }
        if (frame.type !== 'dashboard_frame') return;
        const payload = adaptFrame(frame);
        if (payload) handlerRef.current(payload);
      };

      ws.onclose = () => {
        if (disposed) return;
        setStatus('closed');
        timer = setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
      };

      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      disposed = true;
      clearTimeout(timer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, []);

  return status;
}
