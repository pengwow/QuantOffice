/**
 * ChatPage — 与 LLM 对话（SSE 流式输出）
 *
 * 设计：
 *  - 直接消费 /api/chat/stream（SSE）
 *  - LLM 未启用时显示空状态 + 引导跳转到 /settings
 *  - 提供 4 个 quick action 示例
 */

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/api/client';
import styles from './Pages.module.css';

type Role = 'user' | 'assistant' | 'system';

interface Message {
  role: Role;
  content: string;
  ts: number;
  meta?: string;
}

const QUICK_ACTIONS = [
  { label: '📊 分析当前回测', prompt: '请帮我分析当前正在运行的策略回测结果，指出风险点。' },
  { label: '🔍 解读市场',     prompt: '请用 1 段话解读当前 BTC 市场行情。' },
  { label: '🛡 给出风控建议', prompt: '请给出针对中小资金量化账户的 3 条风控建议。' },
  { label: '💡 写一个均线策略', prompt: '请用 Python 写一个 5/20 SMA 均线交叉策略示例。' },
];

const API_BASE = (() => {
  const PLUGIN = import.meta.env.VITE_PLUGIN_MODE === 'quantcell';
  return import.meta.env.VITE_API_BASE ?? (PLUGIN ? '/api/plugins/quant-office' : '/api');
})();

export function ChatPage() {
  const status = useQuery({
    queryKey: ['chat-status'],
    queryFn: api.chatStatus,
    refetchInterval: 5_000,
  });

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, messages[messages.length - 1]?.content]);

  const send = async (text: string) => {
    if (!text.trim() || streaming) return;
    const userMsg: Message = { role: 'user', content: text, ts: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setStreaming(true);

    const assistantMsg: Message = { role: 'assistant', content: '', ts: Date.now() };
    setMessages((prev) => [...prev, assistantMsg]);

    let accumulated = '';
    const startedAt = Date.now();

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, max_tokens: 1024 }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new ApiError(res.status, null, errText);
      }

      if (!res.body) {
        throw new Error('浏览器不支持流式响应');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let done = false;
      let errorMsg: string | null = null;

      while (!done) {
        const { value, done: rdone } = await reader.read();
        done = rdone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            const payload = line.slice(5).trim();
            if (payload === '[DONE]') { done = true; break; }
            try {
              const obj = JSON.parse(payload);
              if (obj.type === 'delta' && obj.text) {
                accumulated += obj.text;
                setMessages((prev) => {
                  const next = [...prev];
                  next[next.length - 1] = {
                    ...assistantMsg,
                    content: accumulated,
                    ts: Date.now(),
                  };
                  return next;
                });
              } else if (obj.type === 'error') {
                errorMsg = obj.message;
              }
            } catch {
              /* 忽略解析失败 */
            }
          }
        }
      }

      const elapsed = Date.now() - startedAt;
      if (errorMsg) {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            ...assistantMsg,
            content: accumulated || `❌ ${errorMsg}`,
            meta: `${elapsed}ms · error`,
          };
          return next;
        });
      } else {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            ...assistantMsg,
            meta: `${elapsed}ms · ${status.data?.model ?? 'LLM'}`,
          };
          return next;
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          ...assistantMsg,
          content: `❌ 请求失败: ${msg}\n\n请到「系统设置 → LLM」检查 API key 是否正确。`,
        };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const configured = Boolean(status.data?.configured);

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>💬 AI 对话</div>
        <div className={styles.pageSubtitle}>
          {configured
            ? `已连接 · ${String(status.data?.provider ?? '')} · ${String(status.data?.model ?? '')}`
            : 'LLM 未启用 · 请到「系统设置」页配置 API key'}
        </div>
      </div>

      <div className={styles.chatContainer}>
        <div className={styles.chatHeader}>
          <div className={styles.chatHeaderTitle}>QUANT COPILOT</div>
          <div className={styles.chatHeaderStatus}>
            {configured ? '🟢 LLM 已就绪' : '🔴 LLM 未启用'}
          </div>
        </div>

        <div className={styles.chatMessages}>
          {messages.length === 0 && (
            <div className={styles.chatEmpty}>
              {configured
                ? '👋 您好，我是 Quant Copilot。可以问我策略、回测、风控或代码问题。'
                : '⚠ LLM 未启用，请先到「系统设置 → LLM」配置 provider 与 API key。'}
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`${styles.chatBubble} ${styles[m.role]}`}>
              {m.content || (m.role === 'assistant' && streaming ? '▌' : '')}
              {m.meta && <div className={styles.chatBubbleMeta}>{m.meta}</div>}
            </div>
          ))}
          <div ref={messagesEnd} />
        </div>

        {configured && (
          <div className={styles.chatQuickActions}>
            {QUICK_ACTIONS.map((q) => (
              <button
                key={q.label}
                className={styles.chatQuickBtn}
                onClick={() => send(q.prompt)}
                disabled={streaming}
              >
                {q.label}
              </button>
            ))}
          </div>
        )}

        <div className={styles.chatInputBar}>
          <textarea
            className={styles.chatInput}
            placeholder={configured ? '输入消息，Enter 发送，Shift+Enter 换行' : 'LLM 未启用，无法发送'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={!configured || streaming}
            rows={1}
          />
          <button
            className={styles.chatSend}
            onClick={() => send(input)}
            disabled={!configured || streaming || !input.trim()}
          >
            {streaming ? '…' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
