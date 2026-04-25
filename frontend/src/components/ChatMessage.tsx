import { useQuery } from "@tanstack/react-query";
import { fetchResult, type ConversationMessage } from "../api/chat";
import ChartRenderer, { type ChartSpec } from "./ChartRenderer";
import DataTable from "./DataTable";
import PinButton from "./PinButton";
import QueryDebugPanel from "./QueryDebugPanel";

export type LiveAssistantMessage = {
  role: "assistant";
  status: "running" | "done" | "error";
  steps: { kind: "text" | "tool"; text: string; toolName?: string; isError?: boolean }[];
  final?: {
    summary: string;
    query: string;
    chart: ChartSpec | null;
    data_ref: string | null;
  };
  errorMessage?: string;
};

type Props = { msg: ConversationMessage | { role: "user"; content: string } | LiveAssistantMessage };

function isUserStub(m: Props["msg"]): m is { role: "user"; content: string } {
  return (m as any).role === "user" && typeof (m as any).content === "string";
}

function isLive(m: Props["msg"]): m is LiveAssistantMessage {
  return (m as any).status !== undefined;
}

export default function ChatMessage({ msg }: Props) {
  if (isUserStub(msg)) {
    return (
      <div className="msg msg-user">
        <div className="msg-role">Jij</div>
        <div className="msg-body">{msg.content}</div>
      </div>
    );
  }

  if (isLive(msg)) {
    return <LiveMessage msg={msg} />;
  }

  // ConversationMessage from the server
  if (msg.role === "user") {
    const text = msg.content
      .filter((b: any) => b.type === "text")
      .map((b: any) => b.text)
      .join("\n");
    return (
      <div className="msg msg-user">
        <div className="msg-role">Jij</div>
        <div className="msg-body">{text}</div>
      </div>
    );
  }

  return (
    <div className="msg msg-assistant">
      <div className="msg-role">HouseDataBrowser</div>
      <div className="msg-body">
        {msg.final_summary && <p className="summary">{msg.final_summary}</p>}
        {msg.final_data_ref && msg.final_chart && (
          <ResultBlock
            dataRef={msg.final_data_ref}
            chart={msg.final_chart as ChartSpec}
          />
        )}
        {msg.final_data_ref && !msg.final_chart && (
          <ResultTable dataRef={msg.final_data_ref} />
        )}
        {msg.final_chart && msg.final_query && (
          <PinButton
            query={msg.final_query}
            chartSpec={msg.final_chart as ChartSpec}
          />
        )}
        {msg.final_query && <QueryDebugPanel query={msg.final_query} />}
      </div>
    </div>
  );
}

function LiveMessage({ msg }: { msg: LiveAssistantMessage }) {
  const final = msg.final;
  return (
    <div className="msg msg-assistant">
      <div className="msg-role">
        HouseDataBrowser
        {msg.status === "running" && <span className="dot-pulse" aria-label="bezig"> ●●●</span>}
      </div>
      <div className="msg-body">
        {!final && (
          <ul className="step-list">
            {msg.steps.map((s, i) => (
              <li key={i} className={s.isError ? "step-error" : ""}>
                {s.kind === "tool" ? (
                  <>
                    <code>{s.toolName}</code> {s.text}
                  </>
                ) : (
                  <span className="step-text">{s.text}</span>
                )}
              </li>
            ))}
          </ul>
        )}
        {msg.errorMessage && <div className="error-banner">Fout: {msg.errorMessage}</div>}
        {final && (
          <>
            {final.summary && <p className="summary">{final.summary}</p>}
            {final.data_ref && final.chart && (
              <ResultBlock dataRef={final.data_ref} chart={final.chart} />
            )}
            {final.data_ref && !final.chart && <ResultTable dataRef={final.data_ref} />}
            {final.chart && final.query && (
              <PinButton query={final.query} chartSpec={final.chart} />
            )}
            {final.query && (
              <QueryDebugPanel
                query={final.query}
                events={msg.steps
                  .filter((s) => s.kind === "tool")
                  .map((s) => ({ name: s.toolName ?? "", preview: s.text }))}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ResultBlock({ dataRef, chart }: { dataRef: string; chart: ChartSpec }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["result", dataRef],
    queryFn: () => fetchResult(dataRef),
    staleTime: Infinity,
  });
  if (isLoading) return <div className="muted">data laden…</div>;
  if (isError) return <div className="error-banner">Fout bij laden van resultaat: {(error as Error).message}</div>;
  if (!data) return null;
  return (
    <>
      <ChartRenderer spec={chart} rows={data.rows} />
      <details className="raw-table">
        <summary>Toon datatabel ({data.rows.length} rijen)</summary>
        <DataTable columns={data.columns} rows={data.rows} />
      </details>
    </>
  );
}

function ResultTable({ dataRef }: { dataRef: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["result", dataRef],
    queryFn: () => fetchResult(dataRef),
    staleTime: Infinity,
  });
  if (isLoading) return <div className="muted">data laden…</div>;
  if (!data) return null;
  return <DataTable columns={data.columns} rows={data.rows} />;
}
