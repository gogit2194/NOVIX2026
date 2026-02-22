/**
 * 文枢 WenShape - 深度上下文感知的智能体小说创作系统
 * WenShape - Deep Context-Aware Agent-Based Novel Writing System
 *
 * Copyright © 2025-2026 WenShape Team
 * License: PolyForm Noncommercial License 1.0.0
 *
 * 模块说明 / Module Description:
 *   角色卡片视图 - 展示角色列表和角色编辑表单，支持增删改查操作
 *   Character view for displaying character list and edit form with CRUD operations.
 */

import React, { useState, useEffect } from 'react';
import { Card, Button, Input } from '../ui/core';
import { Plus, User, X, Save } from 'lucide-react';
import { useLocale } from '../../i18n';

/**
 * 字符规范化函数 / Character normalization helper
 * @param {*} value - 要规范化的值 / Value to normalize
 * @returns {number} 规范化后的星级 / Normalized star rating
 */
const normalizeStars = (value) => {
  const parsed = parseInt(value, 10);
  if (Number.isNaN(parsed)) return 1;
  return Math.max(1, Math.min(parsed, 3));
};

/**
 * 格式化别名函数 / Format aliases helper
 * @param {*} value - 别名值 / Aliases value
 * @returns {string} 格式化后的别名字符串 / Formatted aliases string
 */
const formatAliases = (value) => {
  if (Array.isArray(value)) return value.filter(Boolean).join('，');
  return value || '';
};

/**
 * 解析别名函数 / Parse aliases helper
 * @param {string} value - 别名文本 / Aliases text
 * @returns {Array} 解析后的别名数组 / Parsed aliases array
 */
const parseAliases = (value) => {
  return String(value || '')
    .split(/[,，;；\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
};

/**
 * 角色卡片视图组件 - 展示和编辑角色卡片信息
 *
 * Component for displaying character cards and providing edit form interface.
 * Manages character list display, sorting, and inline editing capabilities.
 *
 * @component
 * @example
 * return (
 *   <CharacterView
 *     characters={[{ id: '001', name: '张三', stars: 2 }]}
 *     onEdit={handleEdit}
 *     onSave={handleSave}
 *     editing="ch001"
 *     editingCharacter={editData}
 *     onCancel={handleCancel}
 *   />
 * )
 *
 * @param {Object} props - Component props
 * @param {Array} [props.characters=[]] - 角色列表 / Character list
 * @param {Function} [props.onEdit] - 编辑回调 / Edit callback
 * @param {Function} [props.onSave] - 保存回调 / Save callback
 * @param {string|null} [props.editing=null] - 编辑中的角色ID / Character ID being edited
 * @param {Object|null} [props.editingCharacter=null] - 编辑中的角色数据 / Character data being edited
 * @param {Function} [props.onCancel] - 取消编辑回调 / Cancel edit callback
 * @returns {JSX.Element} 角色卡片视图 / Character view element
 */
export function CharacterView({ characters, onEdit, onSave, editing, editingCharacter, onCancel }) {
  const { t } = useLocale();
  const activeEditing = editing || editingCharacter || null;
  const handleCancel = onCancel || (() => onEdit?.(null));
  const sortedCharacters = React.useMemo(() => {
    const list = Array.isArray(characters) ? characters.slice() : [];
    list.sort((a, b) => {
      const starDiff = normalizeStars(b?.stars) - normalizeStars(a?.stars);
      if (starDiff !== 0) return starDiff;
      return String(a?.name || '').localeCompare(String(b?.name || ''), undefined, { numeric: true, sensitivity: 'base' });
    });
    return list;
  }, [characters]);
  const [formData, setFormData] = useState({
    name: '',
    aliases: '',
    description: '',
    stars: 1
  });

  useEffect(() => {
    if (activeEditing) {
      setFormData({
        name: activeEditing.name || '',
        aliases: formatAliases(activeEditing.aliases),
        description: activeEditing.description || '',
        stars: normalizeStars(activeEditing.stars)
      });
    } else {
      setFormData({
        name: '',
        aliases: '',
        description: '',
        stars: 1
      });
    }
  }, [activeEditing]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const aliases = parseAliases(formData.aliases);
    const uniqueAliases = Array.from(new Set(aliases));
    const payload = {
      name: (formData.name || '').trim(),
      aliases: uniqueAliases,
      description: (formData.description || '').trim(),
      stars: normalizeStars(formData.stars)
    };
    onSave(payload);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-140px)]">
      <div className="lg:col-span-4 flex flex-col gap-4 overflow-hidden">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-bold text-[var(--vscode-fg)]">{t('card.charSectionTitle')}</h3>
          <Button size="sm" onClick={() => onEdit({})}>
            <Plus size={16} className="mr-2" /> {t('common.new')}
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-3 pr-2">
          {sortedCharacters.map((char) => (
            <div
              key={char.name}
              onClick={() => onEdit(char)}
              className={`p-4 rounded-[6px] border cursor-pointer transition-colors ${
                activeEditing?.name === char.name
                  ? 'bg-[var(--vscode-list-active)] text-[var(--vscode-list-active-fg)] border-[var(--vscode-input-border)]'
                  : 'bg-[var(--vscode-bg)] border-[var(--vscode-sidebar-border)] text-[var(--vscode-fg-subtle)] hover:bg-[var(--vscode-list-hover)] hover:text-[var(--vscode-fg)]'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold font-serif text-lg">{char.name}</span>
                <div className="flex items-center gap-2 text-[10px] opacity-80">
                  <span>{t('card.starsLabel').replace('{count}', normalizeStars(char.stars))}</span>
                  <User size={14} className="opacity-70" />
                </div>
              </div>
              <div className={`text-xs opacity-90 line-clamp-2 ${activeEditing?.name === char.name ? 'text-[var(--vscode-list-active-fg)]' : 'text-[var(--vscode-fg-subtle)]'}`}>
                {char.description || t('card.noDesc')}
              </div>
              {Array.isArray(char.aliases) && char.aliases.length > 0 && (
                <div className={`mt-2 text-[10px] opacity-80 line-clamp-1 ${activeEditing?.name === char.name ? 'text-[var(--vscode-list-active-fg)]' : 'text-[var(--vscode-fg-subtle)]'}`}>
                  {t('card.aliasesPrefix')}{char.aliases.join('、')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <Card className="lg:col-span-8 bg-[var(--vscode-bg)] border border-[var(--vscode-sidebar-border)] rounded-[6px] overflow-hidden flex flex-col shadow-none">
        {activeEditing ? (
          <div className="flex-1 flex flex-col">
            <div className="flex flex-row items-center justify-between p-6 border-b border-[var(--vscode-sidebar-border)] bg-[var(--vscode-sidebar-bg)]">
              <h3 className="font-bold text-lg text-[var(--vscode-fg)] flex items-center gap-2">
                <User className="text-[var(--vscode-fg-subtle)]" size={18} />
                {activeEditing.name ? t('card.editTitle').replace('{name}', activeEditing.name) : t('card.newChar')}
              </h3>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={handleCancel}>
                  <X size={16} />
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-8">
              <form id="char-form" onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-[var(--vscode-fg-subtle)] uppercase">{t('card.fieldName')}</label>
                  <Input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder={t('card.charNamePlaceholder')}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-[var(--vscode-fg-subtle)] uppercase">{t('card.fieldStars')}</label>
                  <select
                    value={formData.stars}
                    onChange={(e) => setFormData({ ...formData, stars: normalizeStars(e.target.value) })}
                    className="w-full h-10 px-3 rounded-[6px] border border-[var(--vscode-input-border)] bg-[var(--vscode-input-bg)] text-sm text-[var(--vscode-fg)] focus-visible:outline-none focus-visible:border-[var(--vscode-focus-border)] transition-colors"
                  >
                    <option value={3}>{t('card.stars3')}</option>
                    <option value={2}>{t('card.stars2')}</option>
                    <option value={1}>{t('card.stars1')}</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-[var(--vscode-fg-subtle)] uppercase">{t('card.fieldAliases')}</label>
                  <Input
                    type="text"
                    value={formData.aliases || ''}
                    onChange={(e) => setFormData({ ...formData, aliases: e.target.value })}
                    placeholder={t('card.aliasesPlaceholder')}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-[var(--vscode-fg-subtle)] uppercase">{t('card.fieldDescription')}</label>
                  <textarea
                    className="flex min-h-[200px] w-full rounded-[6px] border border-[var(--vscode-input-border)] bg-[var(--vscode-input-bg)] px-3 py-2 text-sm text-[var(--vscode-fg)] placeholder:text-[var(--vscode-fg-subtle)] focus-visible:outline-none focus-visible:border-[var(--vscode-focus-border)] transition-colors"
                    value={formData.description || ''}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder={t('card.charDescPlaceholder')}
                  />
                </div>
              </form>
            </div>
            <div className="p-4 border-t border-[var(--vscode-sidebar-border)] bg-[var(--vscode-sidebar-bg)] flex justify-end gap-3">
              <Button variant="ghost" onClick={handleCancel}>{t('common.cancel')}</Button>
              <Button form="char-form" type="submit">
                <Save size={16} className="mr-2" /> {t('card.saveChar')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-[var(--vscode-fg-subtle)]">
            <User size={64} className="mb-4 opacity-20" />
            <div className="font-serif text-lg">{t('card.selectCharHint')}</div>
          </div>
        )}
      </Card>
    </div>
  );
}
