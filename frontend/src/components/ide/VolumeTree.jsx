import React, { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import { ChevronDown, ChevronRight, FolderOpen } from 'lucide-react';
import { draftsAPI, volumesAPI } from '../../api';
import { useIDE } from '../../context/IDEContext';
import { cn } from '../ui/core';

/**
 * VolumeTree - 分卷/章节树
 */
const VolumeTree = ({ projectId, onChapterSelect, selectedChapter }) => {
  const { state, dispatch } = useIDE();
  const [expandedVolumes, setExpandedVolumes] = useState(new Set());

  const { data: volumes = [], isLoading: volumesLoading } = useSWR(
    projectId ? [projectId, 'volumes'] : null,
    () => volumesAPI.list(projectId).then((res) => res.data),
    { revalidateOnFocus: false }
  );

  const { data: summaries = [], isLoading: summariesLoading } = useSWR(
    projectId ? [projectId, 'chapter-summaries'] : null,
    () => draftsAPI.listSummaries(projectId).then((res) => res.data),
    { revalidateOnFocus: false }
  );

  const { data: chapters = [], isLoading: chaptersLoading } = useSWR(
    projectId ? [projectId, 'chapters'] : null,
    () => draftsAPI.listChapters(projectId).then((res) => res.data || []),
    { revalidateOnFocus: false }
  );

  const getChapterWeight = (chapterId) => {
    const normalized = (chapterId || '').toUpperCase();
    const match = normalized.match(/^(?:V(\d+))?C(\d+)(?:([EI])(\d+))?$/);
    if (!match) return 0;
    const volume = match[1] ? Number.parseInt(match[1], 10) : 0;
    const chapter = Number.parseInt(match[2], 10);
    const type = match[3];
    const seq = match[4] ? Number.parseInt(match[4], 10) : 0;
    let weight = volume * 1000 + chapter;
    if (type && seq) {
      weight += 0.1 * seq;
    }
    return weight;
  };

  const { volumeList, chaptersByVolume } = useMemo(() => {
    const grouped = {};
    volumes.forEach((volume) => {
      grouped[volume.id] = [];
    });

    const summaryMap = new Map();
    summaries.forEach((summary) => summaryMap.set(summary.chapter, summary));
    const chapterSet = new Set(chapters);

    const normalizedChapters = chapters.map((chapterId) => {
      const summary = summaryMap.get(chapterId);
      if (summary) {
        return summary;
      }
      const volumeMatch = chapterId.match(/^V(\d+)/i);
      const volumeId = volumeMatch ? `V${volumeMatch[1]}` : 'V1';
      return {
        chapter: chapterId,
        title: chapterId,
        word_count: 0,
        volume_id: volumeId,
      };
    });

    summaries.forEach((summary) => {
      if (!chapterSet.has(summary.chapter)) {
        normalizedChapters.push(summary);
      }
    });

    normalizedChapters.forEach((summary) => {
      const volumeId = summary.volume_id || 'V1';
      if (!grouped[volumeId]) {
        grouped[volumeId] = [];
      }
      grouped[volumeId].push(summary);
    });

    Object.keys(grouped).forEach((volumeId) => {
      grouped[volumeId].sort((a, b) => getChapterWeight(a.chapter) - getChapterWeight(b.chapter));
    });

    const list = [...volumes];
    list.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    return { volumeList: list, chaptersByVolume: grouped };
  }, [volumes, summaries, chapters]);

  useEffect(() => {
    if (!volumeList.length) {
      return;
    }
    if (!state.selectedVolumeId || !volumeList.find((item) => item.id === state.selectedVolumeId)) {
      dispatch({ type: 'SET_SELECTED_VOLUME_ID', payload: volumeList[0].id });
    }
  }, [dispatch, state.selectedVolumeId, volumeList]);

  const toggleVolume = (volumeId) => {
    const next = new Set(expandedVolumes);
    if (next.has(volumeId)) {
      next.delete(volumeId);
    } else {
      next.add(volumeId);
    }
    setExpandedVolumes(next);
    dispatch({ type: 'SET_SELECTED_VOLUME_ID', payload: volumeId });
  };

  if (volumesLoading || summariesLoading || chaptersLoading) {
    return <div className="px-3 py-4 text-xs text-ink-400">加载章节中...</div>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <div className="text-xs font-bold text-ink-500 uppercase tracking-wider">章节</div>
      </div>

      <div className="space-y-2">
        {volumeList.length === 0 ? (
          <div className="p-4 text-center text-xs text-ink-400 border border-dashed border-border rounded">
            暂无分卷
          </div>
        ) : (
          volumeList.map((volume) => {
            const isExpanded = expandedVolumes.has(volume.id);
            const isSelected = state.selectedVolumeId === volume.id;
            const chaptersForVolume = chaptersByVolume[volume.id] || [];

            return (
              <div
                key={volume.id}
                className={cn(
                  'border rounded bg-surface',
                  isSelected ? 'border-primary/50 shadow-sm' : 'border-border'
                )}
              >
                <button
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-2 text-left transition-colors',
                    isSelected ? 'bg-primary/5' : 'hover:bg-ink-50'
                  )}
                  onClick={() => toggleVolume(volume.id)}
                >
                  {isExpanded ? (
                    <ChevronDown size={14} className="text-ink-400" />
                  ) : (
                    <ChevronRight size={14} className="text-ink-400" />
                  )}
                  <FolderOpen size={14} className="text-primary" />
                  <span className="text-[10px] font-mono text-primary">{volume.id}</span>
                  <span className="text-xs text-ink-800 truncate flex-1">{volume.title}</span>
                  <span className="text-[10px] text-ink-400">{chaptersForVolume.length}</span>
                </button>

                {isExpanded && (
                  <div className="border-t border-border/70 bg-ink-50/40">
                    {chaptersForVolume.length ? (
                      chaptersForVolume.map((chapter) => (
                        <button
                          key={chapter.chapter}
                          className={cn(
                            'w-full flex items-center gap-2 px-4 py-2 text-left text-xs transition-colors border-l-2',
                            selectedChapter === chapter.chapter
                              ? 'bg-primary/10 border-primary text-primary'
                              : 'border-transparent hover:bg-ink-100 text-ink-700'
                          )}
                          onClick={() => onChapterSelect?.(chapter)}
                        >
                          <span className="font-mono text-[10px]">{chapter.chapter}</span>
                          <span className="truncate flex-1">
                            {chapter.title || chapter.chapter}
                          </span>
                          {chapter.word_count ? (
                            <span className="text-[10px] text-ink-400">
                              {chapter.word_count} 字
                            </span>
                          ) : null}
                        </button>
                      ))
                    ) : (
                      <div className="px-4 py-3 text-xs text-ink-400">暂无章节</div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default VolumeTree;
