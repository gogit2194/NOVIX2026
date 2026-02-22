/**
 * 文枢 WenShape - 深度上下文感知的智能体小说创作系统
 * WenShape - Deep Context-Aware Agent-Based Novel Writing System
 *
 * Copyright © 2025-2026 WenShape Team
 * License: PolyForm Noncommercial License 1.0.0
 */

import React from 'react';
import { cn } from '../ui/core';
import { useLocale } from '../../i18n';

/**
 * 写作画布组件 - 正文展示与排版容器
 *
 * Provides a centered, distraction-free writing canvas with paper-like aesthetics.
 * Implements the "Calm & Focus" design language with proper typography and spacing.
 *
 * @component
 * @example
 * return (
 *   <WritingCanvas className="custom-class">
 *     <p>Chapter content goes here...</p>
 *   </WritingCanvas>
 * )
 *
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - 文章内容 / Article content to display
 * @param {string} [props.className] - 自定义样式类名 / Additional CSS classes
 * @param {Object} [props...props] - 其他DOM属性 / Other HTML attributes
 * @returns {JSX.Element} 包装后的写作画布 / Wrapped writing canvas element
 */
export const WritingCanvas = ({ children, className, ...props }) => {
    const { t } = useLocale();
    return (
        <div className="flex-1 h-full overflow-y-auto relative bg-[var(--vscode-bg)] scroll-smooth" {...props}>
            <div className={cn(
                "max-w-[850px] mx-auto min-h-screen my-8 p-12",
                className
            )}>
                {/*
                  ======================================================================
                  主文章容器 / Main article container
                  ======================================================================
                  使用 prose 类确保排版一致性，empty:before 提供空状态提示
                  Prose classes ensure consistent typography, empty:before provides hint
                */}
                <article className="prose prose-lg prose-slate max-w-none font-serif leading-relaxed text-[var(--vscode-fg)]">
                    {children}
                    {!children && (
                        <span className="text-[var(--vscode-fg-subtle)]">{t('writing.canvasEmpty')}</span>
                    )}
                </article>
            </div>

            {/* 下方填充：为滚动提供舒适的视觉空间 / Bottom padding for scroll comfort */}
            <div className="h-[30vh]" />
        </div>
    );
};
