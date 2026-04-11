export function ResultPanel({
  error,
  result,
  loading,
  jsonTitle = "Full API response (JSON)",
}: {
  error: string | null;
  result: unknown;
  loading: boolean;
  /** Heading above the raw JSON block. */
  jsonTitle?: string;
}) {
  return (
    <>
      {loading && (
        <p className="mt-6 text-sm text-slate-500" aria-live="polite">
          Running…
        </p>
      )}
      {error && (
        <div className="mt-6 rounded-xl border border-red-900/50 bg-red-950/40 p-4 text-sm text-red-200">
          {error}
        </div>
      )}
      {result !== null && !loading && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-slate-300">{jsonTitle}</h2>
          <pre className="mt-2 max-h-[480px] overflow-auto rounded-xl border border-surface-border bg-black/40 p-4 font-mono text-xs text-slate-300">
            {JSON.stringify(result, null, 2)}
          </pre>
        </section>
      )}
    </>
  );
}
