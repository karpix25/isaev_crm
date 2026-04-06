export declare function useChatHistory(leadId: string, page?: number, transport?: import("../types").MessageTransport): import("@tanstack/react-query").UseQueryResult<{
    messages: import("../types").ChatMessage[];
    total: number;
    page: number;
    page_size: number;
}, Error>;
export declare function useSendMessage(): import("@tanstack/react-query").UseMutationResult<import("../types").ChatMessage, Error, {
    leadId: string;
    content: string;
    transport: import("../types").MessageTransport;
}, unknown>;
export declare function useSendBusinessCard(): import("@tanstack/react-query").UseMutationResult<import("../types").ChatMessage, Error, {
    leadId: string;
}, unknown>;
export declare function useUnreadCount(): import("@tanstack/react-query").UseQueryResult<number, Error>;
