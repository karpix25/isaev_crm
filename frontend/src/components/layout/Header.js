import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React from 'react';
import { Search, Bell, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
export function Header({ title }) {
    const navigate = useNavigate();
    const handleLogout = () => {
        localStorage.removeItem('access_token');
        navigate('/login');
    };
    return (_jsxs("header", { className: "flex h-16 items-center justify-between border-b bg-card px-6", children: [_jsx("h1", { className: "text-xl font-semibold", children: title }), _jsxs("div", { className: "flex items-center gap-4", children: [_jsxs("div", { className: "relative", children: [_jsx(Search, { className: "absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" }), _jsx("input", { type: "text", placeholder: "\u041F\u043E\u0438\u0441\u043A \u043F\u043E \u0441\u0438\u0441\u0442\u0435\u043C\u0435...", className: "h-10 w-64 rounded-lg border bg-background pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary" })] }), _jsxs("button", { className: "relative rounded-lg p-2 hover:bg-accent", children: [_jsx(Bell, { className: "h-5 w-5" }), _jsx("span", { className: "absolute right-1 top-1 h-2 w-2 rounded-full bg-destructive" })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("div", { className: "flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-sm font-medium text-primary-foreground", children: "AD" }), _jsx("button", { onClick: handleLogout, className: "rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-destructive", title: "\u0412\u044B\u0439\u0442\u0438", children: _jsx(LogOut, { className: "h-5 w-5" }) })] })] })] }));
}
