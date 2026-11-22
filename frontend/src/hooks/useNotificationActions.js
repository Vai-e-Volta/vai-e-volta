import { useMutation, useQueryClient } from '@tanstack/react-query';
import { markAllNotificationsRead, markNotificationRead } from '../services/notifications';

/** Marcar avisos como lidos (F-52); o indicador do sino e a lista recarregam depois. */
export function useNotificationActions() {
  const queryClient = useQueryClient();
  const onSettled = () => queryClient.invalidateQueries({ queryKey: ['notifications'] });
  const markRead = useMutation({ mutationFn: markNotificationRead, onSettled });
  const markAll = useMutation({ mutationFn: markAllNotificationsRead, onSettled });
  return { markRead, markAll };
}
