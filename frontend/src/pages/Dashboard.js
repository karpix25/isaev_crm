import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardAPI } from '@/lib/api';
import { Users, Calendar, TrendingUp, Briefcase } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatTimeAgo } from '@/lib/utils';
import { LeadStatus } from '@/types';
export function Dashboard() {
    const { data: metrics } = useQuery({
        queryKey: ['dashboard-metrics'],
        queryFn: () => dashboardAPI.getMetrics(),
    });
    if (!metrics) {
        return _jsx("div", { children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430..." });
    }
    return (_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "grid gap-4 md:grid-cols-4", children: [_jsx(MetricCard, { title: "\u0412\u0441\u0435\u0433\u043E \u043B\u0438\u0434\u043E\u0432", value: metrics.total_leads, icon: Users, color: "bg-blue-500" }), _jsx(MetricCard, { title: "\u041D\u0430 \u0437\u0430\u043C\u0435\u0440", value: metrics.appointments, icon: Calendar, color: "bg-purple-500" }), _jsx(MetricCard, { title: "\u041A\u043E\u043D\u0432\u0435\u0440\u0441\u0438\u044F", value: `${metrics.conversion_rate}%`, icon: TrendingUp, color: "bg-green-500" }), _jsx(MetricCard, { title: "\u0412 \u0440\u0430\u0431\u043E\u0442\u0435", value: metrics.in_progress, icon: Briefcase, color: "bg-orange-500" })] }), _jsxs("div", { className: "grid gap-6 md:grid-cols-2", children: [_jsxs("div", { className: "rounded-lg border bg-card p-6", children: [_jsx("h3", { className: "mb-4 text-lg font-semibold", children: "\u0410\u043A\u0442\u0438\u0432\u043D\u043E\u0441\u0442\u044C \u043B\u0438\u0434\u043E\u0432 (7 \u0434\u043D\u0435\u0439)" }), _jsx(ResponsiveContainer, { width: "100%", height: 250, children: _jsxs(BarChart, { data: metrics.activity_chart, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3" }), _jsx(XAxis, { dataKey: "day" }), _jsx(YAxis, {}), _jsx(Tooltip, {}), _jsx(Bar, { dataKey: "count", fill: "hsl(var(--primary))", radius: [8, 8, 0, 0] })] }) })] }), _jsxs("div", { className: "rounded-lg border bg-card p-6", children: [_jsx("h3", { className: "mb-4 text-lg font-semibold", children: "\u041A\u043E\u043D\u0432\u0435\u0440\u0441\u0438\u044F \u0432 \u0437\u0430\u043C\u0435\u0440\u044B" }), _jsx(ResponsiveContainer, { width: "100%", height: 250, children: _jsxs(LineChart, { data: metrics.conversion_chart, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3" }), _jsx(XAxis, { dataKey: "day" }), _jsx(YAxis, {}), _jsx(Tooltip, {}), _jsx(Line, { type: "monotone", dataKey: "rate", stroke: "hsl(var(--primary))", strokeWidth: 2, dot: { fill: 'hsl(var(--primary))' } })] }) })] })] }), _jsxs("div", { className: "rounded-lg border bg-card p-6", children: [_jsx("h3", { className: "mb-4 text-lg font-semibold", children: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044F \u0418\u0418" }), _jsx("div", { className: "space-y-3", children: metrics.recent_ai_actions.length === 0 ? (_jsx("p", { className: "text-sm text-muted-foreground py-4 text-center", children: "\u041D\u0435\u0442 \u043D\u0435\u0434\u0430\u0432\u043D\u0438\u0445 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0439 \u0418\u0418" })) : (metrics.recent_ai_actions.map((action, idx) => (_jsx(ActionItem, { name: action.lead_name, message: action.message_content, status: action.status, time: formatTimeAgo(action.created_at), avatar: action.lead_name[0] }, idx)))) })] })] }));
}
function MetricCard({ title, value, icon: Icon, color }) {
    return (_jsx("div", { className: "rounded-lg border bg-card p-6", children: _jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm text-muted-foreground", children: title }), _jsx("p", { className: "mt-2 text-3xl font-bold", children: value })] }), _jsx("div", { className: `rounded-lg ${color} p-3`, children: _jsx(Icon, { className: "h-6 w-6 text-white" }) })] }) }));
}
function ActionItem({ name, message, status, time, avatar }) {
    const statusColors = {
        [LeadStatus.NEW]: 'bg-blue-500',
        [LeadStatus.CONSULTING]: 'bg-yellow-500',
        [LeadStatus.QUALIFIED]: 'bg-green-500',
        [LeadStatus.FOLLOW_UP]: 'bg-purple-500',
    };
    return (_jsxs("div", { className: "flex items-start gap-3 rounded-lg border p-3", children: [_jsx("div", { className: "flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground", children: avatar }), _jsxs("div", { className: "flex-1 overflow-hidden", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("div", { className: "font-medium truncate", children: name }), _jsx("div", { className: "text-[10px] text-muted-foreground whitespace-nowrap", children: time })] }), _jsx("p", { className: "text-sm text-muted-foreground truncate", children: message }), _jsx("div", { className: "mt-1", children: _jsx("span", { className: `inline-block rounded px-2 py-0.5 text-[10px] font-bold text-white ${statusColors[status] || 'bg-slate-500'}`, children: status }) })] })] }));
}
