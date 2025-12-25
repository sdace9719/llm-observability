import { useEffect, useRef, useState } from 'react';
import './App.css';

const initialMessages = [
  {
    id: 'welcome',
    sender: 'bot',
    text: 'Hi there! I am Clara, your virtual success partner. Ask me anything about your account, billing, or product features.',
    timestamp: new Date().toISOString()
  },
  {
    id: 'help',
    sender: 'bot',
    text: 'You can also pick a quick action below to get started faster.',
    timestamp: new Date().toISOString()
  }
];

const pastelBadges = [
  { label: 'Avg. reply', value: 'under 2 min', tone: 'soft-blue' },
  { label: 'CSAT', value: '4.8 / 5', tone: 'soft-green' },
  { label: 'Live agents', value: 'online', tone: 'soft-orange' }
];

const quickActions = [
  { id: 'order-status', label: 'Track my order', prompt: 'Where is my order right now?' },
  { id: 'billing', label: 'Billing question', prompt: 'I have a billing issue.' },
  { id: 'meeting', label: 'Talk to an agent', prompt: 'I need to speak with a human agent.' },
  { id: 'features', label: 'Product features', prompt: 'What can your product do?' }
];

const topicCards = [
  {
    id: 'shipping',
    label: 'Shipping updates',
    confidence: 82,
    prompt: 'Can you update me on the latest shipping timelines?'
  },
  {
    id: 'pricing',
    label: 'Plan recommendations',
    confidence: 74,
    prompt: 'Which pricing plan is best for a fast-growing team?'
  },
  {
    id: 'agents',
    label: 'Talk to a human',
    confidence: 68,
    prompt: 'Please connect me to a live support agent.'
  },
  {
    id: 'integrations',
    label: 'Integrations library',
    confidence: 63,
    prompt: 'What integrations are available out of the box?'
  }
];

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

export default function App() {
  const [messages, setMessages] = useState(initialMessages);
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loginState, setLoginState] = useState({ user: '', accessCode: '', error: '', pending: false });
  const scrollAnchorRef = useRef(null);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!inputValue.trim() || isThinking) {
      return;
    }
    handleSend(inputValue.trim());
  };

  const handleSend = async (text) => {
    const trimmed = text.slice(0, 500);
    const userMessage = {
      id: createId('user'),
      sender: 'user',
      text: trimmed,
      timestamp: new Date().toISOString()
    };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsThinking(true);

    try {
      const reply = await fetchBotReply(trimmed);
      const botMessage = {
        id: createId('bot'),
        sender: 'bot',
        text: reply,
        timestamp: new Date().toISOString()
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      const fallback = {
        id: createId('bot'),
        sender: 'bot',
        text:
          error instanceof Error
            ? `Something went wrong: ${error.message}`
            : 'Our support assistant is offline. Please try again shortly.',
        timestamp: new Date().toISOString()
      };
      setMessages((prev) => [...prev, fallback]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    const user = loginState.user.trim();
    const accessCode = loginState.accessCode.trim();
    if (!user || !accessCode || loginState.pending) return;
    setLoginState((prev) => ({ ...prev, pending: true, error: '' }));

    try {
      const response = await fetch(`${API_BASE_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: user, access_code: accessCode })
      });
      if (!response.ok) {
        const detail = await safeParseJson(response);
        throw new Error(detail?.error ?? 'Login failed');
      }
      await response.json();
      setIsLoggedIn(true);
    } catch (error) {
      setLoginState((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Login failed'
      }));
    } finally {
      setLoginState((prev) => ({ ...prev, pending: false }));
    }
  };

  return (
    <div className="app-shell">
      {!isLoggedIn ? (
        <LoginCard
          value={loginState.user}
          accessCode={loginState.accessCode}
          error={loginState.error}
          pending={loginState.pending}
          onChange={(value) => setLoginState((prev) => ({ ...prev, user: value }))}
          onAccessCodeChange={(value) => setLoginState((prev) => ({ ...prev, accessCode: value }))}
          onSubmit={handleLogin}
        />
      ) : (
      <div className="chat-card">
        <header className="chat-header">
          <div className="avatar">
            <img src="/support-bot.svg" alt="Support bot" />
            <span className="presence-dot" aria-hidden />
          </div>
          <div>
            <p className="title">Clara • Customer Care</p>
            <p className="subtitle">We'll keep the conversation light and helpful.</p>
          </div>
          <button className="outline-btn" type="button">
            View history
          </button>
        </header>

        <section className="status-pills">
          {pastelBadges.map((badge) => (
            <article key={badge.label} className={`pill ${badge.tone}`}>
              <p className="pill-label">{badge.label}</p>
              <p className="pill-value">{badge.value}</p>
            </article>
          ))}
        </section>

        <section className="topic-grid">
          {topicCards.map((topic) => (
            <button
              key={topic.id}
              className="topic-card"
              type="button"
              onClick={() => handleSend(topic.prompt)}
            >
              <span className="topic-label">{topic.label}</span>
              <span className="topic-confidence">{topic.confidence}% match</span>
              <p>{topic.prompt}</p>
            </button>
          ))}
        </section>

        <section className="messages" aria-live="polite">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {isThinking && <TypingBubble />}
          <div ref={scrollAnchorRef} />
        </section>

        <SuggestionTray onSelect={handleSend} suggestions={quickActions} />

        <form className="chat-input" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Type your question…"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            aria-label="Chat message"
          />
          <button type="submit" disabled={!inputValue.trim() || isThinking}>
            Send
          </button>
        </form>
      </div>
      )}
    </div>
  );
}

function MessageBubble({ message }) {
  const isBot = message.sender === 'bot';
  return (
    <div className={`bubble-row ${isBot ? 'bot' : 'user'}`}>
      {isBot && <span className="bubble-chip">Clara</span>}
      <div className="bubble">
        <p>{message.text}</p>
        <span>{formatTime(message.timestamp)}</span>
      </div>
      {!isBot && <span className="bubble-chip">You</span>}
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="bubble-row bot">
      <span className="bubble-chip">Clara</span>
      <div className="bubble typing">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function SuggestionTray({ suggestions, onSelect }) {
  return (
    <div className="suggestion-tray">
      {suggestions.map((item) => (
        <button key={item.id} type="button" onClick={() => onSelect(item.prompt)}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

async function fetchBotReply(prompt) {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify({ prompt })
  });

  if (!response.ok) {
    const detail = await safeParseJson(response);
    throw new Error(detail?.error ?? 'Unable to reach support assistant');
  }

  const payload = await response.json();
  return payload.reply ?? 'Thanks! An agent will follow up shortly.';
}

function formatTime(value) {
  try {
    return new Intl.DateTimeFormat('en', {
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(value));
  } catch {
    return '';
  }
}

function createId(prefix) {
  const random =
    globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
  return `${prefix}-${random}`;
}

async function safeParseJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
function LoginCard({ value, accessCode, onChange, onAccessCodeChange, onSubmit, error, pending }) {
  return (
    <div className="chat-card login-card">
      <header className="chat-header">
        <div className="avatar">
          <img src="/support-bot.svg" alt="Support bot" />
          <span className="presence-dot" aria-hidden />
        </div>
        <div>
          <p className="title">Clara • Customer Care</p>
          <p className="subtitle">Sign in to continue to chat.</p>
        </div>
      </header>

      <form className="chat-input" onSubmit={onSubmit}>
        <input
          type="email"
          placeholder="Enter your email to start"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-label="Email"
          required
        />
        <input
          type="password"
          placeholder="Enter access code"
          value={accessCode}
          onChange={(event) => onAccessCodeChange(event.target.value)}
          aria-label="Access code"
          required
        />
        <button type="submit" disabled={!value.trim() || pending}>
          {pending ? 'Signing in…' : 'Continue'}
        </button>
      </form>

      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

