import { useEffect, useRef, useState } from "react";

type Props = {
  onSend: (text: string, opts: { deep: boolean }) => void;
  disabled?: boolean;
  placeholder?: string;
};

export default function ChatInput({ onSend, disabled, placeholder }: Props) {
  const [text, setText] = useState("");
  const [deep, setDeep] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (ref.current && !disabled) ref.current.focus();
  }, [disabled]);

  function send() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t, { deep });
    setText("");
    // Diep-modus is een eenmalige boost — automatisch uit na verzenden
    setDeep(false);
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="chat-input-wrap">
      <div className="chat-input">
        <textarea
          ref={ref}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          rows={3}
          placeholder={placeholder ?? "Stel een vraag over de data van je huis… (bv. 'vergelijk elektriciteitsproductie zomer 2024 met zomer 2023')"}
          disabled={disabled}
        />
        <button onClick={send} disabled={disabled || !text.trim()}>
          {disabled ? "…" : "Verstuur"}
        </button>
      </div>
      <div className="chat-input-options">
        <label
          className={`deep-toggle ${deep ? "on" : ""}`}
          title="Forceert maximale denktijd voor deze ene vraag — gebruik voor complexe vragen die meerdere measurements moeten combineren of waar Claude vaker fout gaat."
        >
          <input
            type="checkbox"
            checked={deep}
            onChange={(e) => setDeep(e.target.checked)}
            disabled={disabled}
          />
          <span>🧠 Diep nadenken (langzamer, grondiger)</span>
        </label>
      </div>
    </div>
  );
}
