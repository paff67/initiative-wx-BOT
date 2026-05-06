import { useQuery } from '@tanstack/react-query';
import { Paperclip, Send } from 'lucide-react';
import { fetchPresenceEvents } from '../api/client';
import { EmptyState, KeyValue, PageHeader, Panel, Pill, classLabel, deliveryTone, formatDateTime, shortId } from '../lib/presenceView';

export default function Delivery({ profileId }: { profileId: string }) {
  const { data } = useQuery({ queryKey: ['presence-delivery', profileId], queryFn: () => fetchPresenceEvents(profileId, 'delivery', 80), refetchInterval: 10000, enabled: Boolean(profileId) });
  const events = data?.events || [];

  return (
    <div className="stack">
      <PageHeader
        title="投递记录"
        description="展示最终进入 Weixin 通道的文本、附件候选、fallback 和投递状态。静默与 dry-run 不会在这里冒充真实发送。"
      />

      {events.length === 0 ? (
        <Panel>
          <EmptyState title="暂无投递记录" description="有 render 被允许投递后，会写入 delivery-events.jsonl 并显示在这里。" />
        </Panel>
      ) : (
        events.map((event: any) => {
          const render = event.render || {};
          const speech = render.speech || {};
          const status = event.status || event.result || (render.would_deliver ? 'success' : render.type || 'silent');
          return (
            <Panel
              key={event.delivery_event_id || event.run_id}
              title={shortId(event.delivery_event_id || event.run_id, 24)}
              eyebrow={formatDateTime(event.created_at)}
              action={
                <div className="inline-row">
                  <Pill tone={deliveryTone(status, render.would_deliver)}>{status}</Pill>
                  <Pill tone="neutral">{classLabel(event.message_class)}</Pill>
                </div>
              }
            >
              <div className="split-grid">
                <div className={`message-bubble ${render.type === 'silent' ? 'is-silent' : ''}`}>
                  {render.type === 'text' ? render.text : '[SILENT]'}
                </div>
                <div className="kv-stack">
                  <KeyValue label="Render Run" value={shortId(event.render_run_id || render.render_run_id, 18)} mono />
                  <KeyValue label="通道" value={render.channel || 'weixin'} />
                  <KeyValue label="投递指令" value={render.delivery_instruction || '无'} />
                  <KeyValue label="Fallback" value={render.fallback?.type || '无'} />
                  <KeyValue
                    label="语音附件"
                    value={
                      <span className="inline-row">
                        <Pill tone={speech.enabled ? 'accent' : 'muted'}>{speech.enabled ? '启用' : '关闭'}</Pill>
                        {speech.enabled && <Pill tone="neutral"><Paperclip size={13} /> {speech.audio_format || speech.response_format || 'mp3'}</Pill>}
                      </span>
                    }
                  />
                </div>
              </div>

              {speech.voice_design?.prompt && (
                <div className="detail-band mt-4">
                  <div className="inline-row">
                    <Send size={15} />
                    <strong>语音设计</strong>
                    <Pill tone={speech.voice_design.enabled ? 'accent' : 'muted'}>{speech.voice_design.delivery_mode || 'text_only'}</Pill>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--color-muted)]">{speech.voice_design.prompt}</p>
                </div>
              )}
            </Panel>
          );
        })
      )}
    </div>
  );
}
