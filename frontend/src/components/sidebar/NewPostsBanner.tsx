import React from 'react';
import { newPostsLabel } from '../../i18n';
import { useReportStore } from '../../store/useReportStore';
import { useUserStore } from '../../store/useUserStore';
import { admitAllReports } from '../../api/reports';
import { invalidateBundle } from '../../queryClient';

export function NewPostsBanner(): React.ReactElement {
  const { pendingNewCount } = useReportStore();
  const { username } = useUserStore();

  const handleClick = async () => {
    if (!username || pendingNewCount === 0) return;

    try {
      // Admission is a watermark, not filter-scoped (see backend UserAdmission)
      // — advancing it then invalidating the bundle query is now the whole
      // flow; the bundle refetch brings reports, dots, and every panel count
      // back in sync in one round trip.
      await admitAllReports();
      invalidateBundle();
    } catch (e) {
      console.error('Failed to admit reports:', e);
    }
  };

  const active = pendingNewCount > 0;

  return (
    <button
      onClick={handleClick}
      disabled={!active}
      style={{
        width: '100%',
        padding: '7px 12px',
        background: active ? '#2563eb' : '#1e2235',
        color: active ? '#fff' : '#4b5563',
        border: 'none',
        borderBottom: '1px solid #252836',
        cursor: active ? 'pointer' : 'default',
        fontSize: 12,
        fontWeight: active ? 600 : 400,
        fontFamily: "'Inter', system-ui, sans-serif",
        textAlign: 'center',
        transition: 'background 0.15s',
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        if (active)
          (e.currentTarget as HTMLButtonElement).style.background = '#1d4ed8';
      }}
      onMouseLeave={(e) => {
        if (active)
          (e.currentTarget as HTMLButtonElement).style.background = '#2563eb';
      }}
    >
      {newPostsLabel(pendingNewCount)}
    </button>
  );
}
