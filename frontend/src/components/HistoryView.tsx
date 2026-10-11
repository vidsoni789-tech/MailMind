import React from 'react';
import { Clock } from 'lucide-react';
import { AuditLog } from '../types';

interface HistoryViewProps {
  logs: AuditLog[];
  loading: boolean;
}

export const HistoryView: React.FC<HistoryViewProps> = ({ logs, loading }) => {
  return (
    <div className="max-w-4xl mx-auto p-6 sm:p-8 space-y-6 select-none">
      <div className="border-b border-[#E7E4DC] pb-4">
        <h2 className="text-base font-semibold text-[#252821] flex items-center gap-2">
          <Clock className="w-4 h-4 text-[#4263EB]" />
          Audit Log & Action Trail
        </h2>
        <p className="text-xs text-[#74766F] mt-1">
          Historical record of AI generation, user approval decisions, and external write operations.
        </p>
      </div>

      {loading ? (
        <div className="p-12 text-center text-[#74766F] text-xs">
          Loading audit trail...
        </div>
      ) : logs.length === 0 ? (
        <div className="p-12 text-center text-[#74766F] text-xs bg-white rounded-xl border border-[#E7E4DC] shadow-card">
          No external actions recorded yet.
        </div>
      ) : (
        <div className="relative border-l-2 border-[#E7E4DC] ml-4 space-y-5 py-2">
          {logs.map((log) => {
            const isApproved = log.approval_status === 'approved';
            return (
              <div key={log.id} className="relative pl-6">
                {/* Timeline node */}
                <div
                  className={`absolute -left-[9px] top-1.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center shadow-sm ${
                    isApproved ? 'bg-[#23845B]' : 'bg-[#A66A12]'
                  }`}
                />

                <div className="p-4 rounded-xl bg-white border border-[#E7E4DC] space-y-2 shadow-card">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[#252821] uppercase tracking-wider font-mono">
                      {log.action.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] text-[#92938C] font-mono">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>

                  <p className="text-xs text-[#74766F]">
                    <span className="font-medium text-[#252821] mr-1">Target:</span>
                    {log.target_id || log.target_type}
                  </p>

                  {log.result && (
                    <p className="text-[11px] text-[#252821] bg-[#FBFAF7] border border-[#E7E4DC] p-2.5 rounded-lg font-mono">
                      {log.result}
                    </p>
                  )}

                  <div className="pt-1 flex items-center gap-2">
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-medium border ${
                        isApproved
                          ? 'bg-[#F0FDF4] text-[#23845B] border-[#DCFCE7]'
                          : 'bg-[#FEF8ED] text-[#A66A12] border-[#FCE6BE]'
                      }`}
                    >
                      Status: {log.approval_status}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
