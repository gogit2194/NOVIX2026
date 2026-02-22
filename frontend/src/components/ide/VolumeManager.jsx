/**
 * 文枢 WenShape - 深度上下文感知的智能体小说创作系统
 * WenShape - Deep Context-Aware Agent-Based Novel Writing System
 *
 * Copyright © 2025-2026 WenShape Team
 * License: PolyForm Noncommercial License 1.0.0
 *
 * 模块说明 / Module Description:
 *   分卷管理组件 - 展示项目分卷列表，支持创建/编辑/删除操作
 *   Volume manager component for listing and managing project volumes (parts/books).
 */

import React, { useState } from 'react';
import useSWR from 'swr';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { volumesAPI } from '../../api';
import { cn } from '../ui/core';
import logger from '../../utils/logger';
import { useLocale } from '../../i18n';

/**
 * 分卷管理组件 - 小说分卷（部分、章节集合）的创建和编辑
 *
 * Component for managing volumes (parts or books) within a project.
 * Supports creating, editing, and deleting volumes (V1 is not deletable).
 *
 * @component
 * @example
 * return (
 *   <VolumeManager
 *     projectId="proj-001"
 *     onVolumeSelect={handleSelect}
 *     onRefresh={handleRefresh}
 *   />
 * )
 *
 * @param {Object} props - Component props
 * @param {string} [props.projectId] - 项目ID / Project identifier
 * @param {Function} [props.onVolumeSelect] - 选择分卷回调 / Callback on volume selection
 * @param {Function} [props.onRefresh] - 刷新回调 / Callback on refresh
 * @returns {JSX.Element} 分卷管理组件 / Volume manager element
 */
const VolumeManager = ({ projectId, onVolumeSelect, onRefresh }) => {
  const { t } = useLocale();
  const [isCreating, setIsCreating] = useState(false);
  const [editingVolume, setEditingVolume] = useState(null);
  const [newVolume, setNewVolume] = useState({ title: '', summary: '' });

  const { data: volumes = [], mutate, isLoading } = useSWR(
    projectId ? [projectId, 'volumes'] : null,
    () => volumesAPI.list(projectId).then((res) => res.data),
    { revalidateOnFocus: false }
  );

  const handleCreateVolume = async () => {
    if (!newVolume.title.trim()) {
      alert(t('volume.titleRequired'));
      return;
    }

    try {
      const response = await volumesAPI.create(projectId, newVolume);
      mutate([...volumes, response.data]);
      setNewVolume({ title: '', summary: '' });
      setIsCreating(false);
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to create volume:', error);
      alert(t('volume.createFailed'));
    }
  };

  const handleUpdateVolume = async () => {
    if (!editingVolume?.title?.trim()) {
      alert(t('volume.titleRequired'));
      return;
    }

    try {
      const response = await volumesAPI.update(projectId, editingVolume.id, {
        title: editingVolume.title,
        summary: editingVolume.summary,
        order: editingVolume.order,
      });
      mutate(volumes.map((volume) => (volume.id === editingVolume.id ? response.data : volume)));
      setEditingVolume(null);
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to update volume:', error);
      alert(t('volume.updateFailed'));
    }
  };

  const handleDeleteVolume = async (volumeId) => {
    if (volumeId === 'V1') {
      alert(t('volume.v1CannotDelete'));
      return;
    }
    if (!window.confirm(t('volume.deleteConfirm'))) {
      return;
    }

    try {
      await volumesAPI.delete(projectId, volumeId);
      mutate(volumes.filter((volume) => volume.id !== volumeId));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to delete volume:', error);
      alert(t('volume.deleteFailed'));
    }
  };

  if (isLoading) {
    return <div className="text-xs text-[var(--vscode-fg-subtle)] px-3 py-4">{t('common.loading')}</div>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <div className="text-xs font-bold text-[var(--vscode-fg-subtle)] uppercase tracking-wider">{t('volume.sectionTitle')}</div>
        <button
          className="inline-flex items-center gap-1 text-xs text-[var(--vscode-fg)] hover:text-[var(--vscode-fg)] transition-colors"
          onClick={() => setIsCreating(true)}
        >
          <Plus size={12} /> {t('common.new')}
        </button>
      </div>

      <div className="space-y-1.5">
        {volumes.length === 0 ? (
          <div className="p-3 text-center text-xs text-[var(--vscode-fg-subtle)] border border-dashed border-[var(--vscode-sidebar-border)] rounded-[6px]">
            {t('volume.empty')}
          </div>
        ) : (
          volumes.map((volume) => (
            <div
              key={volume.id}
              className="flex items-center justify-between gap-2 px-3 py-2 border border-[var(--vscode-sidebar-border)] rounded-[6px] bg-[var(--vscode-bg)] hover:bg-[var(--vscode-list-hover)] transition-colors"
            >
              <button
                className="flex-1 min-w-0 text-left"
                onClick={() => onVolumeSelect?.(volume.id)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-[var(--vscode-fg-subtle)]">{volume.id}</span>
                  <span className="text-xs font-semibold text-[var(--vscode-fg)] truncate">{volume.title}</span>
                </div>
                {volume.summary && (
                  <div className="text-[11px] text-[var(--vscode-fg-subtle)] mt-0.5 line-clamp-1">{volume.summary}</div>
                )}
              </button>
              <div className="flex items-center gap-1">
                <button
                  className="p-2 rounded-[6px] hover:bg-[var(--vscode-list-hover)] text-[var(--vscode-fg-subtle)] hover:text-[var(--vscode-fg)] transition-colors"
                  onClick={() => setEditingVolume(volume)}
                  title={t('common.edit')}
                >
                  <Pencil size={14} />
                </button>
                <button
                  className={cn(
                    'p-2 rounded-[6px] transition-colors',
                    volume.id === 'V1' ? 'text-[var(--vscode-fg-subtle)] cursor-not-allowed' : 'hover:bg-red-50 text-red-500'
                  )}
                  onClick={() => handleDeleteVolume(volume.id)}
                  title={volume.id === 'V1' ? t('volume.v1CannotDelete') : t('common.delete')}
                  disabled={volume.id === 'V1'}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {isCreating && (
        <Modal
          title={t('volume.createTitle')}
          onClose={() => setIsCreating(false)}
          onConfirm={handleCreateVolume}
          confirmText={t('volume.create')}
        >
          <InputField
            label={t('volume.titleLabel')}
            value={newVolume.title}
            onChange={(value) => setNewVolume({ ...newVolume, title: value })}
            placeholder={t('volume.titlePlaceholder')}
          />
          <TextAreaField
            label={t('volume.summaryLabel')}
            value={newVolume.summary}
            onChange={(value) => setNewVolume({ ...newVolume, summary: value })}
            placeholder={t('volume.summaryPlaceholder')}
          />
        </Modal>
      )}

      {editingVolume && (
        <Modal
          title={t('volume.editTitle')}
          onClose={() => setEditingVolume(null)}
          onConfirm={handleUpdateVolume}
          confirmText={t('common.save')}
        >
          <InputField
            label={t('volume.titleLabel')}
            value={editingVolume.title}
            onChange={(value) => setEditingVolume({ ...editingVolume, title: value })}
          />
          <TextAreaField
            label={t('volume.summaryLabel')}
            value={editingVolume.summary || ''}
            onChange={(value) => setEditingVolume({ ...editingVolume, summary: value })}
          />
        </Modal>
      )}
    </div>
  );
};

const Modal = ({ title, onClose, onConfirm, confirmText, children }) => {
  const { t } = useLocale();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 anti-theme">
      <div className="w-full max-w-md glass-panel border border-[var(--vscode-sidebar-border)] rounded-[6px] overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--vscode-sidebar-border)] flex items-center justify-between bg-[var(--vscode-sidebar-bg)]">
          <div className="text-sm font-bold text-[var(--vscode-fg)]">{title}</div>
          <button
            className="p-2 rounded-[6px] text-[var(--vscode-fg-subtle)] hover:text-[var(--vscode-fg)] hover:bg-[var(--vscode-list-hover)] transition-colors"
            onClick={onClose}
            title={t('common.close')}
          >
            X
          </button>
        </div>
        <div className="p-4 space-y-3">{children}</div>
        <div className="px-4 py-3 border-t border-[var(--vscode-sidebar-border)] bg-[var(--vscode-sidebar-bg)] flex justify-end gap-2">
          <button
            className="px-3 py-2 text-sm rounded-[6px] border border-[var(--vscode-input-border)] text-[var(--vscode-fg)] hover:bg-[var(--vscode-list-hover)] transition-colors"
            onClick={onClose}
          >
            {t('common.cancel')}
          </button>
          <button
            className="px-3 py-2 text-sm rounded-[6px] bg-[var(--vscode-list-active)] text-[var(--vscode-list-active-fg)] hover:opacity-90 transition-colors"
            onClick={onConfirm}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

const InputField = ({ label, value, onChange, placeholder }) => {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-semibold text-[var(--vscode-fg-subtle)] uppercase">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm rounded-[6px] border border-[var(--vscode-input-border)] bg-[var(--vscode-input-bg)] text-[var(--vscode-fg)] focus:outline-none focus:ring-1 focus:ring-[var(--vscode-focus-border)] focus:border-[var(--vscode-focus-border)]"
      />
    </label>
  );
};

const TextAreaField = ({ label, value, onChange, placeholder }) => {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-semibold text-[var(--vscode-fg-subtle)] uppercase">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm rounded-[6px] border border-[var(--vscode-input-border)] bg-[var(--vscode-input-bg)] text-[var(--vscode-fg)] focus:outline-none focus:ring-1 focus:ring-[var(--vscode-focus-border)] focus:border-[var(--vscode-focus-border)] resize-none"
        rows={4}
      />
    </label>
  );
};

export default VolumeManager;
