/**
 * 文枢 WenShape - 深度上下文感知的智能体小说创作系统
 * WenShape - Deep Context-Aware Agent-Based Novel Writing System
 *
 * Copyright © 2025-2026 WenShape Team
 * License: PolyForm Noncommercial License 1.0.0
 *
 * 模块说明 / Module Description:
 *   应用主路由配置 - IDE-First 设计的核心入口
 */

import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import WritingSession from './pages/WritingSession';
import ErrorBoundary from './components/ErrorBoundary';
import { projectsAPI } from './api';
import { t } from './i18n';
import logger from './utils/logger';

/**
 * 自动重定向组件 / Auto-Redirect Component
 *
 * 应用加载时的首个入口。负责：
 * 1. 检查已存在的项目列表
 * 2. 重定向到最近项目的 IDE，或自动创建首个默认项目
 * 3. 提供加载中和错误状态的 UI 反馈
 *
 * @component
 * @returns {JSX.Element} 加载/错误页面或无返回（重定向发生）
 */
function AutoRedirect() {
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  useEffect(() => {
    const redirect = async () => {
      try {
        const res = await projectsAPI.list();
        const projects = res.data;

        if (projects && projects.length > 0) {
          navigate(`/project/${projects[0].id}/session`, { replace: true });
          return;
        }

        const newProject = await projectsAPI.create({ name: t('app.defaultProjectName') });
        navigate(`/project/${newProject.data.id}/session`, { replace: true });
      } catch (err) {
        logger.error('Failed to load projects:', err);
        setError(err?.message || String(err));
      }
    };

    redirect();
  }, [navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--vscode-bg)] text-[var(--vscode-fg)]">
        <div className="ws-paper p-8 text-center max-w-md">
          <h1 className="text-lg font-bold text-red-600 mb-2">{t('app.loadFailed')}</h1>
          <p className="text-[var(--vscode-fg-subtle)] text-sm break-words">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-6 px-4 h-10 bg-[var(--vscode-list-active)] text-[var(--vscode-list-active-fg)] rounded-[6px] border border-[var(--vscode-input-border)] hover:opacity-90 transition-colors"
          >
            {t('app.retryBtn')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--vscode-bg)] text-[var(--vscode-fg)]">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-[var(--vscode-focus-border)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-[var(--vscode-fg-subtle)] text-sm">{t('app.loading')}</p>
      </div>
    </div>
  );
}

function RedirectToSession() {
  return <Navigate to="session" replace />;
}

function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<AutoRedirect />} />
        <Route path="/project/:projectId/session" element={<WritingSession />} />

        {/* 兼容旧路径 */}
        <Route path="/project/:projectId" element={<RedirectToSession />} />
        <Route path="/project/:projectId/fanfiction" element={<RedirectToSession />} />

        {/* 当前入口统一回到首页 */}
        <Route path="/agents" element={<Navigate to="/" replace />} />
        <Route path="/system" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}

export default App;
