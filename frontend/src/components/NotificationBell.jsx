import { useQuery } from '@tanstack/react-query';
import { NavLink } from 'react-router';
import { getUnreadCount } from '../services/notifications';

// O indicador consulta o unread-count de tempos em tempos (H022-3), e também quando a
// pessoa volta para a aba.
const POLL_MS = 30_000;

function BellIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none">
      <path
        d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16Z M10 20a2 2 0 0 0 4 0"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Sino do cabeçalho com o indicador de avisos novos (F-46, RN-68). Leva a /notificacoes. */
export default function NotificationBell() {
  const { data: count = 0 } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: getUnreadCount,
    refetchInterval: POLL_MS,
    refetchOnWindowFocus: true,
  });

  const label =
    count === 0 ? 'Notificações' : `Notificações, ${count} ${count === 1 ? 'nova' : 'novas'}`;

  return (
    <NavLink
      to="/notificacoes"
      aria-label={label}
      className={({ isActive }) =>
        `relative flex h-10 w-10 items-center justify-center rounded-full border bg-panel transition-colors hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface ${
          isActive ? 'border-accent text-accent' : 'border-line text-slate-200'
        }`
      }
    >
      <BellIcon />
      {count > 0 && (
        <span
          aria-hidden="true"
          className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-[11px] font-bold text-ink ring-2 ring-surface"
        >
          {count > 9 ? '9+' : count}
        </span>
      )}
    </NavLink>
  );
}
