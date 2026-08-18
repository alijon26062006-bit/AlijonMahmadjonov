/** Избранное: список id и мгновенное переключение.

    Сердечко закрашивается сразу, запрос уходит следом. Сервер отказал —
    возвращаем как было: человек не должен гадать, сохранилось или нет.
*/
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { api } from '../api/client';

export function useFavorites(enabled: boolean) {
  const qc = useQueryClient();
  const { data } = useQuery<{ ids: string[] }>({
    queryKey: ['fav-ids'], queryFn: () => api('/api/favorites/ids'),
    enabled, staleTime: 60_000,
  });
  const ids = new Set(data?.ids ?? []);

  const toggle = useCallback(async (id: string, next: boolean) => {
    qc.setQueryData<{ ids: string[] }>(['fav-ids'], (prev) => {
      const list = new Set(prev?.ids ?? []);
      if (next) list.add(id); else list.delete(id);
      return { ids: [...list] };
    });
    try {
      await api(`/api/favorites/${id}`, { method: next ? 'PUT' : 'DELETE' });
      qc.invalidateQueries({ queryKey: ['favorites'] });
    } catch {
      qc.invalidateQueries({ queryKey: ['fav-ids'] });
    }
  }, [qc]);

  return { ids, toggle };
}
