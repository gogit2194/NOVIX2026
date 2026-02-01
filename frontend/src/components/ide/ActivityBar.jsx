import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useIDE } from '../../context/IDEContext';
import {
  Files,
  BookOpen,
  Bot,
  Library,
  Info,
  X,
  Lightbulb,
} from 'lucide-react';
import { cn } from '../../components/ui/core';

export function ActivityBar() {
  const { state, dispatch } = useIDE();
  const [showLicense, setShowLicense] = useState(false);

  const icons = [
    { id: 'explorer', icon: Files, label: '资源管理器' },
    { id: 'facts', icon: Lightbulb, label: '事实全典' },
    { id: 'cards', icon: BookOpen, label: '设定卡片' },
    { id: 'fanfiction', icon: Library, label: '同人导入' },
    { id: 'agents', icon: Bot, label: '智能体' },
  ];

  const activeIndex = icons.findIndex((item) => item.id === state.activeActivity);

  return (
    <>
      <div className="w-12 flex flex-col items-center py-2 bg-surface/80 border-r border-border backdrop-blur-sm z-30">
        <div className="flex-1 space-y-1 relative">
          {activeIndex !== -1 && state.sidePanelVisible && (
            <motion.div
              className="absolute left-1 w-10 h-10 bg-primary/10 rounded-md"
              initial={false}
              animate={{ top: `${activeIndex * 44 + 4}px` }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
          )}

          {icons.map((item) => (
            <ActivityItem
              key={item.id}
              icon={item.icon}
              label={item.label}
              isActive={state.activeActivity === item.id && state.sidePanelVisible}
              onClick={() => dispatch({ type: 'SET_ACTIVE_PANEL', payload: item.id })}
            />
          ))}
        </div>

        <button
          onClick={() => setShowLicense(true)}
          title="版权声明"
          className={cn(
            'w-10 h-10 flex items-center justify-center rounded-md transition-all duration-200 group relative z-10',
            'text-ink-400 hover:text-ink-900'
          )}
        >
          <Info size={20} strokeWidth={2} />
        </button>
      </div>

      <AnimatePresence>
        {showLicense && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowLicense(false)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-surface rounded-lg shadow-2xl border border-border max-w-3xl w-full max-h-[80vh] overflow-hidden"
            >
              <div className="flex items-center justify-between p-4 border-b border-border">
                <div>
                  <h2 className="text-xl font-bold text-ink-900">版权声明</h2>
                  <p className="text-xs text-ink-500 mt-0.5">Copyright & License</p>
                </div>
                <button
                  onClick={() => setShowLicense(false)}
                  className="p-2 hover:bg-ink-100 rounded-lg transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="p-6 overflow-y-auto max-h-[calc(80vh-80px)]">
                <div className="prose prose-sm max-w-none">
                  <pre className="whitespace-pre-wrap text-xs leading-relaxed font-mono bg-ink-50 p-4 rounded-lg border border-border">
                    {`PolyForm Noncommercial License 1.0.0

https://polyformproject.org/licenses/noncommercial/1.0.0

1. Purpose

The purpose of this license is to allow the software to be used for noncommercial purposes, while reserving the right to use the software for commercial purposes for the licensor.

2. Agreement

In order to receive this license, you must agree to its rules. The rules of this license are both obligations (like a contract) and conditions (like a copyright license). You must not do anything with this software that triggers a rule that you cannot or will not follow.

3. License Grant

The licensor grants you a copyright license for the software to do everything you might do with the software that would otherwise infringe the licensor's copyright in it for any noncommercial purpose.

4. Noncommercial Purposes

Noncommercial purposes include:
*   Use for personal use, including personal research, experimentation, and testing
*   Use by a non-profit organization, such as a charity or a school, for disjoint charitable or educational purposes
*   Use for testing and evaluation of the software

Any other use is a commercial purpose. Commercial purposes strictly prohibited include, but are not limited to:
*   Use by any for-profit entity for any purpose
*   Use in any commercial product or service
*   Use for any business operation or commercial workflow
*   Distribution as part of a paid product or service

5. Notices

You must ensure that anyone who gets a copy of any part of this software from you also gets a copy of this license.

6. No Other Rights

This license does not imply any rights other than those expressly granted.

7. Disclaimer

AS FAR AS THE LAW ALLOWS, THIS SOFTWARE COMES AS IS, WITHOUT ANY WARRANTY OR CONDITION, AND THE LICENSOR WILL NOT BE LIABLE TO YOU FOR ANY DAMAGES ARISING OUT OF THIS LICENSE OR THE USE OF THIS SOFTWARE.

---
COPYRIGHT NOTICE
---
Copyright (c) 2026 丁逸飞 (Ding Yifei) <1467673018@qq.com>

All Rights Reserved.
STRICTLY NO COMMERCIAL USE WITHOUT WRITTEN PERMISSION.
禁止一切未经书面授权的商业使用。Commercial Licensing Contact / 商业授权联系:
Email: 1467673018@qq.com
GitHub: https://github.com/unitagain`}
                  </pre>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function ActivityItem({ icon: Icon, label, isActive, onClick }) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={cn(
        'w-10 h-10 flex items-center justify-center rounded-md transition-all duration-200 group relative z-10',
        isActive ? 'text-primary' : 'text-ink-400 hover:text-ink-900'
      )}
    >
      <Icon size={20} strokeWidth={isActive ? 2.5 : 2} />
      {isActive && (
        <motion.div
          layoutId="activity-indicator"
          className="absolute left-0 top-2 bottom-2 w-[3px] bg-primary rounded-r-full"
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        />
      )}
    </button>
  );
}
