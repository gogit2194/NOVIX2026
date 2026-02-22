import { useLocale } from '../../i18n';

/**
 * LanguageSwitch - 语言切换按钮
 *
 * 点击在中文（zh-CN）与英文（en-US）间切换界面语言。
 * 切换结果通过 localStorage 持久化，并通过 useLocale Hook 触发全局重渲染。
 *
 * @component
 */
export default function LanguageSwitch() {
  const { locale, setLocale } = useLocale();
  const isZh = locale === 'zh-CN';

  return (
    <button
      onClick={() => setLocale(isZh ? 'en-US' : 'zh-CN')}
      className="px-2 py-1 text-xs text-[var(--vscode-fg-subtle)] hover:text-[var(--vscode-fg)] hover:bg-[var(--vscode-list-hover)] rounded-[4px] transition-colors leading-none"
      title={isZh ? 'Switch to English' : '切换为中文'}
    >
      {isZh ? 'EN' : '中'}
    </button>
  );
}
