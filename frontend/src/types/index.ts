export enum LeadStatus {
    NEW = 'NEW',
    CONSULTING = 'CONSULTING',
    FOLLOW_UP = 'FOLLOW_UP',
    QUALIFIED = 'QUALIFIED',
    MEASUREMENT = 'MEASUREMENT',
    ESTIMATE = 'ESTIMATE',
    CONTRACT = 'CONTRACT',
    WON = 'WON',
    LOST = 'LOST',
    SPAM = 'SPAM'
}

export enum MessageDirection {
    INBOUND = 'inbound',
    OUTBOUND = 'outbound'
}

export interface Lead {
    id: string
    org_id: string
    telegram_id: number
    full_name: string | null
    phone: string | null
    username: string | null
    status: LeadStatus
    ai_summary: string | null
    ai_qualification_status?: string
    source: string | null
    avatar_url?: string
    converted_to_project_id?: string | null
    last_message_at?: string | null
    unread_count: number
    extracted_data?: string | any
    created_at: string
    updated_at: string
}

export interface ChatMessage {
    id: string
    lead_id: string
    direction: MessageDirection
    content: string
    media_url: string | null
    telegram_message_id: number | null
    is_read: boolean
    sender_name: string | null
    created_at: string
    ai_metadata?: Record<string, any>
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
    activity_chart: ActivityChartItem[];
    conversion_chart: ConversionChartItem[];
    recent_ai_actions: RecentAIAction[];
}

export interface User {
    id: string
    email: string
    full_name: string
    role: string
    org_id: string
}

export interface LoginRequest {
    email: string
    password: string
}

export interface TokenResponse {
    access_token: string
    refresh_token: string
    token_type: string
}

// AI Configuration
export interface PromptConfigBase {
    name: string
    llm_model?: string
    embedding_model?: string
    system_prompt: string
    welcome_message?: string
    handoff_criteria?: string
    is_active: boolean
}

export interface PromptConfigCreate extends PromptConfigBase { }

export interface PromptConfigResponse extends PromptConfigBase {
    id: string
    org_id: string
    created_at: string
    updated_at: string
}

export interface KnowledgeItemBase {
    content: string
    category?: string
    title?: string
    metadata_json?: any
}

export interface KnowledgeItemCreate extends KnowledgeItemBase { }

export interface KnowledgeItemResponse extends KnowledgeItemBase {
    id: string
    org_id: string
    created_at: string
    updated_at: string
}

export interface KnowledgeSearchRequest {
    query: string
    limit?: number
    category?: string
}

// Custom Fields
export interface CustomField {
    id: string
    org_id: string
    field_name: string
    field_label: string
    field_type: string
    options: string[] | null
    description: string | null
    is_active: boolean
    display_order: string
    created_at: string
    updated_at: string
}
