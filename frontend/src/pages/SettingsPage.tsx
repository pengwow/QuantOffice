/**
 * SettingsPage — 系统设置（LLM / Exchange / Risk）
 *
 * 设计要点：
 *  - 三个折叠面板（LLM、Exchange、Risk），独立保存
 *  - LLM/Exchange 切换 provider/venue 时自动填默认 base_url / model
 *  - 输入框支持显示"已设置"标记，api_key 始终脱敏
 *  - 提供「联通测试」按钮，实时调用第三方 API 验证 key 是否有效
 */

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import styles from './Pages.module.css';

type LlmPreset = { key: string; label: string; base_url: string; default_model: string };
type ExchangePreset = { key: string; label: string; base_url: string; testnet_base_url: string };

export function SettingsPage() {
  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>⚙ 系统设置</div>
        <div className={styles.pageSubtitle}>配置 LLM 提供商 · 交易所凭证 · 风控阈值（热生效）</div>
      </div>
      <LlmPanel />
      <ExchangePanel />
      <RiskPanel />
    </div>
  );
}

// ============================================================
// LLM
// ============================================================
function LlmPanel() {
  const qc = useQueryClient();
  const presets = useQuery({ queryKey: ['llm-presets'], queryFn: api.listLlmPresets });
  const llm = useQuery({ queryKey: ['llm'], queryFn: api.getLlm, refetchInterval: 0 });

  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [apiKeyInput, setApiKeyInput] = useState('');

  useEffect(() => {
    if (llm.data) {
      setDraft(llm.data);
      setApiKeyInput(''); // 不预填（避免误覆盖）
    }
  }, [llm.data]);

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { ...draft };
      if (apiKeyInput) body.api_key = apiKeyInput;
      return api.updateLlm(body);
    },
    onSuccess: (data) => {
      qc.setQueryData(['llm'], data);
      qc.invalidateQueries({ queryKey: ['chat-status'] });
      setApiKeyInput('');
      alert('LLM 配置已保存');
    },
    onError: (err: Error) => alert(`保存失败: ${err.message}`),
  });

  const test = useMutation({
    mutationFn: api.testLlm,
    onSuccess: (data) => {
      if (data.ok) {
        alert(`✅ 联通成功 (${data.elapsed_ms}ms)\n模型: ${data.model ?? '-'}`);
      } else {
        alert(`❌ 联通失败: ${data.error ?? '未知错误'}`);
      }
    },
  });

  const handleProviderChange = (providerKey: string) => {
    const preset = presets.data?.find((p) => p.key === providerKey);
    setDraft({
      ...draft,
      provider: providerKey,
      base_url: preset?.base_url ?? '',
      model: preset?.default_model ?? '',
    });
  };

  return (
    <Panel title="🧠 LLM 提供商" desc="OpenAI 兼容协议 · 支持 DeepSeek / OpenAI / 通义千问 / Ollama / 自定义">
      <Row label="启用">
        <input
          type="checkbox"
          checked={Boolean(draft.enabled)}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
        <Hint>关闭后所有 LLM 调用自动降级到规则化建议</Hint>
      </Row>

      <Row label="Provider">
        <select value={String(draft.provider ?? '')} onChange={(e) => handleProviderChange(e.target.value)}>
          {(presets.data ?? []).map((p: LlmPreset) => (
            <option key={p.key} value={p.key}>{p.label}</option>
          ))}
        </select>
      </Row>

      <Row label="Base URL">
        <input
          type="text"
          value={String(draft.base_url ?? '')}
          onChange={(e) => setDraft({ ...draft, base_url: e.target.value })}
          placeholder="https://api.deepseek.com/v1"
        />
      </Row>

      <Row label="Model">
        <input
          type="text"
          value={String(draft.model ?? '')}
          onChange={(e) => setDraft({ ...draft, model: e.target.value })}
          placeholder="deepseek-chat"
        />
      </Row>

      <Row label="API Key">
        <input
          type="password"
          value={apiKeyInput}
          onChange={(e) => setApiKeyInput(e.target.value)}
          placeholder={draft.api_key_set ? '已设置（输入新值覆盖，留空保留）' : 'sk-...'}
        />
        {Boolean(draft.api_key_set) && (
          <Hint>当前: {String(draft.api_key)}</Hint>
        )}
      </Row>

      <Row label="Temperature">
        <input
          type="number"
          step="0.1"
          min={0}
          max={2}
          value={Number(draft.temperature ?? 0.3)}
          onChange={(e) => setDraft({ ...draft, temperature: parseFloat(e.target.value) })}
        />
        <Hint>0 = 精确，1 = 平衡，2 = 创造性</Hint>
      </Row>

      <Row label="Max Tokens">
        <input
          type="number"
          min={1}
          max={32768}
          value={Number(draft.max_tokens ?? 1024)}
          onChange={(e) => setDraft({ ...draft, max_tokens: parseInt(e.target.value, 10) })}
        />
      </Row>

      <Row label="Timeout (s)">
        <input
          type="number"
          min={1}
          max={300}
          value={Number(draft.timeout_sec ?? 30)}
          onChange={(e) => setDraft({ ...draft, timeout_sec: parseInt(e.target.value, 10) })}
        />
      </Row>

      <ButtonRow>
        <button
          className={styles.btnPrimary}
          onClick={() => save.mutate()}
          disabled={save.isPending}
        >
          {save.isPending ? '保存中…' : '保存'}
        </button>
        <button
          className={styles.btnSecondary}
          onClick={() => test.mutate()}
          disabled={test.isPending || !draft.enabled}
        >
          {test.isPending ? '测试中…' : '🔌 联通测试'}
        </button>
      </ButtonRow>
    </Panel>
  );
}

// ============================================================
// Exchange
// ============================================================
function ExchangePanel() {
  const qc = useQueryClient();
  const presets = useQuery({ queryKey: ['exchange-presets'], queryFn: api.listExchangePresets });
  const ex = useQuery({ queryKey: ['exchange'], queryFn: api.getExchange, refetchInterval: 0 });

  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [apiSecretInput, setApiSecretInput] = useState('');

  useEffect(() => {
    if (ex.data) {
      setDraft(ex.data);
      setApiKeyInput('');
      setApiSecretInput('');
    }
  }, [ex.data]);

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { ...draft };
      if (apiKeyInput) body.api_key = apiKeyInput;
      if (apiSecretInput) body.api_secret = apiSecretInput;
      return api.updateExchange(body);
    },
    onSuccess: (data) => {
      qc.setQueryData(['exchange'], data);
      setApiKeyInput('');
      setApiSecretInput('');
      alert('Exchange 配置已保存');
    },
    onError: (err: Error) => alert(`保存失败: ${err.message}`),
  });

  const test = useMutation({
    mutationFn: api.testExchange,
    onSuccess: (data) => {
      if (data.ok) {
        alert(`✅ 联通成功\nbase_url: ${data.base_url}\nBTC 价: ${data.btc_price}`);
      } else {
        alert(`❌ 联通失败: ${data.error ?? '未知错误'}`);
      }
    },
  });

  return (
    <Panel title="🏦 交易所" desc="Binance / OKX / Bybit（testnet 可不填 key）">
      <Row label="启用">
        <input
          type="checkbox"
          checked={Boolean(draft.enabled)}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
        <Hint>关闭后所有下单/账户接口报错</Hint>
      </Row>

      <Row label="Venue">
        <select
          value={String(draft.venue ?? 'binance')}
          onChange={(e) => setDraft({ ...draft, venue: e.target.value })}
        >
          {(presets.data ?? []).map((p: ExchangePreset) => (
            <option key={p.key} value={p.key}>{p.label}</option>
          ))}
        </select>
      </Row>

      <Row label="Testnet">
        <input
          type="checkbox"
          checked={Boolean(draft.testnet)}
          onChange={(e) => setDraft({ ...draft, testnet: e.target.checked })}
        />
        <Hint>勾选后使用测试网（不消耗真实资金）</Hint>
      </Row>

      <Row label="API Key">
        <input
          type="password"
          value={apiKeyInput}
          onChange={(e) => setApiKeyInput(e.target.value)}
          placeholder={draft.api_key_set ? '已设置（输入新值覆盖）' : '留空使用公共行情'}
        />
        {Boolean(draft.api_key_set) && <Hint>当前: {String(draft.api_key)}</Hint>}
      </Row>

      <Row label="API Secret">
        <input
          type="password"
          value={apiSecretInput}
          onChange={(e) => setApiSecretInput(e.target.value)}
          placeholder={draft.api_secret_set ? '已设置（输入新值覆盖）' : '留空表示只读'}
        />
        {Boolean(draft.api_secret_set) && <Hint>当前: {String(draft.api_secret)}</Hint>}
      </Row>

      <Row label="Timeout (s)">
        <input
          type="number"
          min={1}
          max={60}
          value={Number(draft.timeout_sec ?? 10)}
          onChange={(e) => setDraft({ ...draft, timeout_sec: parseInt(e.target.value, 10) })}
        />
      </Row>

      <ButtonRow>
        <button className={styles.btnPrimary} onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? '保存中…' : '保存'}
        </button>
        <button className={styles.btnSecondary} onClick={() => test.mutate()} disabled={test.isPending}>
          {test.isPending ? '测试中…' : '🔌 联通测试'}
        </button>
      </ButtonRow>
    </Panel>
  );
}

// ============================================================
// Risk
// ============================================================
function RiskPanel() {
  const qc = useQueryClient();
  const risk = useQuery({ queryKey: ['risk'], queryFn: api.getRisk, refetchInterval: 0 });

  const [draft, setDraft] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (risk.data) setDraft(risk.data);
  }, [risk.data]);

  const save = useMutation({
    mutationFn: () => api.updateRisk(draft),
    onSuccess: (data) => {
      qc.setQueryData(['risk'], data);
      alert('风控配置已保存');
    },
    onError: (err: Error) => alert(`保存失败: ${err.message}`),
  });

  return (
    <Panel title="🛡 风控阈值" desc="运行时覆盖默认风控参数（仅在 demo/小盘 实盘下生效）">
      <Row label="最大回撤 (0-1)">
        <input
          type="number"
          step="0.01"
          min={0}
          max={1}
          value={Number(draft.max_drawdown ?? 0.05)}
          onChange={(e) => setDraft({ ...draft, max_drawdown: parseFloat(e.target.value) })}
        />
        <Hint>如 0.05 = 5%</Hint>
      </Row>

      <Row label="告警回撤 (0-1)">
        <input
          type="number"
          step="0.01"
          min={0}
          max={1}
          value={Number(draft.warning_drawdown ?? 0.03)}
          onChange={(e) => setDraft({ ...draft, warning_drawdown: parseFloat(e.target.value) })}
        />
      </Row>

      <Row label="最大仓位 (0-10)">
        <input
          type="number"
          step="0.1"
          min={0}
          max={10}
          value={Number(draft.max_position_ratio ?? 1.0)}
          onChange={(e) => setDraft({ ...draft, max_position_ratio: parseFloat(e.target.value) })}
        />
        <Hint>1.0 = 100% 资金</Hint>
      </Row>

      <Row label="熔断触发次数">
        <input
          type="number"
          min={1}
          max={1000}
          value={Number(draft.circuit_breaker_threshold ?? 5)}
          onChange={(e) => setDraft({ ...draft, circuit_breaker_threshold: parseInt(e.target.value, 10) })}
        />
        <Hint>连续 N 次触发告警后熔断</Hint>
      </Row>

      <ButtonRow>
        <button className={styles.btnPrimary} onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? '保存中…' : '保存'}
        </button>
      </ButtonRow>
    </Panel>
  );
}

// ============================================================
// 通用小组件
// ============================================================
function Panel({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <div className={styles.settingsPanel}>
      <div className={styles.settingsPanelHead}>
        <div className={styles.settingsPanelTitle}>{title}</div>
        <div className={styles.settingsPanelDesc}>{desc}</div>
      </div>
      <div className={styles.settingsPanelBody}>{children}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.settingsRow}>
      <label className={styles.settingsLabel}>{label}</label>
      <div className={styles.settingsControl}>{children}</div>
    </div>
  );
}

function ButtonRow({ children }: { children: React.ReactNode }) {
  return <div className={styles.settingsActions}>{children}</div>;
}

function Hint({ children }: { children: React.ReactNode }) {
  return <span className={styles.settingsHint}>{children}</span>;
}
