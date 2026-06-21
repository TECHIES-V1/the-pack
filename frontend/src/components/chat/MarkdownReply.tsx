// Renders Alpha's reply as Markdown so he can use lists, bold, headings, links, and code blocks —
// formatted like a real assistant, not a flat blob. Code is syntax-highlighted (highlight.js) and
// every code block gets a "Copy" button (the most-cited table-stakes detail).

import { useRef, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

// A fenced code block with a hover "Copy" button. Copies the raw text via the rendered <pre>.
function CodeBlock({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);
  function copy() {
    const code = ref.current?.textContent ?? "";
    navigator.clipboard?.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  }
  return (
    <div className="group/code relative my-2">
      <button
        onClick={copy}
        className="absolute top-2 right-2 z-10 rounded-md border border-[#2a2a2a] bg-[#1a1a1a] px-2 py-0.5 text-[11px] text-[#a1a1aa] opacity-0 group-hover/code:opacity-100 hover:text-white transition-opacity cursor-pointer"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      <pre
        ref={ref}
        className="overflow-x-auto rounded-lg bg-[#0f0f0f] border border-[#2a2a2a] p-3 text-[12px] leading-relaxed"
      >
        {children}
      </pre>
    </div>
  );
}

export function MarkdownReply({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
      components={{
        p: ({ children }) => <p className="my-1.5 first:mt-0 last:mb-0 leading-relaxed">{children}</p>,
        ul: ({ children }) => <ul className="my-1.5 flex flex-col gap-1 pl-1">{children}</ul>,
        ol: ({ children }) => (
          <ol className="my-1.5 flex flex-col gap-1 pl-5 list-decimal marker:text-[#71717a]">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="flex gap-2 [ol_&]:list-item [ol_&]:pl-1">
            <span className="mt-[9px] hidden h-1 w-1 shrink-0 rounded-full bg-[#e6a23c]/70 [ul_&]:block" />
            <span className="flex-1">{children}</span>
          </li>
        ),
        strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noreferrer" className="text-[#e6a23c] underline underline-offset-2">
            {children}
          </a>
        ),
        h1: ({ children }) => <h1 className="mt-3 mb-1 text-[15px] font-semibold text-white">{children}</h1>,
        h2: ({ children }) => <h2 className="mt-3 mb-1 text-[14px] font-semibold text-white">{children}</h2>,
        h3: ({ children }) => <h3 className="mt-2 mb-1 text-[13px] font-semibold text-white">{children}</h3>,
        // Block code (highlighted by rehype-highlight) keeps its hljs classes; inline code gets the
        // pill treatment.
        code: ({ className, children }) => {
          const isBlock = /\blanguage-|\bhljs\b/.test(className || "");
          if (isBlock) return <code className={className}>{children}</code>;
          return (
            <code className="rounded bg-[#2a2a2a] px-1.5 py-0.5 font-mono text-[0.85em] text-[#e4e4e7]">
              {children}
            </code>
          );
        },
        pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
        blockquote: ({ children }) => (
          <blockquote className="my-2 border-l-2 border-[#404040] pl-3 text-[#a1a1aa]">{children}</blockquote>
        ),
        hr: () => <hr className="my-3 border-[#2a2a2a]" />,
        table: ({ children }) => (
          <div className="my-3 overflow-x-auto">
            <table className="w-full text-left border-collapse text-[0.9em]">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="text-[#a1a1aa]">{children}</thead>,
        th: ({ children }) => (
          <th className="border-b border-[#3a3a3a] px-2.5 py-1.5 font-semibold text-white align-top">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border-b border-[#222] px-2.5 py-1.5 align-top">{children}</td>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
