import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteConversation,
  listConversations,
  type Conversation,
} from "../api/chat";

type Props = {
  activeId: string | null;
  onSelect: (id: string | null) => void;
};

export default function ConversationSidebar({ activeId, onSelect }: Props) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });
  const delMut = useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      if (activeId === id) onSelect(null);
    },
  });

  return (
    <aside className="convo-sidebar">
      <div className="convo-header">
        <span>Gesprekken</span>
        <button onClick={() => onSelect(null)} title="Nieuw gesprek">+ Nieuw</button>
      </div>
      {isLoading && <div className="muted">laden…</div>}
      {!isLoading && (data?.length ?? 0) === 0 && (
        <div className="muted convo-empty">Nog geen gesprekken. Stel een vraag om er een te starten.</div>
      )}
      <ul className="convo-list">
        {(data ?? []).map((c: Conversation) => (
          <li
            key={c.id}
            className={c.id === activeId ? "active" : ""}
            onClick={() => onSelect(c.id)}
          >
            <div className="convo-title">{c.title}</div>
            <div className="convo-meta">{new Date(c.updated_at).toLocaleString("nl-NL")}</div>
            <button
              className="convo-delete"
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(`Gesprek "${c.title}" verwijderen?`)) delMut.mutate(c.id);
              }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
