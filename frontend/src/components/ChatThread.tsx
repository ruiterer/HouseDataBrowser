import { useEffect, useRef } from "react";
import ChatMessage, { type LiveAssistantMessage } from "./ChatMessage";
import type { ConversationMessage } from "../api/chat";

type Props = {
  messages: ConversationMessage[];
  pendingUser: string | null;
  live: LiveAssistantMessage | null;
};

export default function ChatThread({ messages, pendingUser, live }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, pendingUser, live?.steps.length, live?.final, live?.errorMessage]);

  if (messages.length === 0 && !pendingUser && !live) {
    return (
      <div className="thread-empty">
        <h3>Stel een vraag over de data van je huis</h3>
        <ul>
          <li>"Wat was de gemiddelde binnentemperatuur in januari 2024?"</li>
          <li>"Vergelijk de elektriciteitsproductie van zomer 2024 met zomer 2023."</li>
          <li>"Hoe vaak is de voordeur afgelopen week geopend?"</li>
          <li>"Toon een heatmap van vochtigheid per uur en dag van de week voor afgelopen maand."</li>
        </ul>
      </div>
    );
  }

  return (
    <div className="thread">
      {messages.map((m) => (
        <ChatMessage key={m.id} msg={m} />
      ))}
      {pendingUser && <ChatMessage msg={{ role: "user", content: pendingUser }} />}
      {live && <ChatMessage msg={live} />}
      <div ref={endRef} />
    </div>
  );
}
