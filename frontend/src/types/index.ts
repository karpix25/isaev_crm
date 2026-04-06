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
    operator_comment?: string | null
    telegram_lookup_status?: string | null
    telegram_lookup_checked_at?: string | null
    telegram_lookup_error?: string | null
    ai_qualification_status?: string
    readiness_score?: 'A' | 'B' | 'C' | null
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
    telegram_id?: number | null
    username?: string | null
    phone?: string | null
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

export interface OperatorUser {
    id: string
    telegram_id?: number | null
    full_name?: string | null
    username?: string | null
    phone?: string | null
    email?: string | null
    role: 'MANAGER' | 'WORKER'
}

export interface OperatorCreatePayload {
    telegram_id: number
    full_name?: string
    username?: string
    phone?: string
    email?: string
    role?: 'MANAGER' | 'WORKER'
}

export interface OperatorUpdatePayload {
    full_name?: string
    username?: string
    phone?: string
    email?: string
    role?: 'MANAGER' | 'WORKER'
}

export type OperatorAccessRequestStatus = 'pending' | 'approved' | 'rejected'

export interface OperatorAccessRequest {
    id: string
    org_id: string
    telegram_id: number
    full_name?: string | null
    username?: string | null
    status: OperatorAccessRequestStatus
    processed_by_user_id?: string | null
    processed_by_name?: string | null
    processed_at?: string | null
    rejection_reason?: string | null
    created_at: string
}

export interface OperatorAccessApprovePayload {
    role?: 'MANAGER' | 'WORKER'
    full_name?: string
    username?: string
    phone?: string
    email?: string
}

export interface OperatorAccessRejectPayload {
    reason?: string
}

export interface LeadImportError {
    row: number
    reason: string
}

export interface LeadImportResult {
    total_rows: number
    imported: number
    updated: number
    skipped: number
    detected_columns: Record<string, string>
    errors: LeadImportError[]
}

export interface LeadBulkDeleteResult {
    requested: number
    deleted: number
}

export interface LeadChangeLogItem {
    id: string
    action: string
    source?: string | null
    user_id?: string | null
    user_name?: string | null
    changes?: Record<string, { old: any; new: any }>
    created_at: string
}

export interface LeadChangeLogResponse {
    items: LeadChangeLogItem[]
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
