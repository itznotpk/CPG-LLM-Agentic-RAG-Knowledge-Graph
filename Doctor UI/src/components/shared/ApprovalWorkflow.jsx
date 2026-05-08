import React, { useState } from 'react';
import { 
  FileEdit, 
  CheckCircle2, 
  XCircle,
  User, 
  ChevronDown,
  History,
  RefreshCw
} from 'lucide-react';
import { Badge, Button } from '../shared';
import { useTheme } from '../../context/ThemeContext';

// Workflow States - Simplified
export const WORKFLOW_STATES = {
  DRAFT: 'draft',
  APPROVED: 'approved',
  REJECTED: 'rejected'
};

const stateConfig = {
  [WORKFLOW_STATES.DRAFT]: {
    label: 'Pending Review',
    icon: FileEdit,
    color: 'bg-amber-100 text-amber-700 border-amber-200',
    dotColor: 'bg-amber-500',
    description: 'Awaiting approval'
  },
  [WORKFLOW_STATES.APPROVED]: {
    label: 'Approved',
    icon: CheckCircle2,
    color: 'bg-green-100 text-green-700 border-green-200',
    dotColor: 'bg-green-500',
    description: 'Ready to generate report'
  },
  [WORKFLOW_STATES.REJECTED]: {
    label: 'Rejected',
    icon: XCircle,
    color: 'bg-red-100 text-red-700 border-red-200',
    dotColor: 'bg-red-500',
    description: 'Needs regeneration'
  }
};

// Workflow Status Badge
export function WorkflowStatusBadge({ status, size = 'md' }) {
  const config = stateConfig[status] || stateConfig[WORKFLOW_STATES.DRAFT];
  const Icon = config.icon;
  
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5'
  };

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${config.color} ${sizeClasses[size]}`}>
      <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'} />
      {config.label}
    </span>
  );
}

// Workflow Actions Panel - Simplified
export function WorkflowActions({ 
  currentStatus, 
  onStatusChange, 
  onReject,
  onRegenerate,
  history = [],
  disabled = false 
}) {
  const { isDark } = useTheme();
  const [showHistory, setShowHistory] = useState(false);
  const [comment, setComment] = useState('');
  const [isRejected, setIsRejected] = useState(false);

  const handleApprove = () => {
    if (onStatusChange) {
      onStatusChange(WORKFLOW_STATES.APPROVED, comment);
      setComment('');
      setIsRejected(false);
    }
  };

  const handleReject = () => {
    if (onReject) {
      onReject(comment);
      setIsRejected(true);
    }
  };

  const handleRegenerate = () => {
    if (onRegenerate) {
      onRegenerate(comment);
      setComment('');
      setIsRejected(false);
    }
  };

  return (
    <div className={`backdrop-blur-sm rounded-xl border p-4 ${isDark ? 'bg-white/5 border-white/10' : 'bg-white/60 border-slate-200'}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className={`text-sm font-semibold flex items-center gap-2 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
          <FileEdit className="w-4 h-4 text-[var(--accent-primary)]" />
          Review & Approve
        </h3>
        <WorkflowStatusBadge status={isRejected ? WORKFLOW_STATES.REJECTED : currentStatus} size="sm" />
      </div>

      {/* Rejected State - Show Regenerate Option */}
      {isRejected && (
        <div className={`mb-4 p-4 rounded-lg ${isDark ? 'bg-red-500/10 border border-red-500/30' : 'bg-red-50 border border-red-200'}`}>
          <div className="flex items-start gap-3 mb-3">
            <XCircle className={`w-5 h-5 mt-0.5 ${isDark ? 'text-red-400' : 'text-red-600'}`} />
            <div>
              <p className={`text-sm font-medium ${isDark ? 'text-red-300' : 'text-red-800'}`}>Care Plan Rejected</p>
              <p className={`text-xs mt-1 ${isDark ? 'text-red-200/80' : 'text-red-700'}`}>
                Add feedback below and regenerate the care plan.
              </p>
            </div>
          </div>
          
          {/* Feedback for regeneration */}
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What should be changed? (e.g., 'Use alternative medication', 'More conservative approach')..."
            className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500/50 resize-none mb-3 ${
              isDark 
                ? 'bg-white/5 border-red-500/30 text-white placeholder-slate-500' 
                : 'bg-white/80 border-red-300 text-slate-800 placeholder-slate-400'
            }`}
            rows={2}
          />
          
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              icon={RefreshCw}
              onClick={handleRegenerate}
              disabled={disabled}
            >
              Regenerate Care Plan
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsRejected(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Normal State - Show Approve/Reject */}
      {!isRejected && currentStatus !== WORKFLOW_STATES.APPROVED && (
        <>
          {/* AI Feedback Info */}
          <div className={`mb-3 p-3 rounded-lg ${isDark ? 'bg-[var(--accent-primary)]/10' : 'bg-[var(--accent-primary)]/5'}`}>
            <p className={`text-xs ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              <span className="font-semibold">Help Improve AI Recommendations:</span> Your feedback helps our AI learn and provide better care plan recommendations.
            </p>
          </div>

          {/* Comment Input */}
          <div className="mb-4">
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add a comment (optional)..."
              className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 resize-none ${
                isDark 
                  ? 'bg-white/5 border-white/20 text-white placeholder-slate-500' 
                  : 'bg-white/80 border-slate-300 text-slate-800 placeholder-slate-400'
              }`}
              rows={2}
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant="success"
                size="sm"
                icon={CheckCircle2}
                onClick={handleApprove}
                disabled={disabled}
              >
                Approve
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={XCircle}
                onClick={handleReject}
                disabled={disabled}
              >
                Reject
              </Button>
            </div>
            
            {history.length > 0 && (
              <button
                onClick={() => setShowHistory(!showHistory)}
                className={`flex items-center gap-1 text-xs ${isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'}`}
              >
                <History className="w-3.5 h-3.5" />
                History ({history.length})
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
              </button>
            )}
          </div>
        </>
      )}

      {/* Approved State */}
      {currentStatus === WORKFLOW_STATES.APPROVED && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-green-600">
            <CheckCircle2 className="w-5 h-5" />
            <span className="text-sm font-medium">Care Plan Approved - Ready to Generate Report</span>
          </div>
          
          {history.length > 0 && (
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`flex items-center gap-1 text-xs ${isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <History className="w-3.5 h-3.5" />
              History ({history.length})
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
            </button>
          )}
        </div>
      )}

      {/* History */}
      {showHistory && history.length > 0 && (
        <div className={`mt-4 pt-4 border-t ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
          <div className="space-y-3">
            {history.map((item, index) => (
              <div key={index} className="flex items-start gap-3 text-sm">
                <div className={`p-1 rounded-full ${stateConfig[item.status]?.dotColor || 'bg-slate-400'}`}>
                  <div className="w-2 h-2" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className={`font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{item.action}</span>
                    <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>{item.timestamp}</span>
                  </div>
                  <div className={`flex items-center gap-2 text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    <User className="w-3 h-3" />
                    {item.user}
                  </div>
                  {item.comment && (
                    <p className={`text-xs mt-1 italic ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>"{item.comment}"</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Compact Workflow Indicator for List Items
export function WorkflowIndicator({ status, onClick }) {
  const config = stateConfig[status] || stateConfig[WORKFLOW_STATES.DRAFT];
  
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs ${config.color} hover:opacity-80 transition-opacity`}
      title={config.description}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
      {config.label}
    </button>
  );
}
