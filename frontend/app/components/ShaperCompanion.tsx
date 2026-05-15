"use client";

import { useState, useRef, useEffect } from "react";
import styles from "./companion.module.css";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "companion" | "user";
  content: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ShaperCompanion() {
  const [isOpen, setIsOpen] = useState(false);
  const [hasOpened, setHasOpened] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "companion", content: "Greetings, Exile. The Atlas holds many secrets. What knowledge do you seek?" }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  const handleOpen = () => {
    setIsOpen(true);
    setHasOpened(true);
  };

  const handleClose = () => setIsOpen(false);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/companion/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, history: messages }),
      });

      if (!res.ok) throw new Error("Failed to get response");
      const data = await res.json();
      setMessages(prev => [...prev, { role: "companion", content: data.response }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "companion",
        content: "The Atlas grows dark... I cannot reach my knowledge at this moment. Try again, Exile."
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.companionRoot}>
      {/* Greeting bubble — only shows before first open */}
      {!hasOpened && (
        <div className={styles.greetingBubble} onClick={handleOpen}>
          <span>Greetings Exile, need assistance?</span>
          <div className={styles.greetingTail} />
        </div>
      )}

      {/* Chat panel */}
      {isOpen && (
        <div className={styles.chatPanel}>
          <div className={styles.chatHeader}>
            <div className={styles.chatHeaderLeft}>
              <div>
                <div className={styles.headerName}>The Shaper</div>
                <div className={styles.headerStatus}>● Awaiting..</div>
              </div>
            </div>
            <button className={styles.closeBtn} onClick={handleClose} aria-label="Close">✕</button>
          </div>

          <div className={styles.messages}>
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`${styles.message} ${msg.role === "companion" ? styles.messageCompanion : styles.messageUser}`}
              >
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
            ))}
            {loading && (
              <div className={`${styles.message} ${styles.messageCompanion} ${styles.messageLoading}`}>
                <span className={styles.dot} />
                <span className={styles.dot} />
                <span className={styles.dot} />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className={styles.inputRow}>
            <input
              className={styles.input}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask the Shaper..."
              disabled={loading}
            />
            <button
              className={styles.sendBtn}
              onClick={handleSend}
              disabled={loading || !input.trim()}
            >
              ⚡
            </button>
          </div>
        </div>
      )}

      {/* Floating avatar button */}
      <button
        className={`${styles.avatarBtn} ${isOpen ? styles.avatarBtnOpen : ""}`}
        onClick={isOpen ? handleClose : handleOpen}
        aria-label="Toggle Shaper companion"
      >
        <img
          src="/images/companions/shaper.jpg"
          alt="Shaper"
          className={styles.avatarImg}
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
        <div className={styles.avatarFallback}>📖</div>
      </button>
    </div>
  );
}
