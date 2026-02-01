import React, { useState } from 'react';
import { FileText, Plus, RefreshCw } from 'lucide-react';
import { useIDE } from '../../../context/IDEContext';
import { sessionAPI } from '../../../api';
import VolumeManager from '../VolumeManager';
import VolumeTree from '../VolumeTree';
import AnalysisSyncDialog from '../AnalysisSyncDialog';
import AnalysisReviewDialog from '../../writing/AnalysisReviewDialog';

/**
 * ExplorerPanel - 资源管理器面板
 * 仅展示分卷与章节结构。
 */
export default function ExplorerPanel() {
  const { state, dispatch } = useIDE();
  const [syncOpen, setSyncOpen] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewItems, setReviewItems] = useState([]);
  const [reviewSaving, setReviewSaving] = useState(false);

  const handleChapterClick = (chapter) => {
    const chapterId = typeof chapter === 'string' ? chapter : chapter.chapter;
    const chapterTitle = typeof chapter === 'string' ? '' : (chapter.title || '');
    dispatch({
      type: 'SET_ACTIVE_DOCUMENT',
      payload: {
        type: 'chapter',
        id: chapterId,
        data: { title: chapterTitle }
      }
    });
  };

  const handleSyncConfirm = async (chapterIds) => {
    if (!state.activeProjectId) return;
    setSyncLoading(true);
    try {
      const resp = await sessionAPI.analyzeBatch(state.activeProjectId, { chapters: chapterIds });
      const results = resp.data?.results || [];
      const analyses = results
        .filter((item) => item.success && item.analysis)
        .map((item) => ({ chapter: item.chapter, analysis: item.analysis }));
      if (analyses.length === 0) {
        throw new Error('未获取到可审阅的分析结果');
      }
      setReviewItems(analyses);
      setReviewOpen(true);
      setSyncOpen(false);
    } catch (error) {
      console.error(error);
      alert(`同步失败: ${error.message}`);
    } finally {
      setSyncLoading(false);
    }
  };

  const handleReviewSave = async (payload) => {
    if (!state.activeProjectId) return;
    setReviewSaving(true);
    try {
      const resp = await sessionAPI.saveAnalysisBatch(state.activeProjectId, {
        items: payload,
        overwrite: true,
      });
      if (!resp.data?.success) {
        throw new Error(resp.data?.error || '保存失败');
      }
      setReviewOpen(false);
      setReviewItems([]);
    } catch (error) {
      console.error(error);
      alert(`保存失败: ${error.message}`);
    } finally {
      setReviewSaving(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-border/50 flex items-center justify-between">
        <div className="flex items-center gap-2 text-ink-900 font-bold text-sm">
          <FileText size={14} className="text-primary" />
          <span>资源管理器</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <button
            onClick={() => setSyncOpen(true)}
            className="flex items-center gap-1 text-ink-500 hover:text-primary"
            title="分析同步"
          >
            <RefreshCw size={12} />
            分析同步
          </button>
          <button
            onClick={() =>
              dispatch({
                type: 'OPEN_CREATE_CHAPTER_DIALOG',
                payload: { volumeId: state.selectedVolumeId },
              })
            }
            className="flex items-center gap-1 text-primary hover:text-primary/80"
            title="新建章节"
          >
            <Plus size={12} />
            新建章节
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-4">
        <VolumeManager
          projectId={state.activeProjectId}
          onVolumeSelect={(volumeId) =>
            dispatch({ type: 'SET_SELECTED_VOLUME_ID', payload: volumeId })
          }
          onRefresh={() => {}}
        />

        <VolumeTree
          projectId={state.activeProjectId}
          onChapterSelect={handleChapterClick}
          selectedChapter={state.activeDocument?.id}
        />
      </div>

      <AnalysisSyncDialog
        open={syncOpen}
        projectId={state.activeProjectId}
        loading={syncLoading}
        onClose={() => setSyncOpen(false)}
        onConfirm={handleSyncConfirm}
      />

      <AnalysisReviewDialog
        open={reviewOpen}
        analyses={reviewItems}
        onCancel={() => setReviewOpen(false)}
        onSave={handleReviewSave}
        saving={reviewSaving}
      />
    </div>
  );
}
