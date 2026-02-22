import React from 'react';
import { useLocale } from '../../i18n';

export function Logo({ size = 'default', showText = true }) {
  const sizeClasses = {
    small: 'text-lg',
    default: 'text-2xl',
    large: 'text-4xl',
  };

  return (
    <div className="flex items-center gap-2">
      {showText ? (
        <div className="flex flex-col leading-none">
          <span className={`brand-logo ${sizeClasses[size]} text-ink-900`}>
            文枢
          </span>
        </div>
      ) : null}
    </div>
  );
}

export function LogoFull({ className = '' }) {
  const { t } = useLocale();
  return (
    <div className={`flex flex-col items-center ${className}`}>
      <Logo size="large" />
      <span className="text-xs text-ink-400 mt-1 tracking-widest">
        {t('logo.subtitle')}
      </span>
    </div>
  );
}

export default Logo;
