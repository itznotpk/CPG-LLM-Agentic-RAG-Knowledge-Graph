import React from 'react';
import { CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

export function ProgressBar({ value, max = 100, variant = 'primary', className = '', showLabel = true }) {
  const { isDark } = useTheme();
  const percentage = Math.min((value / max) * 100, 100);

  const variants = {
    primary: 'bg-[var(--accent-primary)]',
    success: 'bg-green-500',
    danger: 'bg-red-500',
    warning: 'bg-amber-500',
    info: 'bg-blue-500',
  };

  const bgVariants = {
    primary: isDark ? 'bg-[var(--accent-primary)]/20' : 'bg-[var(--accent-primary)]/10',
    success: isDark ? 'bg-green-900/50' : 'bg-green-200',
    danger: isDark ? 'bg-red-900/50' : 'bg-red-200',
    warning: isDark ? 'bg-amber-900/50' : 'bg-amber-200',
    info: isDark ? 'bg-blue-900/50' : 'bg-blue-200',
  };

  return (
    <div className={`w-full ${className}`}>
      <div className={`h-2.5 rounded-full ${bgVariants[variant]} overflow-hidden`}>
        <div
          className={`h-full rounded-full ${variants[variant]} probability-bar transition-all duration-700`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <div className={`flex justify-between mt-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          <span>{value}%</span>
        </div>
      )}
    </div>
  );
}

export function ProbabilityBar({ label, probability, risk = 'low', className = '' }) {
  const { isDark } = useTheme();
  const riskColors = {
    high: 'danger',
    medium: 'warning',
    low: 'success',
  };

  return (
    <div className={`${className}`}>
      <div className="flex justify-between items-center mb-1">
        <span className={`text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{label}</span>
        <span className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-800'}`}>{probability}%</span>
      </div>
      <ProgressBar value={probability} variant={riskColors[risk]} showLabel={false} />
    </div>
  );
}

export function StepIndicator({ steps, currentStep, className = '' }) {
  const { isDark } = useTheme();
  
  return (
    <div className={`flex items-center justify-center gap-2 ${className}`}>
      {steps.map((step, index) => {
        const stepNumber = index + 1;
        const isActive = stepNumber === currentStep;
        const isCompleted = stepNumber < currentStep;

        return (
          <React.Fragment key={step.id || stepNumber}>
            <div className="flex flex-col items-center">
              <div
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center
                  font-semibold text-sm transition-all duration-300
                  ${isCompleted
                    ? 'bg-green-500 text-white'
                    : isActive
                      ? 'bg-[var(--accent-primary)] text-white shadow-lg shadow-[var(--accent-primary)]/30'
                      : isDark 
                        ? 'bg-white/10 text-slate-400 border border-white/20'
                        : 'bg-white/50 text-slate-500 border border-slate-300'
                  }
                `}
              >
                {isCompleted ? <CheckCircle className="w-5 h-5" /> : stepNumber}
              </div>
              <span
                className={`
                  mt-2 text-xs font-medium
                  ${isActive 
                    ? (isDark ? 'text-white' : 'text-slate-800')
                    : (isDark ? 'text-slate-400' : 'text-slate-600')
                  }
                `}
              >
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`
                  w-12 h-0.5 mb-6
                  ${isCompleted ? 'bg-green-500' : (isDark ? 'bg-[var(--accent-primary)]/30' : 'bg-[var(--accent-primary)]/20')}
                `}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export function LoadingSpinner({ size = 'md', className = '' }) {
  const sizes = {
    sm: 'w-5 h-5',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className={`${sizes[size]} ${className}`}>
      <svg
        className="animate-spin text-[var(--accent-primary)]"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  );
}

// Skeleton Loader Components
export function Skeleton({ className = '', variant = 'text' }) {
  const { isDark } = useTheme();
  const baseClasses = `animate-pulse rounded ${isDark ? 'bg-slate-700/60' : 'bg-slate-200/60'}`;
  
  const variants = {
    text: 'h-4 w-full',
    title: 'h-6 w-3/4',
    avatar: 'h-12 w-12 rounded-full',
    button: 'h-10 w-24 rounded-xl',
    card: 'h-32 w-full rounded-xl',
    badge: 'h-6 w-20 rounded-full',
  };

  return <div className={`${baseClasses} ${variants[variant]} ${className}`} />;
}

export function SkeletonCard({ className = '' }) {
  const { isDark } = useTheme();
  
  return (
    <div className={`backdrop-blur-xl border rounded-2xl p-5 ${isDark ? 'bg-white/5 border-white/10' : 'bg-white/40 border-white/30'} ${className}`}>
      <div className="flex items-center gap-3 mb-4">
        <Skeleton variant="avatar" className="w-10 h-10" />
        <div className="flex-1">
          <Skeleton variant="title" className="mb-2" />
          <Skeleton variant="text" className="w-1/2" />
        </div>
      </div>
      <div className="space-y-3">
        <Skeleton variant="text" />
        <Skeleton variant="text" className="w-5/6" />
        <Skeleton variant="text" className="w-4/6" />
      </div>
    </div>
  );
}

export function SkeletonDiagnosis({ className = '' }) {
  const { isDark } = useTheme();
  
  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header skeleton */}
      <div className="text-center">
        <Skeleton variant="title" className="mx-auto mb-2" />
        <Skeleton variant="text" className="w-2/3 mx-auto" />
      </div>
      
      {/* Main diagnosis card skeleton */}
      <div className={`backdrop-blur-xl border-2 rounded-2xl p-6 ${isDark ? 'bg-white/5 border-[var(--accent-primary)]/30' : 'bg-white/40 border-[var(--accent-primary)]/20'}`}>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <Skeleton variant="avatar" className="w-12 h-12" />
            <div>
              <Skeleton variant="text" className="w-24 mb-2" />
              <Skeleton variant="title" className="w-64" />
            </div>
          </div>
          <Skeleton variant="badge" />
        </div>
        <div className="flex gap-3 mb-4">
          <Skeleton variant="badge" className="w-28" />
          <Skeleton variant="badge" className="w-24" />
        </div>
        <Skeleton variant="card" className="h-20" />
      </div>
      
      {/* Differential list skeleton */}
      <div className={`backdrop-blur-xl border rounded-2xl p-6 ${isDark ? 'bg-white/5 border-white/10' : 'bg-white/40 border-white/30'}`}>
        <div className="flex items-center gap-3 mb-5">
          <Skeleton variant="avatar" className="w-9 h-9" />
          <div>
            <Skeleton variant="title" className="w-40 mb-1" />
            <Skeleton variant="text" className="w-56" />
          </div>
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-white/30'}`}>
              <div className="flex items-center gap-3 mb-2">
                <Skeleton variant="avatar" className="w-6 h-6" />
                <Skeleton variant="text" className="flex-1" />
                <Skeleton variant="badge" />
              </div>
              <div className="ml-9">
                <Skeleton variant="text" className="h-2.5" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SkeletonCarePlan({ className = '' }) {
  const { isDark } = useTheme();
  
  return (
    <div className={`space-y-4 ${className}`}>
      {[1, 2, 3].map((i) => (
        <div key={i} className={`backdrop-blur-xl border rounded-2xl overflow-hidden ${isDark ? 'bg-white/5 border-white/10' : 'bg-white/40 border-white/30'}`}>
          <div className="p-4 flex items-center gap-3">
            <Skeleton variant="avatar" className="w-9 h-9" />
            <Skeleton variant="title" className="w-48" />
          </div>
          <div className="px-4 pb-4 space-y-3">
            {[1, 2].map((j) => (
              <div key={j} className={`p-4 rounded-xl ${isDark ? 'bg-white/5' : 'bg-white/30'}`}>
                <div className="flex justify-between mb-2">
                  <Skeleton variant="text" className="w-48" />
                  <Skeleton variant="badge" />
                </div>
                <Skeleton variant="text" className="w-3/4" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
