import { useId } from 'react';
import { motion } from 'motion/react';

export interface AnimatedBeamProps {
  isLive?: boolean;
  isReverse?: boolean;
  className?: string;
}

export function AnimatedBeam({
  isLive = false,
  isReverse = false,
  className = '',
}: AnimatedBeamProps) {
  const id = useId();
  const gradientId = `beam-grad-${id}`;

  const isActive = isLive || isReverse;
  const strokeColor = isReverse ? '#e11d48' : '#16a34a';
  const glowColor = isReverse ? 'rgba(225, 29, 72, 0.28)' : 'rgba(22, 163, 74, 0.28)';

  return (
    <div
      className={`animated-beam-container ${className}`}
      aria-hidden="true"
      style={{
        position: 'relative',
        flex: '0 0 54px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '44px',
        margin: '0 2px',
      }}
    >
      <svg
        width="54"
        height="44"
        viewBox="0 0 54 44"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ width: '100%', height: '100%', overflow: 'visible' }}
      >
        <defs>
          <linearGradient
            id={gradientId}
            gradientUnits="userSpaceOnUse"
            x1={isReverse ? '52' : '2'}
            y1="22"
            x2={isReverse ? '2' : '52'}
            y2="22"
          >
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.2" />
            <stop offset="50%" stopColor={strokeColor} stopOpacity="1" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0.2" />
          </linearGradient>
        </defs>

        {/* Base dashed track */}
        <line
          x1="2"
          y1="22"
          x2="52"
          y2="22"
          stroke="#d8e3db"
          strokeWidth="1.5"
          strokeDasharray="3 4"
          strokeLinecap="round"
        />

        {/* Active glowing connector line */}
        {isActive && (
          <motion.line
            x1="2"
            y1="22"
            x2="52"
            y2="22"
            stroke={`url(#${gradientId})`}
            strokeWidth="2"
            strokeLinecap="round"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
        )}

        {/* Traveling light pulse dot */}
        {isActive && (
          <motion.circle
            r="3.5"
            cy="22"
            fill={strokeColor}
            initial={{
              cx: isReverse ? 50 : 4,
              opacity: 0,
            }}
            animate={{
              cx: isReverse ? [50, 4] : [4, 50],
              opacity: [0, 1, 1, 0],
            }}
            transition={{
              duration: isReverse ? 0.95 : 1.15,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
            style={{
              filter: `drop-shadow(0 0 4px ${glowColor})`,
            }}
          />
        )}
      </svg>
    </div>
  );
}
