// Renders Alpha's reply as Markdown so he can use lists, bold, headings, links, and code blocks —
// formatted like a real assistant, not a flat blob. Styled compactly for the dark chat surface.

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownReply({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
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
        code: ({ children }) => (
          <code className="rounded bg-[#2a2a2a] px-1.5 py-0.5 font-mono text-[0.85em] text-[#e4e4e7]">
            {children}
          </code>
        ),
        pre: ({ children }) => (
          <pre className="my-2 overflow-x-auto rounded-lg bg-[#0f0f0f] border border-[#2a2a2a] p-3 text-[12px] leading-relaxed">
            {children}
          </pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="my-2 border-l-2 border-[#404040] pl-3 text-[#a1a1aa]">{children}</blockquote>
        ),
        hr: () => <hr className="my-3 border-[#2a2a2a]" />,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
