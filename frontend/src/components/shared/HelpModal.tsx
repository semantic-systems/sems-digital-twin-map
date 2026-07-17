import React, { useState } from 'react';
import { t, getLang } from '../../i18n';
import { HELP_CONTENT } from '../../content/helpContent';
import type { HelpBlock } from '../../content/helpContent';
import { startTour } from '../../tour/tour';

function Block({ block }: { block: HelpBlock }): React.ReactElement {
  if (block.type === 'p') {
    return <p style={{ margin: '0 0 8px', lineHeight: 1.6 }}>{block.text}</p>;
  }
  if (block.type === 'steps') {
    return (
      <ol style={{ margin: '0 0 8px', paddingLeft: 20, lineHeight: 1.6 }}>
        {block.items.map((item, i) => (
          <li key={i} style={{ marginBottom: 6 }}>{item}</li>
        ))}
      </ol>
    );
  }
  if (block.type === 'list') {
    return (
      <ul style={{ margin: '0 0 8px', paddingLeft: 20, lineHeight: 1.6 }}>
        {block.items.map((item, i) => (
          <li key={i} style={{ marginBottom: 6 }}>{item}</li>
        ))}
      </ul>
    );
  }
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', margin: '0 0 8px', fontSize: 13 }}>
      <tbody>
        {block.rows.map(([label, desc], i) => (
          <tr key={i} style={{ borderTop: '1px solid #f3f4f6' }}>
            <td style={{ padding: '6px 10px 6px 0', whiteSpace: 'nowrap', fontWeight: 600, color: '#111827', verticalAlign: 'top' }}>
              {label}
            </td>
            <td style={{ padding: '6px 0', color: '#374151', verticalAlign: 'top' }}>{desc}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function HelpButton(): React.ReactElement {
  const [open, setOpen] = useState(false);
  const sections = HELP_CONTENT[getLang()];

  return (
    <>
      <button
        data-tour="help-button"
        onClick={() => setOpen(true)}
        title={t('help_title')}
        aria-label={t('help')}
        style={{
          position: 'fixed',
          top: 10,
          right: 14,
          zIndex: 500,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          height: 26,
          padding: '0 11px 0 9px',
          borderRadius: 999,
          border: '1px solid #d1d5db',
          background: '#fff',
          color: '#374151',
          fontSize: 12,
          fontWeight: 600,
          cursor: 'pointer',
          fontFamily: "'Inter', system-ui, sans-serif",
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
        }}
      >
        <span
          aria-hidden="true"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: '#374151',
            color: '#fff',
            fontSize: 10,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          ?
        </span>
        {t('help')}
      </button>

      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9998,
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff',
              borderRadius: 12,
              width: 560,
              maxWidth: '92vw',
              maxHeight: '86vh',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 50px rgba(0,0,0,0.35)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 20px',
                borderBottom: '1px solid #e5e7eb',
                flexShrink: 0,
              }}
            >
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#111827', margin: 0 }}>
                {t('help')}
              </h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <button
                  onClick={() => {
                    setOpen(false);
                    void startTour();
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    border: '1px solid #bfdbfe',
                    background: '#eff6ff',
                    color: '#1d4ed8',
                    fontSize: 12,
                    fontWeight: 600,
                    borderRadius: 999,
                    padding: '5px 11px',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                  }}
                >
                  <span aria-hidden="true">🧭</span>
                  {t('take_tour')}
                </button>
                <button
                  onClick={() => setOpen(false)}
                  aria-label={t('close')}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    fontSize: 18,
                    lineHeight: 1,
                    color: '#6b7280',
                    cursor: 'pointer',
                    padding: 4,
                  }}
                >
                  ✕
                </button>
              </div>
            </div>

            <div style={{ overflowY: 'auto', padding: '16px 20px', fontSize: 13, color: '#374151' }}>
              {sections.map((section, i) => (
                <div key={i} style={{ marginBottom: i === sections.length - 1 ? 0 : 20 }}>
                  <h3 style={{ fontSize: 13, fontWeight: 700, color: '#111827', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span aria-hidden="true">{section.icon}</span>
                    {section.title}
                  </h3>
                  {section.blocks.map((block, j) => (
                    <Block key={j} block={block} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
