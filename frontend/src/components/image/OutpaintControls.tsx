import { SelectField } from "@/components/ui/Field";
import { api, type AssetRead } from "@/lib/api/client";
import { editOutputSize, MAX_PADDING, PADDING_STEP, type Padding } from "@/lib/imageEdit";

const SIDES = ["left", "top", "right", "bottom"] as const;
const OPTIONS = Array.from({ length: MAX_PADDING / PADDING_STEP + 1 }, (_, i) => ({
  value: i * PADDING_STEP,
  label: `${i * PADDING_STEP}px`,
}));

export function OutpaintControls({
  source,
  value,
  onChange,
}: {
  source: AssetRead & { width: number; height: number };
  value: Padding;
  onChange: (padding: Padding) => void;
}) {
  const inner = editOutputSize(source, "inpaint");
  const total = editOutputSize(source, "outpaint", value);
  const pct = (part: number, whole: number) => `${(part / whole) * 100}%`;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {SIDES.map((side) => (
          <SelectField
            key={side}
            label={`Extend ${side}`}
            options={OPTIONS}
            value={value[side]}
            onChange={(e) => onChange({ ...value, [side]: Number(e.target.value) })}
          />
        ))}
      </div>
      <div className="mx-auto max-w-sm">
        <div
          data-testid="outpaint-preview"
          className="relative w-full rounded-md border border-dashed border-accent bg-surface-raised"
          style={{ aspectRatio: `${total.width} / ${total.height}` }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- local API thumbnail */}
          <img
            src={api.assets.thumbnailUrl(source.id)}
            alt="Source"
            className="absolute object-cover"
            style={{
              left: pct(value.left, total.width),
              top: pct(value.top, total.height),
              width: pct(inner.width, total.width),
              height: pct(inner.height, total.height),
            }}
          />
        </div>
        <p className="mt-1 text-center text-xs text-muted">
          Result {total.width}×{total.height}px (source {inner.width}×{inner.height})
        </p>
      </div>
    </div>
  );
}
