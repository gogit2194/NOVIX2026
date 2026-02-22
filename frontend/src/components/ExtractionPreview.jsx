import React from 'react';
import { Card } from './ui/core';
import { X } from 'lucide-react';
import { useLocale } from '../i18n';

/**
 * ExtractionPreview - 结构化提取预览
 * 展示写作过程中的实体与事实提取结果。
 */
export default function ExtractionPreview({ data, onClose }) {
  const { t } = useLocale();
  if (!data) return null;

  return (
    <Card className="p-4 bg-[var(--vscode-bg)] text-[var(--vscode-fg)] border border-[var(--vscode-sidebar-border)] rounded-[6px] shadow-none">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-[var(--vscode-fg)]">{t('extractionPreview.title')}</h3>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--vscode-list-hover)] rounded-[6px]"
          >
            <X size={20} className="text-[var(--vscode-fg-subtle)]" />
          </button>
        )}
      </div>

      <div className="space-y-3">
        {data.characters && data.characters.length > 0 && (
          <div>
            <h4 className="font-medium text-[var(--vscode-fg)] mb-2">{t('extractionPreview.characters')}</h4>
            <div className="space-y-1">
              {data.characters.map((char, idx) => (
                <div key={idx} className="text-sm text-[var(--vscode-fg-subtle)] pl-4">
                  • {char}
                </div>
              ))}
            </div>
          </div>
        )}

        {data.locations && data.locations.length > 0 && (
          <div>
            <h4 className="font-medium text-[var(--vscode-fg)] mb-2">{t('extractionPreview.worldviews')}</h4>
            <div className="space-y-1">
              {data.locations.map((loc, idx) => (
                <div key={idx} className="text-sm text-[var(--vscode-fg-subtle)] pl-4">
                  • {loc}
                </div>
              ))}
            </div>
          </div>
        )}

        {data.facts && data.facts.length > 0 && (
          <div>
            <h4 className="font-medium text-[var(--vscode-fg)] mb-2">{t('common.default')}</h4>
            <div className="space-y-1">
              {data.facts.map((fact, idx) => (
                <div key={idx} className="text-sm text-[var(--vscode-fg-subtle)] pl-4">
                  • {fact}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
