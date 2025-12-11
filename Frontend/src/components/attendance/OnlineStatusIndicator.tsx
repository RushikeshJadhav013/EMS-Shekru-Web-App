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
      {/* Simple status dot - no animations */}
      <div
        className={`${dotSize} rounded-full transition-colors duration-300 ${
          isOnline
            ? 'bg-green-500'
            : 'bg-gray-400 dark:bg-gray-600'
        }`}
      />
      
      {showLabel && (
        <span
          className={`text-xs font-medium ${
            isOnline
              ? 'text-green-600 dark:text-green-400'
              : 'text-gray-500 dark:text-gray-400'
          }`}
        >
          {isOnline ? 'Online' : 'Offline'}
        </span>
      )}
    </div>
  );
};

export default OnlineStatusIndicator;
