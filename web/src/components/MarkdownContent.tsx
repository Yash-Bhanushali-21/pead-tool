import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  /** Markdown source */
  source: string;
  className?: string;
};

/**
 * Renders GitHub-flavored Markdown with dark-theme typography (headings, lists, tables, code).
 */
export function MarkdownContent({ source, className = "" }: Props) {
  const trimmed = source.trim();
  if (!trimmed) return null;

  return (
    <div
      className={[
        "prose prose-invert max-w-none text-[15px] leading-relaxed",
        "prose-headings:scroll-mt-4 prose-headings:font-semibold prose-headings:tracking-tight prose-headings:text-slate-100",
        "prose-h1:text-xl prose-h2:text-lg prose-h3:text-base",
        "prose-p:text-slate-200 prose-p:my-3 prose-p:first:mt-0 prose-p:last:mb-0",
        "prose-strong:text-white prose-strong:font-semibold",
        "prose-a:text-sky-400 prose-a:no-underline hover:prose-a:underline",
        "prose-ul:my-3 prose-ol:my-3 prose-li:my-1 prose-li:marker:text-slate-500",
        "prose-blockquote:border-l-sky-600 prose-blockquote:bg-slate-900/40 prose-blockquote:py-0.5 prose-blockquote:not-italic prose-blockquote:text-slate-300",
        "prose-code:rounded prose-code:bg-black/35 prose-code:px-1.5 prose-code:py-0.5 prose-code:font-mono prose-code:text-[13px] prose-code:text-sky-200 prose-code:before:content-none prose-code:after:content-none",
        "prose-pre:bg-black/45 prose-pre:border prose-pre:border-surface-border prose-pre:text-[13px]",
        "prose-hr:border-surface-border",
        "prose-table:text-sm prose-th:border prose-th:border-surface-border prose-td:border prose-td:border-surface-border",
        className,
      ].join(" ")}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{trimmed}</ReactMarkdown>
    </div>
  );
}
