import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { Leads } from './pages/Leads';
import { Chat } from './pages/Chat';
import { Projects } from './pages/Projects';
import { AISettings } from './pages/AISettings';
import { Login } from './pages/Login';
import './index.css';
const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            refetchOnWindowFocus: false,
            retry: 1,
        },
    },
});
function PrivateRoute({ children }) {
    const token = localStorage.getItem('access_token');
    return token ? _jsx(_Fragment, { children: children }) : _jsx(Navigate, { to: "/login", replace: true });
}
import { Toaster } from 'sonner';
function App() {
    return (_jsxs(QueryClientProvider, { client: queryClient, children: [_jsx(Toaster, { position: "top-right", expand: true, richColors: true }), _jsx(BrowserRouter, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(Login, {}) }), _jsx(Route, { path: "/", element: _jsx(PrivateRoute, { children: _jsx(Layout, { title: "\u0411\u0438\u0437\u043D\u0435\u0441-\u0430\u043D\u0430\u043B\u0438\u0442\u0438\u043A\u0430" }) }), children: _jsx(Route, { index: true, element: _jsx(Dashboard, {}) }) }), _jsx(Route, { path: "/leads", element: _jsx(PrivateRoute, { children: _jsx(Layout, { title: "\u0423\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435 \u043B\u0438\u0434\u0430\u043C\u0438" }) }), children: _jsx(Route, { index: true, element: _jsx(Leads, {}) }) }), _jsx(Route, { path: "/projects", element: _jsx(PrivateRoute, { children: _jsx(Layout, { title: "\u041F\u0440\u043E\u0435\u043A\u0442\u044B" }) }), children: _jsx(Route, { index: true, element: _jsx(Projects, {}) }) }), _jsx(Route, { path: "/chat/:leadId?", element: _jsx(PrivateRoute, { children: _jsx(Layout, { title: "AI \u0410\u0441\u0441\u0438\u0441\u0442\u0435\u043D\u0442" }) }), children: _jsx(Route, { index: true, element: _jsx(Chat, {}) }) }), _jsx(Route, { path: "/settings", element: _jsx(PrivateRoute, { children: _jsx(Layout, { title: "\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u0441\u0438\u0441\u0442\u0435\u043C\u044B" }) }), children: _jsx(Route, { index: true, element: _jsx(AISettings, {}) }) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/", replace: true }) })] }) })] }));
}
export default App;
