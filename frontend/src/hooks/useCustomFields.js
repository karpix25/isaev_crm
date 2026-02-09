import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
export function useCustomFields(activeOnly = false) {
    return useQuery({
        queryKey: ['custom-fields', activeOnly],
        queryFn: async () => {
            const { data } = await api.get(`/custom-fields?active_only=${activeOnly}`);
            return data;
        }
    });
}
