export enum LeadStatus {
    NEW = 'NEW',
    QUIZ_COMPLETED = 'QUIZ_COMPLETED',
    MESSENGER_PENDING = 'MESSENGER_PENDING',
    DESIGN_PENDING = 'DESIGN_PENDING',
    DESIGN_REVIEW = 'DESIGN_REVIEW',
    CONSULTING = 'CONSULTING',
    QUALIFIED = 'QUALIFIED',
    MEASUREMENT_PENDING = 'MEASUREMENT_PENDING',
    MEASUREMENT_BOOKED = 'MEASUREMENT_BOOKED',
    MEASUREMENT = 'MEASUREMENT',
    MEASUREMENT_DONE = 'MEASUREMENT_DONE',
    ESTIMATE_PREPARING = 'ESTIMATE_PREPARING',
    ESTIMATE_REVIEW = 'ESTIMATE_REVIEW',
    ESTIMATE_SENT = 'ESTIMATE_SENT',
    ESTIMATE = 'ESTIMATE',
    FOLLOW_UP = 'FOLLOW_UP',
    CONTRACT_NEGOTIATION = 'CONTRACT_NEGOTIATION',
    CONTRACT = 'CONTRACT',
    WON = 'WON',
    LOST = 'LOST',
    SPAM = 'SPAM'
}

export enum MessageDirection {
    INBOUND = 'inbound',
    OUTBOUND = 'outbound'
}

export enum MessageTransport {
    TELEGRAM = 'telegram',
    WHATSAPP = 'whatsapp',
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
    transport?: MessageTransport
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
    avg_estimate_hours?: number | null;
    estimate_sla_met_rate?: number | null;
    estimates_tracked_count: number;
    activity_chart: ActivityChartItem[];
    conversion_chart: ConversionChartItem[];
    recent_ai_actions: RecentAIAction[];
}

export type CompanyFactCategory =
    | 'company'
    | 'pricing'
    | 'measurement'
    | 'estimate'
    | 'portfolio'
    | 'warranty'
    | 'payment'
    | 'regions'
    | 'services'
    | 'communication'

export interface CompanyFact {
    id: string
    org_id: string
    key: string
    title: string
    value: string
    category: CompanyFactCategory
    value_type: 'text' | 'number' | 'url' | 'boolean' | 'list'
    priority: 'core' | 'scenario'
    tags: string[]
    stages: string[]
    questions: string[]
    hint?: string | null
    display_order: number
    is_active: boolean
    created_at: string
    updated_at: string
}

export type CompanyFactPayload = Omit<CompanyFact, 'id' | 'org_id' | 'created_at' | 'updated_at'>

export interface FunnelStepMetric {
    key: string
    label: string
    count: number
    conversion_from_previous?: number | null
    conversion_from_start?: number | null
}

export interface BreakdownItem {
    key: string
    label: string
    count: number
}

export interface QuizAnswerBreakdown {
    step_id: string
    label: string
    options: BreakdownItem[]
}

export interface MessengerMetric {
    messenger: string
    label: string
    clicks: number
    inbound: number
    conversion_rate: number
    lost_after_click: number
}

export interface AnalyticsEventItem {
    id: string
    session_token: string
    lead_id?: string | null
    event_type: string
    step_id?: string | null
    event_data?: Record<string, any> | null
    created_at: string
}

export interface AnalyticsSummary {
    sessions_total: number
    sessions_completed: number
    sessions_abandoned: number
    leads_linked: number
    completion_rate: number
    funnel: FunnelStepMetric[]
    sources: BreakdownItem[]
    campaigns: BreakdownItem[]
    channels: BreakdownItem[]
    quiz_answers: QuizAnswerBreakdown[]
    messenger_metrics: MessengerMetric[]
    recent_events: AnalyticsEventItem[]
}

export interface AnalyticsSummaryParams {
    date_from?: string
    date_to?: string
    source?: string
    campaign?: string
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

export type ManagedUserRole = 'ADMIN' | 'MANAGER' | 'WORKER'

export interface OperatorUser {
    id: string
    telegram_id?: number | null
    full_name?: string | null
    username?: string | null
    phone?: string | null
    email?: string | null
    role: ManagedUserRole
}

export interface OperatorCreatePayload {
    telegram_id: number
    full_name?: string
    username?: string
    phone?: string
    email?: string
    role?: ManagedUserRole
}

export interface OperatorUpdatePayload {
    full_name?: string
    username?: string
    phone?: string
    email?: string
    role?: ManagedUserRole
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
    role?: ManagedUserRole
    full_name?: string
    username?: string
    phone?: string
    email?: string
}

export interface OperatorAccessRejectPayload {
    reason?: string
}

export interface TelegramBusinessCardTemplateSettings {
    template: string
    variables: string[]
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
