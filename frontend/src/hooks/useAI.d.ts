import type { PromptConfigResponse, PromptConfigCreate, KnowledgeItemResponse, KnowledgeItemCreate, KnowledgeSearchRequest } from '@/types';
export declare function useAI(): {
    prompts: import("@tanstack/react-query").UseQueryResult<PromptConfigResponse[], Error>;
    activePrompt: import("@tanstack/react-query").UseQueryResult<PromptConfigResponse, Error>;
    createPrompt: import("@tanstack/react-query").UseMutationResult<PromptConfigResponse, Error, PromptConfigCreate, unknown>;
    addKnowledge: import("@tanstack/react-query").UseMutationResult<KnowledgeItemResponse, Error, KnowledgeItemCreate, unknown>;
    searchKnowledge: import("@tanstack/react-query").UseMutationResult<KnowledgeItemResponse[], Error, KnowledgeSearchRequest, unknown>;
    uploadFile: import("@tanstack/react-query").UseMutationResult<any, Error, {
        file: File;
        category: string;
    }, unknown>;
    deleteKnowledge: import("@tanstack/react-query").UseMutationResult<void, Error, string, unknown>;
    knowledge: import("@tanstack/react-query").UseQueryResult<KnowledgeItemResponse[], Error>;
};
