import { useInfiniteQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { useNotificationActions } from '../hooks/useNotificationActions';
import { getNotifications } from '../services/notifications';
import { formatRelativeTime } from '../utils/format';
import { describeNotification } from '../utils/notifications';

/**
 * Caixa de notificações (F-47, F-52): cada aviso mostra o texto montado a partir do tipo
 * (seção 5); o clique marca como lido e leva à tela relacionada (RN-67).
 */
export default function NotificationsPage() {
  const navigate = useNavigate();
  const { markRead, markAll } = useNotificationActions();
  const query = useInfiniteQuery({
    queryKey: ['notifications', 'list'],
    queryFn: ({ pageParam }) => getNotifications(pageParam),
    initialPageParam: null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });

  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  const hasUnread = items.some((item) => !item.read_at);
  const now = new Date();

  function open(notification, to) {
    if (!notification.read_at) markRead.mutate(notification.id);
    navigate(to);
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          Notificações
        </h1>
        {hasUnread && (
          <button
            type="button"
            onClick={() => markAll.mutate()}
            disabled={markAll.isPending}
            className="rounded-lg border border-flow/40 px-3 py-2 text-sm font-medium text-flow hover:bg-flow/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow disabled:opacity-60"
          >
            Marcar todos como lidos
          </button>
        )}
      </div>

      {markAll.isError && (
        <p role="alert" className="mt-4 text-sm text-red-300">
          Não foi possível marcar os avisos como lidos. {markAll.error.message}
        </p>
      )}

      <div className="mt-6">
        {query.isPending && <p className="text-slate-400">Carregando…</p>}
        {query.isError && !query.data && (
          <div
            role="alert"
            className="rounded-lg border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-200"
          >
            Não foi possível carregar os avisos. {query.error.message}{' '}
            <button
              type="button"
              onClick={() => query.refetch()}
              className="font-medium text-red-100 underline"
            >
              Tentar de novo
            </button>
          </div>
        )}
        {query.data && items.length === 0 && (
          <p className="text-slate-400">Nenhum aviso por enquanto.</p>
        )}
        {items.length > 0 && (
          <ul className="flex flex-col gap-2">
            {items.map((notification) => {
              const { text, to } = describeNotification(notification);
              const unread = !notification.read_at;
              return (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => open(notification, to)}
                    className={`flex w-full items-start gap-3 rounded-xl border p-4 text-left transition-colors hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                      unread ? 'border-accent/40 bg-panel' : 'border-line bg-transparent'
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-2 h-2 w-2 shrink-0 rounded-full ${unread ? 'bg-accent' : 'bg-transparent'}`}
                    />
                    <span className="min-w-0 flex-1">
                      <span className={`block ${unread ? 'text-white' : 'text-slate-300'}`}>
                        {unread && <span className="sr-only">Novo: </span>}
                        {text}
                      </span>
                      <time
                        dateTime={notification.created_at}
                        className="mt-1 block text-xs text-slate-400"
                      >
                        {formatRelativeTime(notification.created_at, now)}
                      </time>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {query.hasNextPage && (
          <button
            type="button"
            onClick={() => query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            className="mt-4 rounded-lg border border-line px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60"
          >
            {query.isFetchingNextPage ? 'Carregando…' : 'Carregar mais'}
          </button>
        )}
      </div>
    </div>
  );
}
