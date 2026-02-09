export declare function useChatHistory(leadId: string, page?: number): import("@tanstack/react-query").UseQueryResult<{
    messages: import("../types").ChatMessage[];
    total: number;
    page: number;
    page_size: number;
}, Error>;
export declare function useSendMessage(): import("@tanstack/react-query").UseMutationResult<import("../types").ChatMessage, Error, {
    leadId: string;
    content: string;
}, unknown>;
export declare function useUnreadCount(): import("@tanstack/react-query").UseQueryResult<number, Error>;
