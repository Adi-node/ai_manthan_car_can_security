import { useCallback, useEffect, useRef, useState } from 'react';
import IdsToggle from './components/IdsToggle.jsx';
import Vehicle2DVisualizer from './components/Vehicle2DVisualizer.jsx';
import ActionLog from './components/ActionLog.jsx';
import useDashboardSocket from './hooks/useDashboardSocket.js';

const MAX_LOGS = 100;

const INITIAL = {
  v2x: { vehicle_speed_kph: 60 },
  prediction: { is_attack: false, latency_ms: 0 },
};

function timestamp() {
  const d = new Date();
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}

export default function App() {
  const [isIdsEnabled, setIsIdsEnabled] = useState(false);
  const [latest, setLatest] = useState(INITIAL);
  const [logs, setLogs] = useState([]);
  const nextId = useRef(0);

  const pushLog = useCallback((level, message) => {
    setLogs((prev) =>
      [...prev, { id: nextId.current++, time: timestamp(), level, message }].slice(-MAX_LOGS)
    );
  }, []);

  const socketStatus = useDashboardSocket(setLatest);
  const conn = {
    open: { text: 'LIVE', cls: 'text-emerald-300 border-emerald-500/40' },
    connecting: { text: 'CONNECTING', cls: 'text-amber-300 border-amber-500/40' },
    closed: { text: 'RECONNECTING', cls: 'text-amber-300 border-amber-500/40' },
  }[socketStatus];

  const isAttack = latest.prediction.is_attack;
  const latencyMs = latest.prediction.latency_ms;
  const latencyRef = useRef(latencyMs);
  latencyRef.current = latencyMs;

  // Log once per attack burst when simulated mitigation is on.
  useEffect(() => {
    if (isIdsEnabled && isAttack) {
      pushLog(
        'prevented',
        `SIMULATED MITIGATION. Backend flagged an attack in ${latencyRef.current.toFixed(1)}ms.`
      );
    }
  }, [isIdsEnabled, isAttack, pushLog]);

  // Context lines for the demo.
  const prevIds = useRef(null);
  useEffect(() => {
    if (prevIds.current === isIdsEnabled) return; // StrictMode re-run / no change
    if (prevIds.current === null) {
      pushLog('info', 'Dashboard connected. Mitigation simulation is OFF; backend detection remains active.');
    } else {
      pushLog('info', `Mitigation simulation ${isIdsEnabled ? 'ON' : 'OFF'}. Backend detection remains active.`);
    }
    prevIds.current = isIdsEnabled;
  }, [isIdsEnabled, pushLog]);

  const prevAttack = useRef(false);
  useEffect(() => {
    if (isAttack && !prevAttack.current && !isIdsEnabled) {
      pushLog('warn', 'Backend flagged an attack; mitigation simulation is OFF.');
    }
    prevAttack.current = isAttack;
  }, [isAttack, isIdsEnabled, pushLog]);

  const status = isAttack
    ? isIdsEnabled
      ? { text: 'SIMULATED MITIGATION', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40' }
      : { text: 'UNDER ATTACK', cls: 'bg-red-500/15 text-red-300 border-red-500/40' }
    : { text: 'NOMINAL', cls: 'bg-slate-700/40 text-slate-300 border-slate-600' };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 px-6 py-4">
        <div>
          <h1 className="text-xl font-bold tracking-wide">Vehicle Cyber-Security Dashboard</h1>
          <p className="text-xs text-slate-400">Live backend AI detection and V2X telemetry</p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <span className={`rounded-full border px-3 py-1 text-xs font-bold tracking-widest ${conn.cls}`}>
            {conn.text}
          </span>
          <span className={`rounded-full border px-3 py-1 text-xs font-bold tracking-widest ${status.cls}`}>
            {status.text}
          </span>
          <IdsToggle isIdsEnabled={isIdsEnabled} onChange={setIsIdsEnabled} />
        </div>
      </header>

      <main className="grid gap-6 p-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section className="space-y-4">
          <Vehicle2DVisualizer latest={latest} isIdsEnabled={isIdsEnabled} />
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="Reported speed" value={`${Math.round(latest.v2x.vehicle_speed_kph)} km/h`} danger={isAttack} />
            <Stat label="Attack flag" value={isAttack ? 'TRUE' : 'false'} danger={isAttack} />
            <Stat label="AI latency" value={isAttack ? `${latencyMs.toFixed(1)} ms` : '--'} />
          </div>
        </section>

        <section className="flex flex-col">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-widest text-slate-400">Action Log</h2>
          <div className="flex-1">
            <ActionLog logs={logs} />
          </div>
        </section>
      </main>
    </div>
  );
}

function Stat({ label, value, danger }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2">
      <div className="text-[10px] uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`font-mono text-lg font-bold ${danger ? 'text-red-400' : 'text-slate-100'}`}>{value}</div>
    </div>
  );
}
