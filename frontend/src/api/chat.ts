import { fetchEventSource } from "@microsoft/fetch-event-source";
import { apiUrl } from "../base";

export type ChatEvent =
  | { event: "conversation"; data: { id: string; title: string } }
  | { event: "user_message_saved"; data: { id: string } }
  | { event: "agent_start"; data: { provider: string; model: string; effort?: string } }
  | { event: "assistant_text"; data: { text: string; step: number } }
  | { event: "tool_call"; data: { id: string; name: string; input: any; step: number } }
  | {
      event: "tool_result";
      data: { id: string; name: string; is_error: boolean; preview: string; step: number };
    }
  | { event: "usage"; data: Record<string, number> }
  | {
      event: "final";
      data: { summary: string; query: string; chart: any | null; data_ref: string | null };
    }
  | { event: "saved"; data: { assistant_message_id: string } }
  | { event: "done"; data: any }
  | { event: "error"; data: { message: string } };

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: any[];
  final_summary: string | null;
  final_query: string | null;
  final_chart: any | null;
  final_data_ref: string | null;
  created_at: string;
};

export type ConversationDetail = {
  conversation: Conversation;
  messages: ConversationMessage[];
};

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(apiUrl("/api/conversations"));
  if (!res.ok) throw new Error("listConversations failed");
  return res.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const res = await fetch(apiUrl(`/api/conversations/${id}`));
  if (!res.ok) throw new Error("getConversation failed");
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/conversations/${id}`), { method: "DELETE" });
  if (!res.ok) throw new Error("deleteConversation failed");
}

export type StreamChatOpts = {
  conversationId?: string | null;
  message: string;
  deep?: boolean;
  provider?: string | null;
  model?: string | null;
  onEvent: (e: ChatEvent) => void;
  onError?: (err: unknown) => void;
  signal?: AbortSignal;
};

export async function streamChat(opts: StreamChatOpts): Promise<void> {
  const { conversationId, message, deep, provider, model, onEvent, onError, signal } = opts;
  await fetchEventSource(apiUrl("/api/chat"), {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify({
      conversation_id: conversationId ?? null,
      message,
      deep: deep ?? false,
      provider: provider ?? null,
      model: model ?? null,
    }),
    signal,
    openWhenHidden: true,
    onmessage(ev) {
      try {
        const data = ev.data ? JSON.parse(ev.data) : null;
        onEvent({ event: ev.event, data } as ChatEvent);
      } catch (err) {
        onError?.(err);
      }
    },
    onerror(err) {
      onError?.(err);
      throw err;
    },
  });
}

export type ResultDoc = {
  ref: string;
  sql: string;
  columns: string[];
  rows: Record<string, any>[];
  metadata: { row_count?: number; time_range?: { start: string; end: string } };
};

export async function fetchResult(ref: string): Promise<ResultDoc> {
  const res = await fetch(apiUrl(`/api/results/${ref}`));
  if (!res.ok) throw new Error("fetchResult failed");
  return res.json();
}
