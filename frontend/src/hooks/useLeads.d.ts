import type { Lead, LeadStatus } from '@/types';
export declare function useLeads(params?: {
    status?: LeadStatus;
    source?: string;
    search?: string;
}): import("@tanstack/react-query").UseQueryResult<{
    leads: Lead[];
    total: number;
    page: number;
    page_size: number;
}, Error>;
export declare function useLead(id: string): import("@tanstack/react-query").UseQueryResult<Lead, Error>;
export declare function useUpdateLead(): import("@tanstack/react-query").UseMutationResult<Lead, Error, {
    id: string;
    data: Partial<Lead>;
}, unknown>;
export declare function useDeleteLead(): import("@tanstack/react-query").UseMutationResult<void, Error, string, unknown>;
