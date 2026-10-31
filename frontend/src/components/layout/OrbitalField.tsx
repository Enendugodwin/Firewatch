import { useEffect, useRef } from "react";

/**
 * Full-bleed perspective grid field — the orbital frame behind the console.
 *
 * The design calls for a WebGL grid field (green on black, sparse, slow
 * breathing pulse, pointer drift, DOM fallback). This is drawn with Canvas 2D:
 * identical visual language, no 300 kB renderer in a data-critical bundle, and
 * it degrades to a static frame when the user prefers reduced motion or when
 * `getContext("2d")` is unavailable (the CSS gradient behind it remains).
 */
export function OrbitalField({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let context: CanvasRenderingContext2D | null = null;
    try {
      context = canvas.getContext("2d");
    } catch {
      // jsdom, blocked canvases and some kiosk browsers throw instead of
      // returning null. The CSS gradient behind the canvas is the fallback.
      return;
    }
    if (!context) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const state = {
      width: 0,
      height: 0,
      dpr: 1,
      pointerX: 0,
      pointerY: 0,
      targetX: 0,
      targetY: 0,
      frame: 0,
      start: performance.now(),
    };

    function resize() {
      if (!canvas) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      state.dpr = dpr;
      state.width = canvas.clientWidth;
      state.height = canvas.clientHeight;
      canvas.width = Math.floor(state.width * dpr);
      canvas.height = Math.floor(state.height * dpr);
      context?.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function drawGrid(time: number) {
      const ctx = context;
      if (!ctx) return;
      const { width: w, height: h } = state;
      if (w === 0 || h === 0) return;

      ctx.clearRect(0, 0, w, h);

      // Breathing pulse: slow, low amplitude, never distracting.
      const breath = reducedMotion ? 0.6 : 0.58 + 0.42 * Math.sin(time / 5200);
      const horizon = h * 0.6 + state.pointerY * 6;
      const vx = w * 0.5 + state.pointerX * 18;

      // Depth glow behind the horizon.
      const glow = ctx.createRadialGradient(vx, horizon, 0, vx, horizon, Math.max(w, h) * 0.55);
      glow.addColorStop(0, `rgba(96, 213, 139, ${0.055 * breath})`);
      glow.addColorStop(0.45, `rgba(96, 213, 139, ${0.02 * breath})`);
      glow.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, w, h);

      // Vertical spans converging on the vanishing point.
      const bottom = h * 1.02;
      const spacing = w / 7;
      const columns = Math.ceil(w / spacing) + 6;
      ctx.lineWidth = 1;
      for (let i = -3; i <= columns; i += 1) {
        const bottomX = vx + (i - 3) * spacing - w * 0.02;
        const edge = Math.abs(bottomX - vx) / (w * 0.75);
        const alpha = Math.max(0, 0.23 - edge * 0.18) * breath;
        if (alpha <= 0.002) continue;
        ctx.strokeStyle = `rgba(96, 213, 139, ${alpha})`;
        ctx.beginPath();
        ctx.moveTo(vx, horizon);
        ctx.lineTo(bottomX, bottom);
        ctx.stroke();
      }

      // Horizontal spans with perspective compression toward the horizon.
      const rows = 14;
      const phase = reducedMotion ? 0.35 : (time / 16000) % 1;
      for (let i = 0; i < rows; i += 1) {
        const t = (i + phase) / rows;
        const y = horizon + (bottom - horizon) * t ** 2.5;
        if (y <= horizon || y > h) continue;
        const depth = 1 - t;
        const alpha = (0.06 + depth * 0.18) * breath;
        const leftX = vx + (-w * 0.45 - vx) * t;
        const rightX = vx + (w * 1.45 - vx) * t;
        ctx.strokeStyle = `rgba(96, 213, 139, ${alpha})`;
        ctx.beginPath();
        ctx.moveTo(leftX, y);
        ctx.lineTo(rightX, y);
        ctx.stroke();
      }

      // Horizon hairline.
      ctx.strokeStyle = `rgba(114, 165, 249, ${0.1 * breath})`;
      ctx.beginPath();
      ctx.moveTo(0, horizon);
      ctx.lineTo(w, horizon);
      ctx.stroke();
    }

    function loop(time: number) {
      state.pointerX += (state.targetX - state.pointerX) * 0.035;
      state.pointerY += (state.targetY - state.pointerY) * 0.035;
      drawGrid(time - state.start);
      state.frame = window.requestAnimationFrame(loop);
    }

    function onPointerMove(event: PointerEvent) {
      state.targetX = event.clientX / window.innerWidth - 0.5;
      state.targetY = event.clientY / window.innerHeight - 0.5;
    }

    resize();
    if (reducedMotion) {
      drawGrid(0);
    } else {
      state.frame = window.requestAnimationFrame(loop);
      window.addEventListener("pointermove", onPointerMove, { passive: true });
    }

    const onResize = () => {
      resize();
      if (reducedMotion) drawGrid(0);
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.cancelAnimationFrame(state.frame);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <div
      aria-hidden
      className={`pointer-events-none fixed inset-0 z-0 overflow-hidden ${className ?? ""}`}
      style={{
        background:
          "radial-gradient(120% 80% at 50% 66%, #0B101D 0%, #131315 55%, #131315 100%)",
      }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      {/* Fuse the field into the chrome at both edges. */}
      <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-canvas via-canvas/60 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-canvas via-canvas/70 to-transparent" />
    </div>
  );
}
