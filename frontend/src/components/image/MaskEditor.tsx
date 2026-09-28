"use client";

import clsx from "clsx";
import { useCallback, useEffect, useImperativeHandle, useRef, useState, type PointerEvent, type RefObject } from "react";

import { Button } from "@/components/ui/Button";
import { api, type AssetRead } from "@/lib/api/client";
import { hasPaint, overlayToMask } from "@/lib/imageEdit";

export interface MaskHandle {
  /** Uploads the painted area as a white-on-black PNG at source resolution. */
  exportMask: () => Promise<AssetRead>;
}

type Tool = "paint" | "erase";

export function MaskEditor({
  source,
  handle,
  onPaintedChange,
}: {
  source: AssetRead & { width: number; height: number };
  handle: RefObject<MaskHandle | null>;
  onPaintedChange: (painted: boolean) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef<{ x: number; y: number } | null>(null);
  const [tool, setTool] = useState<Tool>("paint");
  const [brush, setBrush] = useState(() => Math.max(8, Math.round(Math.min(source.width, source.height) / 16)));

  const context = useCallback(() => canvas.current?.getContext("2d", { willReadFrequently: true }) ?? null, []);

  const clear = useCallback(() => {
    const ctx = context();
    ctx?.clearRect(0, 0, source.width, source.height);
    onPaintedChange(false);
  }, [context, onPaintedChange, source.width, source.height]);

  // A new source invalidates the painted mask.
  useEffect(() => clear(), [source.id, clear]);

  useImperativeHandle(handle, () => ({
    exportMask: async () => {
      const ctx = context();
      if (!ctx) throw new Error("Canvas is not available in this browser.");
      const painted = ctx.getImageData(0, 0, source.width, source.height);
      const out = document.createElement("canvas");
      out.width = source.width;
      out.height = source.height;
      const outCtx = out.getContext("2d");
      if (!outCtx) throw new Error("Canvas is not available in this browser.");
      outCtx.putImageData(new ImageData(overlayToMask(painted.data), source.width, source.height), 0, 0);
      const blob = await new Promise<Blob | null>((resolve) => out.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("Could not encode the mask.");
      return api.assets.upload(new File([blob], "mask.png", { type: "image/png" }));
    },
  }));

  function point(event: PointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * source.width,
      y: ((event.clientY - rect.top) / rect.height) * source.height,
    };
  }

  function stroke(to: { x: number; y: number }) {
    const ctx = context();
    if (!ctx) return;
    const from = last.current ?? to;
    ctx.globalCompositeOperation = tool === "paint" ? "source-over" : "destination-out";
    ctx.strokeStyle = "rgb(255, 64, 64)";
    ctx.lineWidth = brush;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x + 0.01, to.y);
    ctx.stroke();
    last.current = to;
  }

  function end() {
    if (!last.current) return;
    last.current = null;
    const ctx = context();
    if (ctx) onPaintedChange(hasPaint(ctx.getImageData(0, 0, source.width, source.height).data));
  }

  return (
    <div className="space-y-2">
      <div className="relative w-full overflow-hidden rounded-md border border-border bg-black">
        {/* eslint-disable-next-line @next/next/no-img-element -- local API image */}
        <img src={api.assets.contentUrl(source.id)} alt="Source" className="block w-full select-none" draggable={false} />
        <canvas
          ref={canvas}
          width={source.width}
          height={source.height}
          aria-label="Mask canvas"
          className="absolute inset-0 size-full cursor-crosshair touch-none opacity-50"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            stroke(point(e));
          }}
          onPointerMove={(e) => {
            if (last.current) stroke(point(e));
          }}
          onPointerUp={end}
          onPointerCancel={end}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <div role="radiogroup" aria-label="Mask tool" className="flex gap-1">
          {(["paint", "erase"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={tool === t}
              onClick={() => setTool(t)}
              className={clsx(
                "rounded-md border px-2 py-1 text-xs capitalize",
                tool === t ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-raised",
              )}
            >
              {t}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs text-muted">
          Brush
          <input
            type="range"
            min={4}
            max={256}
            value={brush}
            onChange={(e) => setBrush(Number(e.target.value))}
            aria-label="Brush size"
          />
          <span className="w-12 tabular-nums">{brush}px</span>
        </label>
        <Button variant="ghost" className="px-2 py-1 text-xs" onClick={clear}>
          Clear
        </Button>
      </div>
      <p className="text-xs text-muted">Paint the area to change. Everything else is kept pixel-for-pixel.</p>
    </div>
  );
}
