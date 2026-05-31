export declare enum LeadStatus {
    NEW = "NEW",
    QUIZ_COMPLETED = "QUIZ_COMPLETED",
    MESSENGER_PENDING = "MESSENGER_PENDING",
    DESIGN_PENDING = "DESIGN_PENDING",
    DESIGN_REVIEW = "DESIGN_REVIEW",
    CONSULTING = "CONSULTING",
    QUALIFIED = "QUALIFIED",
    MEASUREMENT_PENDING = "MEASUREMENT_PENDING",
    MEASUREMENT_BOOKED = "MEASUREMENT_BOOKED",
    MEASUREMENT = "MEASUREMENT",
    MEASUREMENT_DONE = "MEASUREMENT_DONE",
    ESTIMATE_PREPARING = "ESTIMATE_PREPARING",
    ESTIMATE_REVIEW = "ESTIMATE_REVIEW",
    ESTIMATE_SENT = "ESTIMATE_SENT",
    ESTIMATE = "ESTIMATE",
    FOLLOW_UP = "FOLLOW_UP",
    CONTRACT_NEGOTIATION = "CONTRACT_NEGOTIATION",
    CONTRACT = "CONTRACT",
    WON = "WON",
    LOST = "LOST",
    SPAM = "SPAM"
}
export declare enum MessageDirection {
    INBOUND = "inbound",
    OUTBOUND = "outbound"
}
export interface Lead {
    id: string;
    org_id: string;
    telegram_id: number;
    full_name: string | null;
    phone: string | null;
    username: string | null;
    status: LeadStatus;
    ai_summary: string | null;
    operator_comment?: string | null;
    telegram_lookup_status?: string | null;
    telegram_lookup_checked_at?: string | null;
    telegram_lookup_error?: string | null;
    ai_qualification_status?: string;
    source: string | null;
    avatar_url?: string;
    converted_to_project_id?: string | null;
    last_message_at?: string | null;
    unread_count: number;
    extracted_data?: string | any;
    created_at: string;
    updated_at: string;
}
export interface ChatMessage {
    id: string;
    lead_id: string;
    direction: MessageDirection;
    content: string;
    media_url: string | null;
    telegram_message_id: number | null;
    is_read: boolean;
    sender_name: string | null;
    created_at: string;
    ai_metadata?: any;
}
export interface ActivityChartItem {
    day: string;
    count: number;
}
export interface ConversionChartItem {
    day: string;
    rate: number;
}
export interface RecentAIAction {
    lead_name: string;
    message_content: string;
    status: LeadStatus;
    created_at: string;
    lead_id: string;
}
export interface DashboardMetrics {
    total_leads: number;
    appointments: number;
    conversion_rate: number;
    in_progress: number;
    spam_count: number;
    avg_estimate_hours?: number | null;
    estimate_sla_met_rate?: number | null;
    estimates_tracked_count: number;
    activity_chart: ActivityChartItem[];
    conversion_chart: ConversionChartItem[];
    recent_ai_actions: RecentAIAction[];
}
export type CompanyFactCategory = 'company' | 'pricing' | 'measurement' | 'estimate' | 'portfolio' | 'warranty' | 'payment' | 'regions' | 'services' | 'communication';
export interface CompanyFact {
    id: string;
    org_id: string;
    key: string;
    title: string;
    value: string;
    category: CompanyFactCategory;
    value_type: 'text' | 'number' | 'url' | 'boolean' | 'list';
    priority: 'core' | 'scenario';
    tags: string[];
    stages: string[];
    questions: string[];
    hint?: string | null;
    display_order: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}
export type CompanyFactPayload = Omit<CompanyFact, 'id' | 'org_id' | 'created_at' | 'updated_at'>;
export interface User {
    id: string;
    email: string;
    full_name: string;
    role: string;
    org_id: string;
}
export interface LoginRequest {
    email: string;
    password: string;
}
export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
}
export interface PromptConfigBase {
    name: string;
    llm_model?: string;
    embedding_model?: string;
    system_prompt: string;
    welcome_message?: string;
    handoff_criteria?: string;
    is_active: boolean;
}
export interface PromptConfigCreate extends PromptConfigBase {
}
export interface PromptConfigResponse extends PromptConfigBase {
    id: string;
    org_id: string;
    created_at: string;
    updated_at: string;
}
export interface KnowledgeItemBase {
    content: string;
    category?: string;
    title?: string;
    metadata_json?: any;
}
export interface KnowledgeItemCreate extends KnowledgeItemBase {
}
export interface KnowledgeItemResponse extends KnowledgeItemBase {
    id: string;
    org_id: string;
    created_at: string;
    updated_at: string;
}
export interface KnowledgeSearchRequest {
    query: string;
    limit?: number;
    category?: string;
}
export interface CustomField {
    id: string;
    org_id: string;
    field_name: string;
    field_label: string;
    field_type: string;
    options: string[] | null;
    description: string | null;
    is_active: boolean;
    display_order: string;
    created_at: string;
    updated_at: string;
}
export interface LeadChangeLogItem {
    id: string;
    action: string;
    source?: string | null;
    user_id?: string | null;
    user_name?: string | null;
    changes?: Record<string, {
        old: any;
        new: any;
    }>;
    created_at: string;
}
export interface LeadChangeLogResponse {
    items: LeadChangeLogItem[];
}
