export declare function useProjects(): import("@tanstack/react-query").UseQueryResult<any, Error>;
export declare function useConvertLeadToProject(): import("@tanstack/react-query").UseMutationResult<any, Error, {
    leadId: string;
    projectName?: string;
}, unknown>;
export declare function useCreateProject(): import("@tanstack/react-query").UseMutationResult<any, Error, {
    name: string;
    address: string;
    description?: string;
    budget_total?: number;
}, unknown>;
export declare function useUpdateProject(): import("@tanstack/react-query").UseMutationResult<any, Error, {
    id: string;
    data: Partial<ProjectBase>;
}, unknown>;
export declare function useDeleteProject(): import("@tanstack/react-query").UseMutationResult<void, Error, string, unknown>;
interface ProjectBase {
    name: string;
    address: string;
    description?: string;
    budget_total?: number;
    budget_spent?: number;
}
export {};
