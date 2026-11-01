const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

const INSANE_SCROLL_S = 0.1;

function Wheel({ cx, spinStyle }) {
  return (
    <g>
      <circle cx={cx} cy={128} r={22} fill="#0f172a" stroke="#475569" strokeWidth={3} />
      <g className="wheel-spin" style={spinStyle}>
        <circle cx={cx} cy={128} r={12} fill="#94a3b8" />
        {[0, 60, 120].map((deg) => (
          <rect
            key={deg}
            x={cx - 1.5}
            y={128 - 12}
            width={3}
            height={24}
            fill="#334155"
            transform={`rotate(${deg} ${cx} 128)`}
          />
        ))}
      </g>
    </g>
  );
}

export default function Vehicle2DVisualizer({ latest, isIdsEnabled }) {
  const isAttack = latest.prediction.is_attack;
  const reportedSpeed = latest.v2x.vehicle_speed_kph;

  const isBlocked = isIdsEnabled && isAttack;
  const isCompromised = !isIdsEnabled && isAttack;

  const speed = isBlocked ? 0 : reportedSpeed;
  const scrollSeconds = isCompromised
    ? INSANE_SCROLL_S
    : speed > 0
      ? clamp(200 / speed, 0.2, 8)
      : 0;
  const moving = scrollSeconds > 0;
  const motionStyle = moving ? { animationDuration: `${scrollSeconds}s` } : { animationPlayState: 'paused' };
  const wheelStyle = moving
    ? { animationDuration: `${Math.max(scrollSeconds / 3, 0.05)}s` }
    : { animationPlayState: 'paused' };

  const borderColor = isCompromised
    ? 'border-red-500 shadow-[0_0_30px_rgba(239,68,68,0.5)]'
    : isBlocked
      ? 'border-emerald-400 shadow-[0_0_30px_rgba(52,211,153,0.4)]'
      : 'border-slate-700';

  return (
    <div className={`relative overflow-hidden rounded-xl border-2 bg-gradient-to-b from-sky-950 via-slate-900 to-slate-900 ${borderColor}`}>
      {/* Status banner */}
      <div className="absolute inset-x-0 top-3 z-10 flex justify-center">
        {isCompromised && (
          <div className="warn-flash rounded-lg border-2 border-red-400 bg-red-600/90 px-5 py-2 text-lg font-black tracking-widest text-white">
            VEHICLE COMPROMISED
          </div>
        )}
        {isBlocked && (
          <div className="rounded-lg border-2 border-emerald-300 bg-emerald-600/90 px-5 py-2 text-lg font-black tracking-widest text-white">
            SIMULATED MITIGATION
          </div>
        )}
      </div>

      {/* Speedometer */}
      <div className="absolute left-4 top-3 z-10 font-mono">
        <div className={`text-3xl font-bold ${isCompromised ? 'text-red-400' : 'text-slate-100'}`}>
          {Math.round(speed)}
          <span className="ml-1 text-sm text-slate-400">km/h</span>
        </div>
        {isBlocked && <div className="text-[10px] text-emerald-300">simulated stop · reported {Math.round(reportedSpeed)} km/h</div>}
      </div>

      {/* Scene */}
      <div className="relative mx-auto h-56 w-full max-w-3xl">
        {/* Car */}
        <div className={`absolute inset-x-0 bottom-[52px] flex justify-center ${isCompromised ? 'car-shake' : ''}`}>
          <svg viewBox="0 0 400 160" className="h-44 w-auto overflow-visible" role="img" aria-label="Vehicle">
            <defs>
              <filter id="shield-glow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="6" />
              </filter>
            </defs>

            {isBlocked && (
              <g className="shield-pulse">
                <ellipse cx={200} cy={92} rx={205} ry={82} fill="rgba(52,211,153,0.12)" stroke="#34d399" strokeWidth={3} filter="url(#shield-glow)" />
                <ellipse cx={200} cy={92} rx={205} ry={82} fill="none" stroke="#6ee7b7" strokeWidth={2} />
              </g>
            )}

            {/* Body */}
            <path
              d="M30 118 L30 96 Q30 86 44 82 L100 74 L135 40 Q140 34 150 34 L250 34 Q262 34 270 42 L305 76 L358 84 Q374 88 374 102 L374 118 Z"
              fill={isCompromised ? '#b91c1c' : '#2563eb'}
              stroke="#0f172a"
              strokeWidth={3}
            />
            {/* Windows */}
            <path d="M148 46 L246 46 L284 76 L112 76 Z" fill="#bae6fd" stroke="#0f172a" strokeWidth={3} opacity={0.9} />
            <line x1={196} y1={46} x2={196} y2={76} stroke="#0f172a" strokeWidth={3} />
            {/* Door line + handle */}
            <line x1={196} y1={78} x2={196} y2={116} stroke="#0f172a" strokeWidth={2} opacity={0.5} />
            <rect x={172} y={88} width={14} height={4} rx={2} fill="#0f172a" opacity={0.6} />

            {/* Head / tail lights */}
            <rect x={358} y={92} width={16} height={9} rx={3} fill="#fef08a" />
            <rect x={30} y={92} width={10} height={9} rx={3} fill="#ef4444" />

            {/* Hazard lights */}
            {isBlocked && (
              <g className="hazard-flash">
                <circle cx={368} cy={90} r={9} fill="#f59e0b" />
                <circle cx={36} cy={90} r={9} fill="#f59e0b" />
                <circle cx={368} cy={90} r={22} fill="#f59e0b" opacity={0.35} />
                <circle cx={36} cy={90} r={22} fill="#f59e0b" opacity={0.35} />
              </g>
            )}

            <Wheel cx={100} spinStyle={wheelStyle} />
            <Wheel cx={304} spinStyle={wheelStyle} />
          </svg>
        </div>

        {/* Road */}
        <div className="absolute inset-x-0 bottom-0 h-[52px] bg-slate-700">
          <div className="absolute inset-x-0 top-0 h-1 bg-slate-500" />
          <div className="road-dashes absolute inset-x-0 top-[26px] h-[6px]" style={motionStyle} />
        </div>
      </div>
    </div>
  );
}
