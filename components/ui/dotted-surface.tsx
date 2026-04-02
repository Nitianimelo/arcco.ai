'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

import { cn } from '@/lib/utils';

type DottedSurfaceProps = Omit<React.ComponentProps<'div'>, 'ref'>;

const getThemeKey = () =>
  document.documentElement.getAttribute('data-theme') || 'dark';

const getThemeConfig = (themeKey: string) => {
  if (themeKey === 'light') {
    return {
      fog: '#ededef',
      point: '#141414',
      accent: '#6366f1',
      opacity: 0.32,
    };
  }

  if (themeKey === 'ghost') {
    return {
      fog: '#0c0c0c',
      point: '#7c83ff',
      accent: '#8b5cf6',
      opacity: 0.22,
    };
  }

  if (themeKey === 'dim') {
    return {
      fog: '#0a0f1c',
      point: '#c7d2fe',
      accent: '#7c83ff',
      opacity: 0.28,
    };
  }

  if (themeKey === 'midnight') {
    return {
      fog: '#000000',
      point: '#e5e7eb',
      accent: '#a78bfa',
      opacity: 0.26,
    };
  }

  return {
    fog: '#050505',
    point: '#d4d4d8',
    accent: '#818cf8',
    opacity: 0.28,
  };
};

export function DottedSurface({
  className,
  children,
  ...props
}: DottedSurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [themeKey, setThemeKey] = useState('dark');

  useEffect(() => {
    if (typeof document === 'undefined') return;

    const syncTheme = () => setThemeKey(getThemeKey());
    syncTheme();

    const observer = new MutationObserver(syncTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const theme = getThemeConfig(themeKey);
    const width = window.innerWidth;
    const height = window.innerHeight;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(theme.fog, 1800, 7200);

    const camera = new THREE.PerspectiveCamera(58, width / height, 1, 10000);
    camera.position.set(0, 310, 1180);

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setSize(width, height);
    renderer.setClearColor(theme.fog, 0);
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    container.appendChild(renderer.domElement);

    const separation = 120;
    const amountX = 38;
    const amountY = 52;
    const baseColor = new THREE.Color(theme.point);
    const accentColor = new THREE.Color(theme.accent);

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(amountX * amountY * 3);
    const colors = new Float32Array(amountX * amountY * 3);

    let i = 0;
    for (let ix = 0; ix < amountX; ix++) {
      for (let iy = 0; iy < amountY; iy++) {
        const index = i * 3;
        const x = ix * separation - (amountX * separation) / 2;
        const z = iy * separation - (amountY * separation) / 2;
        const mixStrength = iy / amountY;
        const particleColor = baseColor.clone().lerp(accentColor, mixStrength * 0.2);

        positions[index] = x;
        positions[index + 1] = 0;
        positions[index + 2] = z;

        colors[index] = particleColor.r;
        colors[index + 1] = particleColor.g;
        colors[index + 2] = particleColor.b;
        i++;
      }
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 7,
      vertexColors: true,
      transparent: true,
      opacity: theme.opacity,
      sizeAttenuation: true,
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    let count = 0;
    let frameId = 0;

    const handleResize = () => {
      const nextWidth = window.innerWidth;
      const nextHeight = window.innerHeight;
      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(nextWidth, nextHeight);
    };

    const animate = () => {
      frameId = window.requestAnimationFrame(animate);

      const positionAttribute = geometry.getAttribute('position') as THREE.BufferAttribute;
      const positionArray = positionAttribute.array as Float32Array;

      let offset = 0;
      for (let ix = 0; ix < amountX; ix++) {
        for (let iy = 0; iy < amountY; iy++) {
          const index = offset * 3;
          positionArray[index + 1] =
            Math.sin((ix + count) * 0.34) * 26 +
            Math.sin((iy + count) * 0.42) * 24;
          offset++;
        }
      }

      positionAttribute.needsUpdate = true;
      points.rotation.z = Math.sin(count * 0.08) * 0.04;
      renderer.render(scene, camera);
      count += 0.035;
    };

    window.addEventListener('resize', handleResize);
    animate();

    return () => {
      window.removeEventListener('resize', handleResize);
      window.cancelAnimationFrame(frameId);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [themeKey]);

  return (
    <div
      ref={containerRef}
      className={cn('pointer-events-none fixed inset-0 z-0 overflow-hidden', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export default DottedSurface;
