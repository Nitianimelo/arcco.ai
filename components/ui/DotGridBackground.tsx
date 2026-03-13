import React from 'react';

const DotGridBackground: React.FC = () => (
  <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
    {/* Square grid — Vercel style */}
    <div
      className="absolute inset-0"
      style={{
        backgroundImage: `
          linear-gradient(to right, var(--dot-color, rgba(255,255,255,0.07)) 1px, transparent 1px),
          linear-gradient(to bottom, var(--dot-color, rgba(255,255,255,0.07)) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }}
    />
    {/* Primary glow — bottom-left */}
    <div
      className="absolute"
      style={{
        bottom: '-20%',
        left: '-10%',
        width: '70%',
        height: '70%',
        background: 'radial-gradient(ellipse at center, var(--glow-primary, rgba(99,102,241,0.28)) 0%, transparent 65%)',
        filter: 'blur(80px)',
      }}
    />
    {/* Secondary glow — top-right */}
    <div
      className="absolute"
      style={{
        top: '-15%',
        right: '-10%',
        width: '55%',
        height: '60%',
        background: 'radial-gradient(ellipse at center, var(--glow-secondary, rgba(139,92,246,0.14)) 0%, transparent 65%)',
        filter: 'blur(100px)',
      }}
    />
  </div>
);

export default DotGridBackground;
