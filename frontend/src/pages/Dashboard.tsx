import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { dashboardAPI } from '@/lib/api'
import { Users, Calendar, TrendingUp, Briefcase } from 'lucide-react'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { formatTimeAgo } from '@/lib/utils'
import { LeadStatus } from '@/types'

export function Dashboard() {
    const { data: metrics } = useQuery({
        queryKey: ['dashboard-metrics'],
        queryFn: () => dashboardAPI.getMetrics(),
    })

    if (!metrics) {
        return <div>Загрузка...</div>
    }

    return (
        <div className="space-y-6">
            {/* Metrics Cards */}
            <div className="grid gap-4 md:grid-cols-4">
                <MetricCard
                    title="Всего лидов"
                    value={metrics.total_leads}
                    icon={Users}
                    color="bg-blue-500"
                />
                <MetricCard
                    title="На замер"
                    value={metrics.appointments}
                    icon={Calendar}
                    color="bg-purple-500"
                />
                <MetricCard
                    title="Конверсия"
                    value={`${metrics.conversion_rate}%`}
                    icon={TrendingUp}
                    color="bg-green-500"
                />
                <MetricCard
                    title="В работе"
                    value={metrics.in_progress}
                    icon={Briefcase}
                    color="bg-orange-500"
                />
            </div>

            {/* Charts */}
            <div className="grid gap-6 md:grid-cols-2">
                {/* Activity Chart */}
                <div className="rounded-lg border bg-card p-6">
                    <h3 className="mb-4 text-lg font-semibold">Активность лидов (7 дней)</h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={metrics.activity_chart}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="day" />
                            <YAxis />
                            <Tooltip />
                            <Bar dataKey="count" fill="hsl(var(--primary))" radius={[8, 8, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Conversion Chart */}
                <div className="rounded-lg border bg-card p-6">
                    <h3 className="mb-4 text-lg font-semibold">Конверсия в замеры</h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={metrics.conversion_chart}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="day" />
                            <YAxis />
                            <Tooltip />
                            <Line
                                type="monotone"
                                dataKey="rate"
                                stroke="hsl(var(--primary))"
                                strokeWidth={2}
                                dot={{ fill: 'hsl(var(--primary))' }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Recent Actions */}
            <div className="rounded-lg border bg-card p-6">
                <h3 className="mb-4 text-lg font-semibold">Последние действия ИИ</h3>
                <div className="space-y-3">
                    {metrics.recent_ai_actions.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4 text-center">Нет недавних действий ИИ</p>
                    ) : (
                        metrics.recent_ai_actions.map((action, idx) => (
                            <ActionItem
                                key={idx}
                                name={action.lead_name}
                                message={action.message_content}
                                status={action.status}
                                time={formatTimeAgo(action.created_at)}
                                avatar={action.lead_name[0]}
                            />
                        ))
                    )}
                </div>
            </div>
        </div>
    )
}

interface MetricCardProps {
    title: string
    value: string | number
    icon: React.ElementType
    color: string
}

function MetricCard({ title, value, icon: Icon, color }: MetricCardProps) {
    return (
        <div className="rounded-lg border bg-card p-6">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm text-muted-foreground">{title}</p>
                    <p className="mt-2 text-3xl font-bold">{value}</p>
                </div>
                <div className={`rounded-lg ${color} p-3`}>
                    <Icon className="h-6 w-6 text-white" />
                </div>
            </div>
        </div>
    )
}

interface ActionItemProps {
    name: string
    message: string
    status: string
    time: string
    avatar: string
}

function ActionItem({ name, message, status, time, avatar }: ActionItemProps) {
    const statusColors: Record<string, string> = {
        [LeadStatus.NEW]: 'bg-blue-500',
        [LeadStatus.CONSULTING]: 'bg-yellow-500',
        [LeadStatus.QUALIFIED]: 'bg-green-500',
        [LeadStatus.FOLLOW_UP]: 'bg-purple-500',
    }

    return (
        <div className="flex items-start gap-3 rounded-lg border p-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                {avatar}
            </div>
            <div className="flex-1 overflow-hidden">
                <div className="flex items-center justify-between">
                    <div className="font-medium truncate">{name}</div>
                    <div className="text-[10px] text-muted-foreground whitespace-nowrap">{time}</div>
                </div>
                <p className="text-sm text-muted-foreground truncate">{message}</p>
                <div className="mt-1">
                    <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold text-white ${statusColors[status] || 'bg-slate-500'}`}>
                        {status}
                    </span>
                </div>
            </div>
        </div>
    )
}
