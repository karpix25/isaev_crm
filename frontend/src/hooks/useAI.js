import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
export function useAI() {
    const queryClient = useQueryClient();
    const prompts = useQuery({
        queryKey: ['ai', 'prompts'],
        queryFn: async () => {
            const { data } = await api.get('/ai/prompts');
            return data;
        }
    });
    const activePrompt = useQuery({
        queryKey: ['ai', 'prompts', 'active'],
        queryFn: async () => {
            const { data } = await api.get('/ai/prompts/active');
            return data;
        }
    });
    const createPrompt = useMutation({
        mutationFn: async (newData) => {
            const { data } = await api.post('/ai/prompts', newData);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'prompts'] });
        }
    });
    const knowledge = useQuery({
        queryKey: ['ai', 'knowledge'],
        queryFn: async () => {
            const { data } = await api.get('/ai/knowledge');
            return data;
        }
    });
    const addKnowledge = useMutation({
        mutationFn: async (newData) => {
            const { data } = await api.post('/ai/knowledge', newData);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'knowledge'] });
        }
    });
    const deleteKnowledge = useMutation({
        mutationFn: async (itemId) => {
            await api.delete(`/ai/knowledge/${itemId}`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'knowledge'] });
        }
    });
    const uploadFile = useMutation({
        mutationFn: async ({ file, category }) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('category', category);
            const { data } = await api.post('/ai/knowledge/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['ai', 'knowledge'] });
        }
    });
    const searchKnowledge = useMutation({
        mutationFn: async (searchData) => {
            const { data } = await api.post('/ai/knowledge/search', searchData);
            return data;
        }
    });
    return {
        prompts,
        activePrompt,
        createPrompt,
        addKnowledge,
        searchKnowledge,
        uploadFile,
        deleteKnowledge,
        knowledge
    };
}
