import React from 'react';
import { useIDE } from '../../context/IDEContext';
import { Folder, Save, AlertCircle, FileText, Bell } from 'lucide-react';

export function StatusBar() {
    const { state } = useIDE();
    const {
        activeProjectId,
        wordCount,
        selectionCount,
        cursorPosition,
        lastSavedAt,
        unsavedChanges,
        zenMode
    } = state;

    const formatTime = (date) => {
        if (!date) return '--:--';
        return new Date(date).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    if (zenMode) return null;

    return (
        <div className="h-6 min-h-[24px] bg-primary text-white flex items-center justify-between px-2 text-[11px] select-none flex-shrink-0 z-50">
            <div className="flex items-center gap-1">
                {activeProjectId && (
                    <button className="flex items-center gap-1.5 px-2 h-full hover:bg-white/10 rounded transition-colors">
                        <Folder size={12} />
                        <span className="max-w-[120px] truncate">{activeProjectId}</span>
                    </button>
                )}

                <button className="flex items-center gap-1.5 px-2 h-full hover:bg-white/10 rounded transition-colors">
                    {unsavedChanges ? (
                        <>
                            <AlertCircle size={12} className="text-yellow-300" />
                            <span>未保存</span>
                        </>
                    ) : lastSavedAt ? (
                        <>
                            <Save size={12} className="text-green-300" />
                            <span>已保存 {formatTime(lastSavedAt)}</span>
                        </>
                    ) : (
                        <>
                            <Save size={12} className="opacity-50" />
                            <span className="opacity-50">--:--</span>
                        </>
                    )}
                </button>
            </div>

            <div className="flex items-center gap-1">
                <button className="flex items-center gap-1.5 px-2 h-full hover:bg-white/10 rounded transition-colors">
                    <FileText size={12} />
                    <span>{wordCount.toLocaleString()} 字</span>
                    {selectionCount > 0 && (
                        <span className="opacity-80">（选中 {selectionCount.toLocaleString()} 字）</span>
                    )}
                </button>

                <button className="flex items-center gap-1.5 px-2 h-full hover:bg-white/10 rounded transition-colors font-mono">
                    <span>Ln {cursorPosition.line}, Col {cursorPosition.column}</span>
                </button>

                <button className="flex items-center gap-1.5 px-2 h-full hover:bg-white/10 rounded transition-colors">
                    <Bell size={12} />
                </button>
            </div>
        </div>
    );
}
