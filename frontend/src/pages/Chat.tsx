import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getConversation,
  streamChat,
  type ConversationMessage,
} from "../api/chat";
import ChatInput from "../components/ChatInput";
import ChatThread from "../components/ChatThread";
import ConversationSidebar from "../components/ConversationSidebar";
import type { LiveAssistantMessage } from "../components/ChatMessage";
import type { ChartSpec } from "../components/ChartRenderer";

export default function Chat() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [live, setLive] = useState<LiveAssistantMessage | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const { data: convo } = useQuery({
    queryKey: ["conversation", activeId],
    queryFn: () => (activeId ? getConversation(activeId) : Promise.resolve(null)),
    enabled: !!activeId,
  });

  const messages: ConversationMessage[] = convo?.messages ?? [];

  const onSelect = useCallback((id: string | null) => {
    abortRef.current?.abort();
    abortRef.current = null;
    setActiveId(id);
    setPendingUser(null);
    setLive(null);
  }, []);

  const send = useCallback(
    async (text: string, opts: { deep: boolean }) => {
      if (live?.status === "running") return;
      setPendingUser(text);
      setLive({ role: "assistant", status: "running", steps: [] });

      const ac = new AbortController();
      abortRef.current = ac;

      try {
        await streamChat({
          conversationId: activeId,
          message: text,
          deep: opts.deep,
          signal: ac.signal,
          onEvent: (ev) => {
            if (ev.event === "conversation") {
              if (!activeId) {
                setActiveId(ev.data.id);
                qc.invalidateQueries({ queryKey: ["conversations"] });
              }
            } else if (ev.event === "agent_start") {
              const effort = ev.data.effort ? ` · effort=${ev.data.effort}` : "";
              setLive((m) =>
                m
                  ? {
                      ...m,
                      steps: [
                        ...m.steps,
                        {
                          kind: "text",
                          text: `model: ${ev.data.model}${effort}`,
                        },
                      ],
                    }
                  : m,
              );
            } else if (ev.event === "assistant_text") {
              setLive((m) =>
                m ? { ...m, steps: [...m.steps, { kind: "text", text: ev.data.text }] } : m,
              );
            } else if (ev.event === "tool_call") {
              setLive((m) =>
                m
                  ? {
                      ...m,
                      steps: [
                        ...m.steps,
                        {
                          kind: "tool",
                          toolName: ev.data.name,
                          text: shortInput(ev.data.input),
                        },
                      ],
                    }
                  : m,
              );
            } else if (ev.event === "tool_result") {
              setLive((m) => {
                if (!m) return m;
                const steps = [...m.steps];
                const last = [...steps].reverse().find(
                  (s) => s.kind === "tool" && s.toolName === ev.data.name,
                );
                if (last) {
                  last.text = `${last.text} → ${ev.data.preview}`;
                  if (ev.data.is_error) last.isError = true;
                }
                return { ...m, steps };
              });
            } else if (ev.event === "final") {
              setLive((m) =>
                m
                  ? {
                      ...m,
                      status: "done",
                      final: {
                        summary: ev.data.summary,
                        query: ev.data.query,
                        chart: ev.data.chart as ChartSpec | null,
                        data_ref: ev.data.data_ref,
                      },
                    }
                  : m,
              );
            } else if (ev.event === "error") {
              setLive((m) =>
                m ? { ...m, status: "error", errorMessage: ev.data.message } : m,
              );
            } else if (ev.event === "saved") {
              // Refetch all conversation queries (don't filter by activeId — the
              // outer closure may have captured the OLD null id when this is the
              // first turn of a new conversation).
              qc.invalidateQueries({ queryKey: ["conversation"] });
              qc.invalidateQueries({ queryKey: ["conversations"] });
              setPendingUser(null);
              setLive(null);
            }
          },
          onError: (err) => {
            console.error("stream error", err);
            setLive((m) => (m ? { ...m, status: "error", errorMessage: String(err) } : m));
          },
        });
      } catch (err) {
        console.error("send failed", err);
        setLive((m) => (m ? { ...m, status: "error", errorMessage: String(err) } : m));
      }
    },
    [activeId, live, qc],
  );

  useEffect(() => () => abortRef.current?.abort(), []);

  return (
    <div className="chat-page">
      <ConversationSidebar activeId={activeId} onSelect={onSelect} />
      <section className="chat-main">
        <ChatThread messages={messages} pendingUser={pendingUser} live={live} />
        <ChatInput onSend={send} disabled={live?.status === "running"} />
      </section>
    </div>
  );
}

function shortInput(input: any): string {
  try {
    const s = JSON.stringify(input);
    return s.length > 120 ? s.slice(0, 120) + "…" : s;
  } catch {
    return "";
  }
}
