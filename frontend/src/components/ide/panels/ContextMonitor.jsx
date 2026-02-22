/**
 * 文枢 WenShape - 深度上下文感知的智能体小说创作系统
 * WenShape - Deep Context-Aware Agent-Based Novel Writing System
 *
 * Copyright © 2025-2026 WenShape Team
 * License: PolyForm Noncommercial License 1.0.0
 *
 * 模块说明 / Module Description:
 *   上下文监控面板 - 展示多模型 Token 消耗、上下文预算分配和健康状态指标
 *   Context monitor panel displaying token consumption, budget allocation, and health metrics.
 */

import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { cn } from '../../ui/core';
import { AlertTriangle, CheckCircle2, AlertOctagon, Activity, BarChart2, PieChart } from 'lucide-react';
import { useLocale } from '../../../i18n';

/**
 * 上下文监控面板 - 实时展示 LLM Token 使用情况和上下文健康状态
 *
 * IDE panel for monitoring context budget allocation, token consumption across agents,
 * and system health status. Shows visual indicators for warning levels and available budget.
 *
 * @component
 * @example
 * return (
 *   <ContextMonitor
 *     data={{
 *       agents: [
 *         { agent: 'archivist', inputTokens: 1000, outputTokens: 500, maxTokens: 5000 }
 *       ],
 *       totalBudget: 128000,
 *       usedTokens: 6500
 *     }}
 *   />
 * )
 *
 * @param {Object} props - Component props
 * @param {Object} [props.data] - 上下文监控数据 / Context monitor data
 * @returns {JSX.Element} 上下文监控面板 / Context monitor panel element
 */

// --- 本地化映射 / Localization mappings ---

const AGENT_COLORS = {
    archivist: 'bg-purple-500',
    writer: 'bg-blue-500',
    editor: 'bg-emerald-500'
};

const TYPE_COLORS = {
    guiding: 'bg-green-500',
    informational: 'bg-blue-500',
    actionable: 'bg-orange-500',
    other: 'bg-gray-400'
};

// --- 子组件 / Subcomponents ---

/**
 * Agent Token 消耗条形图 / Agent cost bar component
 * @param {string} agentId - 智能体ID / Agent identifier
 * @param {number} inputTokens - 输入tokens / Input tokens
 * @param {number} outputTokens - 输出tokens / Output tokens
 * @param {number} maxTokens - 最大预算 / Maximum budget
 */
const AgentCostBar = ({ agentId, inputTokens, outputTokens, maxTokens }) => {
    const { t } = useLocale();
    const total = inputTokens + outputTokens;
    const inputPercent = (inputTokens / maxTokens) * 100;
    const outputPercent = (outputTokens / maxTokens) * 100;
    const AGENT_NAMES = {
        archivist: t('panels.timeline.agentArchivist'),
        writer: t('panels.timeline.agentWriter'),
        editor: t('panels.timeline.agentEditor'),
    };
    const name = AGENT_NAMES[agentId] || agentId;
    const color = AGENT_COLORS[agentId] || 'bg-gray-400';

    return (
        <div className="mb-3">
            <div className="flex justify-between text-[10px] mb-1 text-[var(--vscode-fg-subtle)]">
                <span className="font-bold flex items-center gap-1">
                    <div className={cn("w-2 h-2 rounded-full", color)} />
                    {name}
                </span>
                <span className="font-mono">
                    <span className="text-blue-600">{inputTokens}</span> + <span className="text-green-600">{outputTokens}</span> = {total}
                </span>
            </div>
            <div className="h-2 w-full bg-[var(--vscode-list-hover)] rounded-full overflow-hidden flex">
                <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${inputPercent}%` }}
                    className="h-full bg-blue-400/80"
                    title={`Context: ${inputTokens}`}
                />
                <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${outputPercent}%` }}
                    className="h-full bg-green-500/80"
                    title={`Output: ${outputTokens}`}
                />
            </div>
        </div>
    );
};

const ContextMonitor = ({
            stats = {
        token_usage: {
            total: 0,
            max: 16000,
            breakdown: { guiding: 0, informational: 0, actionable: 0 }
        },
        health: { healthy: true, issues: [] },
        // agent 维度统计可从 traces 推导，或由后端提供
    },
    // 可选：传入 traces 以计算 agent 消耗
    traces = []
}) => {
    const { t } = useLocale();
    const [viewMode, setViewMode] = useState('cost'); // 'cost' (Agent) | 'health' (Context)

    // 基于 traces 计算 Agent 消耗（前端聚合）
    const agentCosts = useMemo(() => {
        const costs = {
            archivist: { input: 0, output: 0 },
            writer: { input: 0, output: 0 },
            editor: { input: 0, output: 0 }
        };

        traces.forEach(trace => {
            // 若 trace 带有 context_stats，则使用其 token_usage 进行粗略拆分
            if (trace.context_stats?.token_usage) {
                const total = trace.context_stats.token_usage;
                const input = Math.floor(total * 0.8);
                const output = total - input;

                if (costs[trace.agent_name]) {
                    costs[trace.agent_name].input = input;
                    costs[trace.agent_name].output = output;
                }
            }
        });
        return costs;
    }, [traces]);

    // 全局统计
    const { token_usage, health } = stats;
    const globalUsagePercent = Math.min((token_usage.total / token_usage.max) * 100, 100);

    // 结构占比
    const guidingPercent = (token_usage.breakdown.guiding / token_usage.max) * 100;
    const infoPercent = (token_usage.breakdown.informational / token_usage.max) * 100;
    const actionPercent = (token_usage.breakdown.actionable / token_usage.max) * 100;

    return (
        <div className="flex flex-col gap-3 p-3 bg-[var(--vscode-bg)] border border-[var(--vscode-sidebar-border)] rounded-[6px] shadow-none h-full">
            {/* 头部 / 标签 */}
            <div className="flex items-center justify-between border-b border-[var(--vscode-sidebar-border)] pb-2">
                <div className="flex items-center gap-2">
                    <Activity size={16} className="text-[var(--vscode-focus-border)]" />
                    <span className="text-xs font-bold text-[var(--vscode-fg)]">{t('panels.context.systemTitle')}</span>
                </div>

                <div className="flex bg-[var(--vscode-input-bg)] p-0.5 rounded-[6px] border border-[var(--vscode-sidebar-border)]">
                    <button
                        onClick={() => setViewMode('cost')}
                        className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-medium transition-all",
                            viewMode === 'cost' ? "bg-[var(--vscode-list-active)] text-[var(--vscode-list-active-fg)]" : "text-[var(--vscode-fg-subtle)] hover:text-[var(--vscode-fg)]"
                        )}
                    >
                        <BarChart2 size={10} className="inline mr-1" />
                        {t('panels.context.viewCost')}
                    </button>
                    <button
                        onClick={() => setViewMode('health')}
                        className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-medium transition-all",
                            viewMode === 'health' ? "bg-[var(--vscode-list-active)] text-[var(--vscode-list-active-fg)]" : "text-[var(--vscode-fg-subtle)] hover:text-[var(--vscode-fg)]"
                        )}
                    >
                        <PieChart size={10} className="inline mr-1" />
                        {t('panels.context.viewHealth')}
                    </button>
                </div>
            </div>

            {/* 内容区 */}
            {viewMode === 'cost' ? (
                <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                    <div className="bg-[var(--vscode-input-bg)] rounded-[6px] p-3 border border-[var(--vscode-sidebar-border)] mb-3">
                        <div className="flex justify-between items-end mb-2">
                            <span className="text-xs font-medium text-[var(--vscode-fg-subtle)]">{t('panels.context.chapterCost')}</span>
                            <div className="text-right">
                                <span className="text-lg font-bold text-[var(--vscode-fg)] leading-none">{token_usage.total}</span>
                                <span className="text-xs text-[var(--vscode-fg-subtle)] ml-1">/ {token_usage.max}</span>
                            </div>
                        </div>
                        <div className="h-1.5 w-full bg-[var(--vscode-list-hover)] rounded-full overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${globalUsagePercent}%` }}
                                className={cn("h-full", globalUsagePercent > 90 ? "bg-red-500" : "bg-[var(--vscode-focus-border)]")}
                            />
                        </div>
                    </div>

                    <div className="space-y-4">
                        {Object.entries(agentCosts).map(([agent, cost]) => (
                            <AgentCostBar
                                key={agent}
                                agentId={agent}
                                inputTokens={cost.input}
                                outputTokens={cost.output}
                                maxTokens={8192} // Max per agent turn assumption for visualization
                            />
                        ))}
                    </div>

                    <div className="mt-4 pt-4 border-t border-[var(--vscode-sidebar-border)] flex justify-center gap-4 text-[10px] text-[var(--vscode-fg-subtle)]">
                        <div className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded bg-blue-400/80" />
                            <span>{t('panels.context.inputTokens')}</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded bg-green-500/80" />
                            <span>{t('panels.context.outputTokens')}</span>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="animate-in fade-in slide-in-from-right-4 duration-300 space-y-4">
                    {/* Health Status */}
                    <div className={cn(
                        "flex items-center gap-2 p-2 rounded-lg text-xs font-bold border",
                        health.healthy ? "bg-green-50 border-green-200 text-green-700" : "bg-red-50 border-red-200 text-red-700"
                    )}>
                        {health.healthy ? <CheckCircle2 size={14} /> : <AlertOctagon size={14} />}
                        {health.healthy ? t('panels.context.healthyMsg') : t('panels.context.warningMsg')}
                    </div>

                    {/* Breakdown Chart */}
                    <div className="bg-[var(--vscode-input-bg)] rounded-[6px] p-3 border border-[var(--vscode-sidebar-border)]">
                        <div className="text-[10px] text-[var(--vscode-fg-subtle)] mb-2 font-medium">{t('panels.context.tokenDistribution')}</div>
                        <div className="h-8 w-full bg-[var(--vscode-list-hover)] rounded flex overflow-hidden relative border border-[var(--vscode-sidebar-border)]">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${guidingPercent}%` }}
                                className={cn("h-full shadow-sm", TYPE_COLORS.guiding)}
                            />
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${infoPercent}%` }}
                                className={cn("h-full shadow-sm", TYPE_COLORS.informational)}
                            />
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${actionPercent}%` }}
                                className={cn("h-full shadow-sm", TYPE_COLORS.actionable)}
                            />
                        </div>
                        <div className="flex justify-between mt-2 text-[10px]">
                            <span className="flex items-center gap-1 text-[var(--vscode-fg-subtle)]">
                                <div className={cn("w-1.5 h-1.5 rounded-full", TYPE_COLORS.guiding)} /> {t('panels.context.typeGuiding')} ({token_usage.breakdown.guiding})
                            </span>
                            <span className="flex items-center gap-1 text-[var(--vscode-fg-subtle)]">
                                <div className={cn("w-1.5 h-1.5 rounded-full", TYPE_COLORS.informational)} /> {t('panels.context.typeInfo')} ({token_usage.breakdown.informational})
                            </span>
                            <span className="flex items-center gap-1 text-[var(--vscode-fg-subtle)]">
                                <div className={cn("w-1.5 h-1.5 rounded-full", TYPE_COLORS.actionable)} /> {t('panels.context.typeAction')} ({token_usage.breakdown.actionable})
                            </span>
                        </div>
                    </div>

                    {/* Issues List */}
                    {health.issues.length > 0 && (
                        <div className="bg-red-50/50 border border-red-100 rounded-[6px] p-3">
                            <div className="flex items-center gap-2 mb-2 text-red-700 font-bold text-xs">
                                <AlertTriangle size={12} />
                                <span>{t('panels.context.riskList')}</span>
                            </div>
                            <ul className="space-y-1">
                                {health.issues.map((issue, idx) => (
                                    <li key={idx} className="text-[10px] text-red-600 flex items-start gap-1.5">
                                        <span className="mt-1 w-1 h-1 rounded-full bg-red-500 shrink-0" />
                                        <span><span className="font-bold">[{issue.type}]</span> {issue.message}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ContextMonitor;
