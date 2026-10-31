import { useEffect, useRef } from 'react';

const LEVEL_STYLES = {
  prevented: 'text-emerald-300',
  info: 'text-slate-400',
  warn: 'text-amber-300',
};

export default function ActionLog({ logs }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [logs]);

  return (
    <div className="flex h-full min-h-[320px] flex-col overflow-hidden rounded-xl border border-slate-700 bg-black">
      <div className="flex items-center gap-2 border-b border-slate-700 bg-slate-900 px-3 py-2">
        <span className="h-3 w-3 rounded-full bg-red-500" />
        <span className="h-3 w-3 rounded-full bg-amber-400" />
        <span className="h-3 w-3 rounded-full bg-emerald-500" />
        <span className="ml-2 font-mono text-xs text-slate-400">action-log -- security time log</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 font-mono text-xs leading-relaxed">
        {logs.length === 0 && <div className="text-slate-600">Awaiting events...</div>}
        {logs.map((entry) => (
          <div key={entry.id} className={LEVEL_STYLES[entry.level] ?? LEVEL_STYLES.info}>
            [{entry.time}] {entry.message}
          </div>
        ))}
        <div className="text-emerald-400">
          $ <span className="animate-pulse">_</span>
        </div>
        <div ref={endRef} />
      </div>
    </div>
  );
}
