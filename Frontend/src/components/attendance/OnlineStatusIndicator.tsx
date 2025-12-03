import React from 'react';

interface OnlineStatusIndicatorProps {
  isOnline: boolean;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export const OnlineStatusIndicator: React.FC<OnlineStatusIndicatorProps> = ({
  isOnline,
  size = 'md',
  showLabel = false
}) => {
  const sizeClasses = {
    sm: 'h-2 w-2',
    md: 'h-3 w-3',
    lg: 'h-4 w-4'
  };

  const dotSize = sizeClasses[size];

  return (
    <div className="flex items-center gap-1.5">
      <div className="relative flex items-center justify-center">
        {/* Outer glow ring for online status */}
        {isOnline && (
          <div className={`absolute ${dotSize} rounded-full bg-green-400 opacity-75 animate-ping`} />
        )}
        
        {/* Main status dot */}
        <div
          className={`relative ${dotSize} rounded-full transition-all duration-300 ${
            isOnline
              ? 'bg-green-500 shadow-lg shadow-green-500/50 animate-pulse'
              : 'bg-slate-400 dark:bg-slate-600'
          }`}
        />
      </div>
      
      {showLabel && (
        <span
          className={`text-xs font-medium ${
            isOnline
              ? 'text-green-600 dark:text-green-400'
              : 'text-slate-500 dark:text-slate-400'
          }`}
        >
          {isOnline ? 'Online' : 'Offline'}
        </span>
      )}
    </div>
  );
};

export default OnlineStatusIndicator;
