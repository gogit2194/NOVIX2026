import React, { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { Bot, Search, Edit3, Terminal, Plus } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { configAPI } from '../../../api';
import { cn, Button } from '../../ui/core';
import LLMProfileModal from '../../../components/LLMProfileModal';
import { useTraceEvents } from '../../../hooks/useTraceEvents';

// Fetcher for SWR
const fetcher = (fn) => fn().then(res => res.data);

const ROLES = [
    { id: 'archivist', label: '档案员', eng: 'Archivist', icon: 'Book', desc: '整理设定 & 构建上下文' },
    { id: 'writer', label: '主笔', eng: 'Writer', icon: 'Edit3', desc: '撰写章节正文' },
    { id: 'editor', label: '编辑', eng: 'Editor', icon: 'Bot', desc: '根据反馈修改章节' },
];

const AgentsPanel = ({ children, mode = 'assistant' }) => {
    // mode: 'assistant' (Right Panel: Console, Timeline, Monitor) | 'config' (Left Panel: Config Only)

    // Default Tab Logic
    const [activeTab, setActiveTab] = useState('console');

    // Adjust default tab based on input children or mode
    useEffect(() => {
        if (mode === 'assistant') {
            setActiveTab('console');
        }
    }, [mode]);

    // Data Fetching
    const { data: profiles = [], isLoading: loadingProfiles } = useSWR(
        'llm-profiles',
        () => fetcher(configAPI.getProfiles),
        { revalidateOnFocus: false }
    );

    const { data: assignments = {}, isLoading: loadingAssignments } = useSWR(
        'agent-assignments',
        () => fetcher(configAPI.getAssignments),
        { revalidateOnFocus: false }
    );

    // Trace Data for assistant mode
    const { isConnected } = useTraceEvents();

    const isLoading = loadingProfiles || loadingAssignments;
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedProfile, setSelectedProfile] = useState(null);

    // Handlers
    const handleAssignmentChange = async (roleId, profileId) => {
        const newAssignments = { ...assignments, [roleId]: profileId };
        mutate('agent-assignments', newAssignments, false);
        try {
            await configAPI.updateAssignments(newAssignments);
            mutate('agent-assignments');
        } catch (e) {
            console.error("Failed to update assignment", e);
            mutate('agent-assignments');
        }
    };

    const handleEditProfile = (profile) => {
        setSelectedProfile(profile);
        setIsModalOpen(true);
    };

    const handleCreateProfile = () => {
        setSelectedProfile(null);
        setIsModalOpen(true);
    };

    const handleSaveProfile = async (profileData) => {
        try {
            await configAPI.saveProfile(profileData);
            setIsModalOpen(false);
            setSelectedProfile(null);
            mutate('llm-profiles');
        } catch (e) {
            console.error("Failed to save profile", e);
        }
    };

    // --- Render: Config Mode (Left Sidebar) ---
    if (mode === 'config') {
        return (
            <div className="flex flex-col h-full bg-surface overflow-hidden">
                <div className="p-4 space-y-6 overflow-y-auto h-full scrollbar-hide">
                    {isLoading ? (
                        [1, 2, 3, 4].map(i => (
                            <div key={i} className="h-24 bg-ink-50 animate-pulse rounded-lg" />
                        ))
                    ) : (
                        <>
                            {/* Agent Roles Config */}
                            <div className="space-y-3">
                                <div className="text-xs font-bold text-ink-400 uppercase tracking-wider mb-2">角色模型绑定</div>
                                {ROLES.map(role => {
                                    const assignedProfileId = assignments[role.id];

                                    // Dynamic icon selection
                                    const Icon = role.id === 'archivist' ? Search : role.id === 'writer' ? Edit3 : Bot;

                                    return (
                                        <div
                                            key={role.id}
                                            className="group flex flex-col gap-3 p-3 rounded-xl border border-border bg-background hover:border-primary/40 hover:shadow-sm transition-all duration-200"
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    <div className={cn("p-2 rounded-lg text-ink-600 bg-ink-50 transition-colors group-hover:bg-primary/5 group-hover:text-primary",
                                                        role.id === 'writer' && "text-primary bg-primary/10"
                                                    )}>
                                                        <Icon size={16} />
                                                    </div>
                                                    <div>
                                                        <div className="text-sm font-bold leading-none text-ink-800">{role.label}</div>
                                                        <div className="text-[10px] text-ink-400 font-medium uppercase tracking-wider mt-1">{role.eng}</div>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="relative">
                                                <select
                                                    value={assignedProfileId || ''}
                                                    onChange={(e) => handleAssignmentChange(role.id, e.target.value)}
                                                    className="w-full text-xs py-2 pl-2 pr-6 bg-ink-50/50 border border-border rounded-lg hover:border-primary/50 focus:border-primary focus:ring-2 focus:ring-primary/10 outline-none transition-colors appearance-none cursor-pointer text-ink-700 font-medium font-mono truncate"
                                                >
                                                    <option value="" disabled>选择模型...</option>
                                                    {profiles.map(p => (
                                                        <option key={p.id} value={p.id}>
                                                            {p.name}
                                                        </option>
                                                    ))}
                                                </select>
                                                <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-ink-400">
                                                    <Bot size={12} />
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Model Library */}
                            <div className="pt-4 border-t border-border">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="text-xs font-bold text-ink-400 uppercase tracking-wider">模型库</div>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={handleCreateProfile}
                                        className="h-6 text-[10px] hover:text-primary px-2"
                                    >
                                        <Plus size={12} className="mr-1" /> 添加
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 gap-2">
                                    {profiles.map(p => (
                                        <div
                                            key={p.id}
                                            onClick={() => handleEditProfile(p)}
                                            className="bg-background border border-border rounded-lg p-3 text-xs flex flex-row items-center justify-between hover:border-primary/30 hover:shadow-sm cursor-pointer transition-all group"
                                        >
                                            <div className="flex flex-col gap-0.5">
                                                <span className="font-bold text-ink-800 group-hover:text-primary transition-colors">{p.name}</span>
                                                <span className="text-ink-300 font-mono text-[10px]">{p.provider}</span>
                                            </div>
                                            <span className="font-mono bg-ink-50 px-2 py-1 rounded text-[10px] text-ink-500">{p.model}</span>
                                        </div>
                                    ))}
                                    {profiles.length === 0 && (
                                        <div className="text-center py-6 text-xs text-ink-400 border border-dashed border-border rounded-lg bg-ink-50/30">
                                            暂无模型可用
                                        </div>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Modal */}
                <AnimatePresence>
                    {isModalOpen && (
                        <LLMProfileModal
                            open={isModalOpen}
                            profile={selectedProfile}
                            onClose={() => {
                                setIsModalOpen(false);
                                setSelectedProfile(null);
                            }}
                            onSave={handleSaveProfile}
                        />
                    )}
                </AnimatePresence>
            </div>
        );
    }

    // --- Render: Assistant Mode (Right Panel) ---
    return (
        <div className="flex flex-col h-full bg-surface text-ink-900 border-l border-border shadow-2xl">
            {/* Header Area */}
            <div className="flex flex-col border-b border-border bg-background flex-shrink-0 z-10">
                <div className="flex items-center justify-between px-4 py-3">
                    <h2 className="text-sm font-bold flex items-center gap-2 tracking-wide">
                        <Bot size={16} className="text-primary" />
                        <span className="font-serif">智能助手</span>
                    </h2>
                    <div className="flex items-center gap-3">
                        {/* WebSocket Status */}
                        <div className="flex items-center gap-1.5" title={isConnected ? "系统在线" : "连接断开"}>
                            <span className={cn("w-1.5 h-1.5 rounded-full shadow-glow transition-colors duration-500", isConnected ? "bg-green-500 shadow-green-500/50" : "bg-red-500 shadow-red-500/50")} />
                            <span className="text-[10px] text-ink-300 font-mono uppercase tracking-wider">
                                {isConnected ? "ONLINE" : "OFFLINE"}
                            </span>
                        </div>
                    </div>
                </div>

                {/* V2 Flow Indicator */}
                <div className="px-4 pb-2">
                    <div className="flex items-center gap-1 text-[9px] text-ink-400">
                        <span className="px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded font-medium">档案员</span>
                        <span>→</span>
                        <span className="px-1.5 py-0.5 bg-green-100 text-green-600 rounded font-medium">主笔</span>
                        <span className="text-ink-200">|</span>
                        <span className="px-1.5 py-0.5 bg-amber-100 text-amber-600 rounded font-medium">编辑</span>
                        <span className="ml-1 text-ink-300 italic">(V2 简化流程)</span>
                    </div>
                </div>

                {/* Modern Tabs */}
                <div className="flex px-2 pb-0 gap-1 overflow-x-auto scrollbar-hide border-b border-transparent">
                    {children && (
                        <TabButton
                            isActive={activeTab === 'console'}
                            onClick={() => setActiveTab('console')}
                            icon={Terminal}
                            label="控制台"
                        />
                    )}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative bg-surface/30">
                <AnimatePresence mode="wait">
                    {activeTab === 'console' && children && (
                        <TabContent key="console">
                            <div className="h-full flex flex-col overflow-hidden">
                                {children}
                            </div>
                        </TabContent>
                    )}

                </AnimatePresence>
            </div>
        </div>
    );
};

// Sub-components for styling
const TabButton = ({ isActive, onClick, icon: Icon, label }) => (
    <button
        onClick={onClick}
        className={cn(
            "relative px-4 py-2.5 text-xs font-bold transition-all duration-300 flex items-center gap-1.5 focus:outline-none rounded-t-lg select-none",
            isActive
                ? "text-primary bg-surface/50 translate-y-[1px]"
                : "text-ink-400 hover:text-ink-600 hover:bg-ink-50/50"
        )}
    >
        <Icon size={14} className={cn("transition-transform duration-300", isActive ? "scale-110" : "scale-100")} />
        <span>{label}</span>
        {isActive && (
            <motion.div
                layoutId="activeTabIndicator"
                className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary shadow-[0_-2px_8px_rgba(var(--primary),0.4)]"
            />
        )}
    </button>
);

const TabContent = ({ children }) => (
    <motion.div
        initial={{ opacity: 0, x: 5 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -5 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="h-full w-full"
    >
        {children}
    </motion.div>
);

export default AgentsPanel;
