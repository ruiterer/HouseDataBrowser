import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  content: string;
  className?: string;
};

/**
 * Renders an LLM-produced summary as Markdown. GFM enables tables, task lists,
 * and strikethrough. Raw HTML in the source is NOT rendered (no rehype-raw),
 * which keeps us safe from accidental injection through model output.
 *
 * Links open in a new tab. Tables get a wrapper so wide ones scroll
 * horizontally without breaking the chat bubble layout.
 */
export default function Markdown({ content, className }: Props) {
  return (
    <div className={className ? `markdown ${className}` : "markdown"}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, ...rest }) => (
            <a {...rest} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          table: ({ children, ...rest }) => (
            <div className="md-table-wrap">
              <table {...rest}>{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
