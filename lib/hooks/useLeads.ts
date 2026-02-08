import useSWR from 'swr';

const fetcher = (url: string) =>
    fetch(url, {
        headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
    }).then((res) => res.json());

export function useLeads(status?: string) {
    const url = status ? `/api/leads?status=${status}` : '/api/leads';

    const { data, error, mutate } = useSWR(url, fetcher, {
        refreshInterval: 10000, // Poll every 10 seconds
        revalidateOnFocus: true,
    });

    return {
        leads: data || [],
        isLoading: !error && !data,
        isError: error,
        mutate,
    };
}
