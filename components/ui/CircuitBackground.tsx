import React, { useEffect, useRef } from 'react';

const CircuitBackground: React.FC = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;

        // Circuit config - REFINED (Slower, fewer, subtler)
        const gridSize = 60; // Larger grid for less clutter
        const lineOpacity = 0.03; // Very subtle lines
        const electronCount = 6; // Few electrons
        const electronSpeed = 0.3; // Very slow movement
        const electronColor = '#6366f1'; // Indigo-500

        // Lines storage
        const lines: { x1: number, y1: number, x2: number, y2: number }[] = [];
        // Electrons storage
        const electrons: {
            lineIndex: number,
            progress: number,
            speed: number,
            size: number
        }[] = [];

        const init = () => {
            lines.length = 0;
            electrons.length = 0;

            // Generate vertical lines
            for (let x = 0; x <= width; x += gridSize) {
                if (Math.random() > 0.5) {
                    lines.push({ x1: x, y1: 0, x2: x, y2: height });
                }
            }
            // Generate horizontal lines
            for (let y = 0; y <= height; y += gridSize) {
                if (Math.random() > 0.5) {
                    lines.push({ x1: 0, y1: y, x2: width, y2: y });
                }
            }

            // Spawn electrons
            for (let i = 0; i < electronCount; i++) {
                spawnElectron();
            }
        };

        const spawnElectron = () => {
            if (lines.length === 0) return;
            const lineIndex = Math.floor(Math.random() * lines.length);
            electrons.push({
                lineIndex,
                progress: Math.random(),
                speed: (Math.random() * 0.5 + 0.5) * electronSpeed * 0.005,
                size: Math.random() * 1.5 + 0.5
            });
        };

        const animate = () => {
            ctx.clearRect(0, 0, width, height);

            // Draw background (very dark)
            ctx.fillStyle = '#050505';
            ctx.fillRect(0, 0, width, height);

            // Draw lines
            ctx.strokeStyle = `rgba(255, 255, 255, ${lineOpacity})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            lines.forEach(line => {
                ctx.moveTo(line.x1, line.y1);
                ctx.lineTo(line.x2, line.y2);
            });
            ctx.stroke();

            // Draw electrons
            electrons.forEach((e, idx) => {
                const line = lines[e.lineIndex];
                e.progress += e.speed;

                if (e.progress >= 1) {
                    // Respawn elsewhere when done
                    electrons[idx] = {
                        lineIndex: Math.floor(Math.random() * lines.length),
                        progress: 0,
                        speed: (Math.random() * 0.5 + 0.5) * electronSpeed * 0.005,
                        size: Math.random() * 1.5 + 0.5
                    };
                    return;
                }

                const x = line.x1 + (line.x2 - line.x1) * e.progress;
                const y = line.y1 + (line.y2 - line.y1) * e.progress;

                // Glowing effect (Very subtle now)
                const gradient = ctx.createRadialGradient(x, y, 0, x, y, e.size * 3);
                gradient.addColorStop(0, electronColor);
                gradient.addColorStop(1, 'transparent');

                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(x, y, e.size * 3, 0, Math.PI * 2);
                ctx.fill();

                // Core
                ctx.fillStyle = '#fff';
                ctx.beginPath();
                ctx.arc(x, y, e.size, 0, Math.PI * 2);
                ctx.fill();
            });

            requestAnimationFrame(animate);
        };

        const handleResize = () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
            init();
        };

        window.addEventListener('resize', handleResize);
        init();
        animate();

        return () => window.removeEventListener('resize', handleResize);
    }, []);

    return (
        <canvas
            ref={canvasRef}
            className="fixed inset-0 pointer-events-none z-0 opacity-20"
            style={{ mixBlendMode: 'screen' }}
        />
    );
};

export default CircuitBackground;
