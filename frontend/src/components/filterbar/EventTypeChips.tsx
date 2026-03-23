import React from 'react';
import { t } from '../../i18n';
import { useFilterStore, ALL_EVENT_TYPES_LIST } from '../../store/useFilterStore';

interface EventTypeChipsProps {
  counts?: Record<string, number>;
}

export function EventTypeChips({ counts = {} }: EventTypeChipsProps): React.ReactElement {
  const { eventTypes, toggleEventType, soloEventType } = useFilterStore();

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'nowrap',
        gap: 3,
        alignItems: 'center',
      }}
    >
      {ALL_EVENT_TYPES_LIST.map((type) => {
        const active = eventTypes.includes(type);
        const count = counts[type];
        return (
          <button
            key={type}
            title={`${t(`et_${type}`)} — Shift+click to solo`}
            onClick={(e) => {
              if (e.shiftKey) {
                soloEventType(type);
              } else {
                toggleEventType(type);
              }
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              fontSize: 10,
              padding: '2px 6px',
              borderRadius: 999,
              border: active ? '1px solid #2563eb' : '1px solid #d1d5db',
              background: active ? '#2563eb' : 'transparent',
              color: active ? '#fff' : '#6b7280',
              cursor: 'pointer',
              fontFamily: "'Inter', system-ui, sans-serif",
              fontWeight: active ? 600 : 400,
              whiteSpace: 'nowrap',
              transition: 'all 0.1s',
              lineHeight: 1.4,
            }}
          >
            {t(`et_${type}`)}
            {count !== undefined && count > 0 && (
              <span
                style={{
                  background: active ? 'rgba(255,255,255,0.25)' : '#e5e7eb',
                  color: active ? '#fff' : '#374151',
                  borderRadius: 999,
                  padding: '0 4px',
                  fontSize: 9,
                  fontWeight: 700,
                  minWidth: 14,
                  textAlign: 'center',
                }}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
