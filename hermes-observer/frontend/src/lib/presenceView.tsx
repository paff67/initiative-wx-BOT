import type { ReactNode } from 'react';

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'error' | 'info' | 'muted';

export function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ');
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className,
}: {
  title?: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('panel', className)}>
      {(title || eyebrow || action) && (
        <div className="panel-header">
          <div>
            {eyebrow && <div className="panel-eyebrow">{eyebrow}</div>}
            {title && <h3>{title}</h3>}
          </div>
          {action && <div className="panel-action">{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  icon,
  tone = 'neutral',
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  icon?: ReactNode;
  tone?: Tone;
}) {
  return (
    <div className={cn('metric-card', `tone-${tone}`)}>
      <div className="metric-top">
        <span>{label}</span>
        {icon && <span className="metric-icon">{icon}</span>}
      </div>
      <div className="metric-value">{value}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </div>
  );
}

export function Pill({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cn('pill', `tone-${tone}`)}>{children}</span>;
}

export function KeyValue({ label, value, mono = false }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="kv-row">
      <span>{label}</span>
      <strong className={mono ? 'mono' : undefined}>{value || '无'}</strong>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {description && <span>{description}</span>}
    </div>
  );
}

export function TextList({ items, empty }: { items?: unknown[]; empty: string }) {
  const list = (items || []).map((item) => toText(item)).filter(Boolean);
  if (!list.length) return <EmptyState title={empty} />;
  return (
    <ul className="text-list">
      {list.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

export function ConfidenceBar({ value }: { value?: number }) {
  const percent = Math.max(0, Math.min(100, Math.round((Number(value) || 0) * 100)));
  return (
    <div className="confidence">
      <div className="confidence-track">
        <span style={{ width: `${percent}%` }} />
      </div>
      <b>{percent}%</b>
    </div>
  );
}

export function actionTone(action?: string): Tone {
  if (action === 'send') return 'success';
  if (action === 'hesitate') return 'warning';
  if (action === 'silent') return 'muted';
  return 'neutral';
}

export function deliveryTone(status?: string, ok?: boolean): Tone {
  if (ok === true || status === 'success' || status === 'delivered') return 'success';
  if (status === 'silent' || status === 'dry-run') return 'muted';
  if (status === 'failed' || status === 'error') return 'error';
  return 'neutral';
}

export function actionLabel(action?: string) {
  const labels: Record<string, string> = { send: '发送', hesitate: '犹豫', silent: '沉默' };
  return labels[action || ''] || action || '未知';
}

export function classLabel(value?: string) {
  const labels: Record<string, string> = {
    none: '无',
    micro_send: '微消息',
    closure: '收口',
    random_share: '随机分享',
    care_timing: '关心时机',
    normal_send: '普通发送',
    media: '媒体',
  };
  return labels[value || ''] || value || '未分类';
}

export function modeLabel(dryRun?: boolean) {
  return dryRun ? 'dry-run' : '正式';
}

export function formatDateTime(value?: string | number | Date) {
  if (!value) return '无';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function shortId(value?: string, keep = 10) {
  if (!value) return '无';
  if (value.length <= keep + 4) return value;
  return `${value.slice(0, keep)}...${value.slice(-4)}`;
}

export function toText(value: unknown, fallback = '无'): string {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => toText(item, '')).filter(Boolean).join('、') || fallback;
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return toText(record.summary || record.normalized_fact || record.reason || record.name || record.id, fallback);
  }
  return fallback;
}

export function compactObject(value: unknown, maxLength = 160) {
  if (!value) return '无';
  if (typeof value === 'string') return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
  try {
    const text = JSON.stringify(value);
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
  } catch {
    return String(value);
  }
}

export function latestEvent<T = any>(data: any): T | undefined {
  return data?.events?.[0] as T | undefined;
}
