import { Link } from "react-router-dom";

export function ToolPageChrome({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-surface pb-24">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <Link to="/tools" className="text-sm text-sky-400 hover:text-sky-300">
          ← All tools
        </Link>
        <h1 className="mt-4 text-xl font-semibold text-white">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
        {children}
      </div>
    </div>
  );
}
