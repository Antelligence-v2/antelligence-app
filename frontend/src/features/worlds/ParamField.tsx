import { useEffect, useState } from "react";
import type { ParamBounds } from "@/api/engine";
import { Slider } from "@/components/ui/slider";
import { humanize } from "./meta";

/** Integer world parameter: slider plus a numeric input clamped to the engine's bounds. */
export function ParamField({ name, bounds, value, onChange }: {
  name: string;
  bounds: ParamBounds;
  value: number;
  onChange: (v: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  if (name === "dimensionality" && bounds.min === 2 && bounds.max === 3) {
    return (
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm">Space</p>
          <p className="text-2xs text-muted-foreground">{value === 3 ? "Volumetric tumor, bots move in 3D" : "Flat tumor slice (the classic model)"}</p>
        </div>
        <div role="radiogroup" aria-label="Dimensionality" className="flex items-center gap-0.5 rounded-md border p-0.5">
          {[2, 3].map((d) => (
            <button
              key={d}
              type="button"
              role="radio"
              aria-checked={value === d}
              onClick={() => onChange(d)}
              className={`h-7 w-12 rounded text-xs font-medium transition-colors ${value === d ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
            >
              {d}D
            </button>
          ))}
        </div>
      </div>
    );
  }
  const commit = () => {
    const n = Math.round(Number(draft));
    onChange(Number.isFinite(n) ? Math.min(bounds.max, Math.max(bounds.min, n)) : bounds.default);
  };
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={`param-${name}`} className="text-sm">{humanize(name)}</label>
        <input
          id={`param-${name}`}
          inputMode="numeric"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && commit()}
          className="numeric h-7 w-20 rounded-md border bg-transparent px-2 text-right font-mono text-xs outline-none transition-colors focus:border-ring"
        />
      </div>
      <Slider min={bounds.min} max={bounds.max} step={1} value={[value]} onValueChange={([v]) => onChange(v)} aria-label={humanize(name)} />
      <div className="numeric flex justify-between font-mono text-2xs text-muted-foreground">
        <span>{bounds.min}</span>
        <span>default {bounds.default}</span>
        <span>{bounds.max}</span>
      </div>
    </div>
  );
}
