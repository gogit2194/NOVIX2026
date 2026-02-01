import React from 'react';
import { useIDE } from '../../context/IDEContext';
import ExplorerPanel from './panels/ExplorerPanel';
import CardsPanel from './panels/CardsPanel';
import AgentsPanel from './panels/AgentsPanel';
import FanfictionPanel from './panels/FanfictionPanel';
import FactsEncyclopedia from './FactsEncyclopedia';

export const SidePanel = () => {
  const { state, dispatch } = useIDE();
  const { sidePanelVisible, activeActivity, sidePanelWidth } = state;

  const titleMap = {
    explorer: '资源管理器',
    facts: '事实全典',
    cards: '设定卡片',
    fanfiction: '同人导入',
    agents: '智能体',
  };

  if (!sidePanelVisible) return null;

  return (
    <div
      className="h-full border-r border-border bg-surface flex flex-col relative group"
      style={{ width: sidePanelWidth, minWidth: 160, maxWidth: 600 }}
    >
      <div className="h-9 px-4 flex items-center justify-between border-b border-border/50 bg-surface text-xs font-bold uppercase tracking-wider text-ink-500 select-none flex-shrink-0">
        <span>{titleMap[activeActivity] || activeActivity.toUpperCase()}</span>
      </div>

      <div className="flex-1 overflow-hidden h-full flex flex-col">
        <div className="flex-1 overflow-hidden min-h-0 relative">
          {activeActivity === 'explorer' && <ExplorerPanel />}
          {activeActivity === 'facts' && (
            <div className="h-full overflow-hidden">
              <FactsEncyclopedia />
            </div>
          )}
          {activeActivity === 'cards' && <CardsPanel />}
          {activeActivity === 'agents' && <AgentsPanel mode="config" />}
          {activeActivity === 'fanfiction' && <FanfictionPanel />}
        </div>
      </div>

      <div
        className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/50 transition-colors z-50"
        onMouseDown={(e) => {
          e.preventDefault();
          const startX = e.pageX;
          const startWidth = sidePanelWidth;

          const handleMouseMove = (moveEvent) => {
            const newWidth = Math.max(160, Math.min(600, startWidth + (moveEvent.pageX - startX)));
            dispatch({ type: 'SET_PANEL_WIDTH', payload: newWidth });
          };

          const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
          };

          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
        }}
      />
    </div>
  );
};
