import {
  forwardRef,
  useCallback,
  useRef,
  type ChangeEvent,
  type InputHTMLAttributes,
} from "react";

const YMD = /^\d{4}-\d{2}-\d{2}$/;

/** True iff string is a real calendar day in UTC (matches `YYYY-MM-DD`). */
export function isValidYmd(s: string): boolean {
  if (!YMD.test(s)) return false;
  const d = new Date(`${s}T00:00:00.000Z`);
  if (Number.isNaN(d.getTime())) return false;
  return d.toISOString().slice(0, 10) === s;
}

/** Strip non-digits, cap at 8 digits, insert dashes → always shows as YYYY-MM-DD style while typing. */
export function formatPartialYmd(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 4) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 4)}-${digits.slice(4)}`;
  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6)}`;
}

function CalendarGlyph() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

type Props = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "onChange" | "placeholder" | "inputMode" | "autoComplete"
> & {
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
};

/**
 * Visible **YYYY-MM-DD** text field plus a native calendar (via hidden `type="date"` + `showPicker()`).
 * The main field always shows ISO order; the browser popup may still follow locale, but the committed value is ISO.
 */
export const DateYmdInput = forwardRef<HTMLInputElement, Props>(function DateYmdInput(
  { value, onChange, min, max, className = "", onBlur, disabled, ...rest },
  ref,
) {
  const hiddenRef = useRef<HTMLInputElement>(null);

  const handleChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      onChange(formatPartialYmd(e.target.value));
    },
    [onChange],
  );

  const handleNativeChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const v = e.target.value;
      if (v) onChange(v);
    },
    [onChange],
  );

  const complete = value.length === 10;
  const minOk = min != null && min !== "" && YMD.test(min);
  const maxOk = max != null && max !== "" && YMD.test(max);
  const invalidRange =
    complete &&
    isValidYmd(value) &&
    ((minOk && min != null && value < min) || (maxOk && max != null && value > max));
  const invalidDate = complete && !isValidYmd(value);
  const ariaInvalid = invalidDate || invalidRange || undefined;

  const openPicker = useCallback(() => {
    if (disabled) return;
    const h = hiddenRef.current;
    if (!h) return;
    const trimmed = value.trim();
    h.value = isValidYmd(trimmed) ? trimmed : "";
    if (minOk && min != null) h.min = min;
    else h.removeAttribute("min");
    if (maxOk && max != null) h.max = max;
    else h.removeAttribute("max");
    const picker = (h as HTMLInputElement & { showPicker?: () => void }).showPicker;
    if (typeof picker === "function") {
      try {
        picker.call(h);
        return;
      } catch {
        /* user gesture / security — fall through */
      }
    }
    h.focus();
    h.click();
  }, [value, min, max, minOk, maxOk, disabled]);

  const wrapClass = ["flex min-w-0 items-stretch font-mono tabular-nums", className].filter(Boolean).join(" ");

  return (
    <div className={wrapClass}>
      <input
        ref={ref}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        placeholder="YYYY-MM-DD"
        maxLength={10}
        value={value}
        onChange={handleChange}
        onBlur={onBlur}
        disabled={disabled}
        aria-invalid={ariaInvalid}
        className="min-w-0 flex-1 border-0 bg-transparent py-2 pl-0 pr-1 text-inherit outline-none ring-0 focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50"
        {...rest}
      />
      <button
        type="button"
        disabled={disabled}
        className="flex shrink-0 items-center justify-center border-l border-surface-border px-2.5 text-slate-500 hover:bg-white/5 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Open calendar"
        title="Open calendar"
        tabIndex={-1}
        onClick={(e) => {
          e.preventDefault();
          openPicker();
        }}
      >
        <CalendarGlyph />
      </button>
      <input
        ref={hiddenRef}
        type="date"
        tabIndex={-1}
        aria-hidden
        className="sr-only"
        onChange={handleNativeChange}
      />
    </div>
  );
});
