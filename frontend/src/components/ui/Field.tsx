import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { useId } from "react";

const CONTROL =
  "w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm outline-none focus:border-accent";

function Label({ htmlFor, children }: { htmlFor: string; children: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-xs font-medium text-muted">
      {children}
    </label>
  );
}

export function TextField({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId();
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <input id={id} className={CONTROL} {...props} />
    </div>
  );
}

export interface Option<T extends string | number> {
  value: T;
  label: string;
}

export function SelectField<T extends string | number>({
  label,
  options,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; options: readonly Option<T>[] }) {
  const id = useId();
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <select id={id} className={CONTROL} {...props}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
