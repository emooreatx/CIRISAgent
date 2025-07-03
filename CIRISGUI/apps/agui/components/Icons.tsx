/**
 * Shared icon components with consistent sizing
 * Use these components instead of inline SVGs to ensure consistent icon sizes across the app
 */

import React from 'react';

interface IconProps {
  className?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
}

const sizeMap = {
  xs: { width: 12, height: 12 },
  sm: { width: 16, height: 16 },
  md: { width: 20, height: 20 },
  lg: { width: 24, height: 24 },
};

export const InfoIcon: React.FC<IconProps> = ({ className = '', size = 'md' }) => {
  const { width, height } = sizeMap[size];
  return (
    <svg 
      className={className} 
      width={width} 
      height={height} 
      viewBox="0 0 20 20" 
      fill="currentColor"
    >
      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
    </svg>
  );
};

export const CheckCircleIcon: React.FC<IconProps> = ({ className = '', size = 'md' }) => {
  const { width, height } = sizeMap[size];
  return (
    <svg 
      className={className} 
      width={width} 
      height={height} 
      viewBox="0 0 20 20" 
      fill="currentColor"
    >
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
    </svg>
  );
};

export const ExclamationTriangleIcon: React.FC<IconProps> = ({ className = '', size = 'md' }) => {
  const { width, height } = sizeMap[size];
  return (
    <svg 
      className={className} 
      width={width} 
      height={height} 
      viewBox="0 0 20 20" 
      fill="currentColor"
    >
      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
    </svg>
  );
};

export const CubeIcon: React.FC<IconProps> = ({ className = '', size = 'md' }) => {
  const { width, height } = sizeMap[size];
  return (
    <svg 
      className={className} 
      width={width} 
      height={height} 
      viewBox="0 0 20 20" 
      fill="currentColor"
    >
      <path d="M11 17a1 1 0 001.447.894l4-2A1 1 0 0017 15V9.236a1 1 0 00-1.447-.894l-4 2a1 1 0 00-.553.894V17zM15.211 6.276a1 1 0 000-1.788l-4.764-2.382a1 1 0 00-.894 0L4.789 4.488a1 1 0 000 1.788l4.764 2.382a1 1 0 00.894 0l4.764-2.382zM4.447 8.342A1 1 0 003 9.236V15a1 1 0 00.553.894l4 2A1 1 0 009 17v-5.764a1 1 0 00-.553-.894l-4-2z" />
    </svg>
  );
};

export const SpinnerIcon: React.FC<IconProps> = ({ className = '', size = 'md' }) => {
  const { width, height } = sizeMap[size];
  return (
    <svg 
      className={`animate-spin ${className}`} 
      width={width} 
      height={height} 
      xmlns="http://www.w3.org/2000/svg" 
      fill="none" 
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
  );
};

export const StatusDot: React.FC<{ status: 'green' | 'yellow' | 'red' | 'gray'; className?: string }> = ({ 
  status, 
  className = '' 
}) => {
  const colorMap = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
    gray: 'bg-gray-500',
  };
  
  return (
    <span className={`w-3 h-3 rounded-full ${colorMap[status]} ${className}`}></span>
  );
};