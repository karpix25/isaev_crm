import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Lock, Mail, Loader2 } from 'lucide-react';
import { authAPI } from '@/lib/api';
export function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();
    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const response = await authAPI.login({ email, password });
            localStorage.setItem('access_token', response.access_token);
            navigate('/');
        }
        catch (err) {
            setError(err.response?.data?.detail || 'Неверный email или пароль');
        }
        finally {
            setLoading(false);
        }
    };
    return (_jsx("div", { className: "flex min-h-screen items-center justify-center bg-background px-4", children: _jsxs("div", { className: "w-full max-w-md space-y-8 rounded-2xl border bg-card p-8 shadow-lg", children: [_jsxs("div", { className: "flex flex-col items-center text-center", children: [_jsx("div", { className: "mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary", children: _jsx(Building2, { className: "h-7 w-7 text-primary-foreground" }) }), _jsx("h1", { className: "text-2xl font-bold tracking-tight", children: "\u0412\u0445\u043E\u0434 \u0432 RenovaCRM" }), _jsx("p", { className: "mt-2 text-sm text-muted-foreground", children: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0441\u0432\u043E\u0438 \u0434\u0430\u043D\u043D\u044B\u0435 \u0434\u043B\u044F \u0434\u043E\u0441\u0442\u0443\u043F\u0430 \u0432 \u0441\u0438\u0441\u0442\u0435\u043C\u0443" })] }), error && (_jsx("div", { className: "rounded-lg bg-destructive/10 p-3 text-center text-sm font-medium text-destructive", children: error })), _jsxs("form", { className: "mt-8 space-y-6", onSubmit: handleSubmit, children: [_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium leading-6 text-foreground", children: "Email \u0430\u0434\u0440\u0435\u0441" }), _jsxs("div", { className: "relative mt-2", children: [_jsx(Mail, { className: "absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" }), _jsx("input", { type: "email", required: true, value: email, onChange: (e) => setEmail(e.target.value), className: "block w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary", placeholder: "admin@example.com" })] })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-sm font-medium leading-6 text-foreground", children: "\u041F\u0430\u0440\u043E\u043B\u044C" }), _jsxs("div", { className: "relative mt-2", children: [_jsx(Lock, { className: "absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" }), _jsx("input", { type: "password", required: true, value: password, onChange: (e) => setPassword(e.target.value), className: "block w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary", placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" })] })] })] }), _jsxs("button", { type: "submit", disabled: loading, className: "flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-semibold text-primary-foreground transition-all hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50", children: [loading && _jsx(Loader2, { className: "h-4 w-4 animate-spin" }), loading ? 'Вход...' : 'Войти в систему'] }), _jsxs("div", { className: "text-center text-xs text-muted-foreground", children: [_jsx("p", { children: "\u0418\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u0439\u0442\u0435 \u0434\u0430\u043D\u043D\u044B\u0435 \u0430\u0434\u043C\u0438\u043D\u0438\u0441\u0442\u0440\u0430\u0442\u043E\u0440\u0430 \u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E:" }), _jsx("p", { className: "mt-1 font-mono", children: "admin@test.com / admin123" })] })] })] }) }));
}
