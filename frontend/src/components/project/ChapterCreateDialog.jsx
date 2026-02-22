import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../ui/core';
import { useLocale } from '../../i18n';

/**
 * ChapterCreateDialog - 新建章节弹窗
 * 仅做视觉一致性优化，不改变数据与交互逻辑。
 */
export function ChapterCreateDialog({
    open,
    onClose,
    onConfirm,
    existingChapters = [],
    volumes = [],
    defaultVolumeId = 'V1',
}) {
    const { t } = useLocale();
    const [chapterType, setChapterType] = useState('normal');
    const [selectedVolume, setSelectedVolume] = useState('V1');
    const [insertAfter, setInsertAfter] = useState('');
    const [suggestedId, setSuggestedId] = useState('');
    const [customId, setCustomId] = useState('');
    const [title, setTitle] = useState('');

    // 逻辑保持不变
    const availableVolumes = volumes.length ? volumes : [{ id: 'V1', title: t('volume.defaultV1') }];

    const normalizeToVolume = (chapterId, volumeId) => {
        const trimmed = (chapterId || '').trim().toUpperCase();
        if (!trimmed) return '';
        if (trimmed.startsWith('V')) return trimmed;
        if (trimmed.startsWith('C')) return `${volumeId}${trimmed}`;
        return trimmed;
    };

    const parseVolumeId = (chapterId) => {
        const match = (chapterId || '').toUpperCase().match(/^V(\d+)/);
        return match ? `V${match[1]}` : 'V1';
    };

    const normalizedChapters = existingChapters.map((chapter) => {
        const volumeId = parseVolumeId(chapter.id);
        const normalizedId = normalizeToVolume(chapter.id, volumeId);
        return { ...chapter, volumeId, normalizedId };
    });

    useEffect(() => {
        if (!open) return;
        let suggested = '';
        if (chapterType === 'normal') {
            const normalChapters = normalizedChapters.filter(
                (chapter) => chapter.volumeId === selectedVolume && /C\d+$/i.test(chapter.normalizedId)
            );
            let maxChapter = 0;
            normalChapters.forEach((chapter) => {
                const match = chapter.normalizedId.match(/C(\d+)/i);
                if (match) maxChapter = Math.max(maxChapter, Number.parseInt(match[1], 10));
            });
            suggested = `${selectedVolume}C${maxChapter + 1}`;
        } else if (chapterType === 'extra' && insertAfter) {
            const extraCount = normalizedChapters.filter(
                (chapter) => chapter.normalizedId.startsWith(insertAfter) && chapter.normalizedId.toUpperCase().includes('E')
            ).length;
            suggested = `${insertAfter}E${extraCount + 1}`;
        } else if (chapterType === 'interlude' && insertAfter) {
            const interludeCount = normalizedChapters.filter(
                (chapter) => chapter.normalizedId.startsWith(insertAfter) && chapter.normalizedId.toUpperCase().includes('I')
            ).length;
            suggested = `${insertAfter}I${interludeCount + 1}`;
        }
        setSuggestedId(suggested);
        setCustomId('');
    }, [chapterType, insertAfter, normalizedChapters, open, selectedVolume]);

    useEffect(() => {
        if (open) {
            setChapterType('normal');
            setInsertAfter('');
            setTitle('');
            setCustomId('');
            const fallback = availableVolumes[0]?.id || 'V1';
            const target = availableVolumes.find((v) => v.id === defaultVolumeId) ? defaultVolumeId : fallback;
            setSelectedVolume(target);
        }
    }, [availableVolumes, defaultVolumeId, open]);

    useEffect(() => {
        if (chapterType !== 'normal') setInsertAfter('');
    }, [chapterType, selectedVolume]);

    const rawId = customId || suggestedId;
    const finalId = normalizeToVolume(rawId, selectedVolume);
    const canCreate = Boolean(title && finalId);
    const normalChapters = normalizedChapters.filter(
        (chapter) => chapter.volumeId === selectedVolume && /C\d+$/i.test(chapter.normalizedId)
    );

    if (!open) return null;

    return createPortal(
        <>
            {/* 简洁遮罩 */}
            <div className="fixed inset-0 z-[100]" onClick={onClose} />

            {/* 命令面板 */}
            <div className="vscode-command-palette anti-theme z-[101]">
                <div className="bg-[var(--vscode-input-bg)] p-1">
                    <div className="px-2 py-1.5 text-xs text-[var(--vscode-fg-subtle)] font-bold uppercase tracking-wider border-b border-[var(--vscode-input-border)] mb-2">
                        {t('chapter.newChapterDialog')}
                    </div>

                    <div className="space-y-3 px-2 pb-3">
                        {/* 类型选择 */}
                        <div className="flex gap-1 bg-[var(--vscode-sidebar-bg)] p-1 rounded-[var(--radius-sm)]">
                            {[
                                { id: 'normal', label: t('chapter.typeNormal') },
                                { id: 'extra', label: t('chapter.typeExtra') },
                                { id: 'interlude', label: t('chapter.typeInterlude') }
                            ].map(tab => (
                                <button
                                    key={tab.id}
                                    onClick={() => setChapterType(tab.id)}
                                    className={cn(
                                        "flex-1 text-[11px] py-1 rounded-[var(--radius-sm)] transition-none",
                                        chapterType === tab.id
                                            ? "bg-[var(--vscode-bg)] text-[var(--vscode-fg)] shadow-sm font-medium"
                                            : "text-[var(--vscode-fg-subtle)] hover:text-[var(--vscode-fg)]"
                                    )}
                                >
                                    {tab.label}
                                </button>
                            ))}
                        </div>

                        {/* 分卷选择 */}
                        <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                            <label className="text-[11px] text-right text-[var(--vscode-fg-subtle)]">{t('chapter.volumeLabel')}</label>
                            <select
                                value={selectedVolume}
                                onChange={(e) => setSelectedVolume(e.target.value)}
                                className="w-full text-xs bg-[var(--vscode-input-bg)] border border-[var(--vscode-input-border)] px-2 py-1 outline-none focus:border-[var(--vscode-focus-border)]"
                            >
                                {availableVolumes.map(v => (
                                    <option key={v.id} value={v.id}>{v.id} - {v.title}</option>
                                ))}
                            </select>
                        </div>

                        {/* 插入位置 */}
                        {chapterType !== 'normal' && (
                            <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                                <label className="text-[11px] text-right text-[var(--vscode-fg-subtle)]">{t('chapter.insertAfterLabel')}</label>
                                <select
                                    value={insertAfter}
                                    onChange={(e) => setInsertAfter(e.target.value)}
                                    className="w-full text-xs bg-[var(--vscode-input-bg)] border border-[var(--vscode-input-border)] px-2 py-1 outline-none focus:border-[var(--vscode-focus-border)]"
                                >
                                    <option value="">{t('chapter.selectChapterOption')}</option>
                                    {normalChapters.map(c => (
                                        <option key={c.normalizedId} value={c.normalizedId}>{c.normalizedId} {c.title}</option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {/* 编号输入 */}
                        <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                            <label className="text-[11px] text-right text-[var(--vscode-fg-subtle)]">{t('chapter.numberLabel')}</label>
                            <div className="flex items-center gap-2">
                                <input
                                    value={customId}
                                    onChange={(e) => setCustomId(e.target.value.toUpperCase())}
                                    placeholder={suggestedId}
                                    className="w-24 text-xs font-mono bg-[var(--vscode-input-bg)] border border-[var(--vscode-input-border)] px-2 py-1 outline-none focus:border-[var(--vscode-focus-border)]"
                                />
                                <span className="text-[10px] text-[var(--vscode-fg-subtle)]">{t('chapter.resultLabel')}{finalId}</span>
                            </div>
                        </div>

                        {/* 标题输入 */}
                        <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                            <label className="text-[11px] text-right text-[var(--vscode-fg-subtle)]">{t('chapter.titleFieldLabel')}</label>
                            <input
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder={t('chapter.titlePlaceholder')}
                                className="w-full text-xs font-bold bg-[var(--vscode-input-bg)] border border-[var(--vscode-input-border)] px-2 py-1 outline-none focus:border-[var(--vscode-focus-border)]"
                                autoFocus
                            />
                        </div>
                    </div>

                    {/* 底部操作 */}
                    <div className="flex justify-end gap-2 p-2 border-t border-[var(--vscode-input-border)] bg-[var(--vscode-sidebar-bg)]">
                        <button
                            onClick={onClose}
                            className="px-3 py-1 text-xs border border-[var(--vscode-input-border)] bg-[var(--vscode-input-bg)] hover:bg-[var(--vscode-list-hover)]"
                        >
                            {t('common.cancel')}
                        </button>
                        <button
                            onClick={() => { if (canCreate) { onConfirm({ id: finalId, title, type: chapterType }); onClose(); } }}
                            disabled={!canCreate}
                            className="px-3 py-1 text-xs text-white bg-[var(--vscode-list-active)] hover:opacity-90 disabled:opacity-50"
                        >
                            {t('common.create')}
                        </button>
                    </div>
                </div>
            </div>
        </>,
        document.body
    )
}
