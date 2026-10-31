export default function IdsToggle({ isIdsEnabled, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isIdsEnabled}
      onClick={() => onChange(!isIdsEnabled)}
      className={`flex items-center gap-4 rounded-2xl border-2 px-5 py-3 transition-colors ${
        isIdsEnabled
          ? 'border-emerald-400 bg-emerald-500/10 shadow-[0_0_24px_rgba(52,211,153,0.35)]'
          : 'border-slate-600 bg-slate-800/60'
      }`}
    >
      <span
        className={`relative inline-block h-9 w-16 rounded-full transition-colors ${
          isIdsEnabled ? 'bg-emerald-500' : 'bg-slate-600'
        }`}
      >
        <span
          className={`absolute top-1 h-7 w-7 rounded-full bg-white shadow transition-all ${
            isIdsEnabled ? 'left-8' : 'left-1'
          }`}
        />
      </span>
      <span className="text-left leading-tight">
        <span className="block text-sm font-bold uppercase tracking-wider text-slate-100">
          AI Intrusion Detection System
        </span>
        <span className={`block text-xs font-semibold ${isIdsEnabled ? 'text-emerald-300' : 'text-slate-400'}`}>
          {isIdsEnabled ? 'ACTIVE - protecting vehicle' : 'OFFLINE - vehicle exposed'}
        </span>
      </span>
    </button>
  );
}
