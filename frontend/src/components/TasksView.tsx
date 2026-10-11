import React, { useState } from 'react';
import {
  CheckSquare,
  Square,
  Trash2,
  Calendar,
  Plus,
  Search,
  Filter,
  Mail,
  Clock,
  CheckCircle2,
  X,
  ArrowUpRight,
} from 'lucide-react';
import { Task } from '../types';

interface TasksViewProps {
  tasks: Task[];
  onToggleStatus: (taskId: string, currentStatus: 'pending' | 'completed') => void;
  onDeleteTask: (taskId: string) => void;
  onCreateTask?: (taskData: {
    title: string;
    deadline?: string;
    priority: string;
    source_from?: string;
  }) => Promise<void>;
  onNavigateToEmail?: (threadId: string, emailFrom?: string) => void;
  loading: boolean;
}

export const TasksView: React.FC<TasksViewProps> = ({
  tasks,
  onToggleStatus,
  onDeleteTask,
  onCreateTask,
  onNavigateToEmail,
  loading,
}) => {
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'completed'>('all');
  const [priorityFilter, setPriorityFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  // New task form state
  const [newTitle, setNewTitle] = useState('');
  const [newDeadline, setNewDeadline] = useState('');
  const [newPriority, setNewPriority] = useState('medium');
  const [newSourceFrom, setNewSourceFrom] = useState('');
  const [creating, setCreating] = useState(false);

  const filteredTasks = tasks.filter((t) => {
    if (statusFilter !== 'all' && t.status !== statusFilter) return false;
    if (priorityFilter !== 'all' && t.priority.toLowerCase() !== priorityFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = t.title.toLowerCase().includes(q);
      const matchText = (t.source_text || '').toLowerCase().includes(q);
      const matchFrom = (t.source_from || '').toLowerCase().includes(q);
      if (!matchTitle && !matchText && !matchFrom) return false;
    }
    return true;
  });

  const pendingCount = tasks.filter((t) => t.status === 'pending').length;
  const highPriorityPending = tasks.filter(
    (t) => t.status === 'pending' && t.priority.toLowerCase() === 'high'
  ).length;
  const completedCount = tasks.filter((t) => t.status === 'completed').length;

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !onCreateTask) return;
    setCreating(true);
    try {
      await onCreateTask({
        title: newTitle.trim(),
        deadline: newDeadline.trim() || undefined,
        priority: newPriority,
        source_from: newSourceFrom.trim() || undefined,
      });
      setNewTitle('');
      setNewDeadline('');
      setNewPriority('medium');
      setNewSourceFrom('');
      setShowAddModal(false);
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-6 sm:p-8 space-y-6 select-none">
      {/* Header & Stats Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#E7E4DC] pb-5">
        <div>
          <h2 className="text-base font-semibold text-[#252821] flex items-center gap-2">
            <CheckSquare className="w-4 h-4 text-[#4263EB]" />
            Action Center & Commitments
          </h2>
          <p className="text-xs text-[#74766F] mt-1">
            Deadlines, extracted commitments, and follow-up tasks from your email threads.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <span className="px-2.5 py-1 rounded-lg bg-white border border-[#E7E4DC] text-[#74766F] shadow-sm">
              {pendingCount} Pending
            </span>
            {highPriorityPending > 0 && (
              <span className="px-2.5 py-1 rounded-lg bg-[#FDF2F2] border border-[#F8D7D7] text-[#C24141] font-medium">
                {highPriorityPending} High Priority
              </span>
            )}
            <span className="px-2.5 py-1 rounded-lg bg-[#F0FDF4] border border-[#DCFCE7] text-[#23845B] font-medium">
              {completedCount} Done
            </span>
          </div>

          <button
            onClick={() => setShowAddModal(true)}
            className="h-9 px-3 rounded-lg bg-[#4263EB] hover:bg-[#3451D1] text-white text-xs font-medium flex items-center gap-1.5 transition whitespace-nowrap shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Add Task</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-[#E7E4DC] shadow-card">
        {/* Status Tabs */}
        <div className="flex items-center gap-1 bg-[#FBFAF7] p-1 rounded-lg border border-[#E7E4DC] text-xs">
          <button
            onClick={() => setStatusFilter('all')}
            className={`h-7 px-3 rounded-md transition font-medium whitespace-nowrap ${
              statusFilter === 'all'
                ? 'bg-white text-[#4263EB] shadow-sm border border-[#E7E4DC]'
                : 'text-[#74766F] hover:text-[#252821]'
            }`}
          >
            All ({tasks.length})
          </button>
          <button
            onClick={() => setStatusFilter('pending')}
            className={`h-7 px-3 rounded-md transition font-medium whitespace-nowrap ${
              statusFilter === 'pending'
                ? 'bg-white text-[#4263EB] shadow-sm border border-[#E7E4DC]'
                : 'text-[#74766F] hover:text-[#252821]'
            }`}
          >
            Pending ({pendingCount})
          </button>
          <button
            onClick={() => setStatusFilter('completed')}
            className={`h-7 px-3 rounded-md transition font-medium whitespace-nowrap ${
              statusFilter === 'completed'
                ? 'bg-white text-[#4263EB] shadow-sm border border-[#E7E4DC]'
                : 'text-[#74766F] hover:text-[#252821]'
            }`}
          >
            Completed ({completedCount})
          </button>
        </div>

        {/* Priority Filter */}
        <div className="flex items-center gap-1.5 text-xs text-[#74766F]">
          <Filter className="w-3.5 h-3.5" />
          <span>Priority:</span>
          {(['all', 'high', 'medium', 'low'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPriorityFilter(p)}
              className={`h-7 px-2 rounded-md text-xs capitalize transition ${
                priorityFilter === p
                  ? 'bg-[#EAEFFF] text-[#4263EB] border border-[#D0DBFF] font-medium'
                  : 'text-[#74766F] hover:text-[#252821]'
              }`}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative min-w-[200px]">
          <Search className="w-3.5 h-3.5 text-[#74766F] absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 bg-[#FBFAF7] border border-[#E7E4DC] rounded-lg pl-8 pr-3 text-xs text-[#252821] placeholder-[#92938C] focus:bg-white focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition"
          />
        </div>
      </div>

      {/* Task List Content */}
      {loading ? (
        <div className="p-12 text-center text-[#74766F] text-xs flex items-center justify-center gap-2">
          <Clock className="w-4 h-4 animate-spin text-[#4263EB]" />
          Loading action items...
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="p-12 text-center text-[#74766F] text-xs bg-white rounded-xl border border-[#E7E4DC] space-y-2 shadow-card">
          <CheckCircle2 className="w-8 h-8 text-[#92938C]/50 mx-auto" />
          <p className="font-medium text-[#252821]">No tasks match your filter</p>
          <p className="text-[#92938C] max-w-sm mx-auto">
            Ask the AI assistant: "Extract deadlines and tasks from my recent emails" or click Add Task above.
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {filteredTasks.map((task) => {
            const isCompleted = task.status === 'completed';
            const isHigh = task.priority.toLowerCase() === 'high';
            return (
              <div
                key={task.id}
                className={`p-4 rounded-xl border transition-all flex items-start justify-between gap-4 ${
                  isCompleted
                    ? 'bg-[#FBFAF7] border-[#E7E4DC] opacity-70'
                    : isHigh
                    ? 'bg-white border-[#E7E4DC] border-l-4 border-l-[#C24141] shadow-card hover:border-[#D6D2C4]'
                    : 'bg-white border-[#E7E4DC] shadow-card hover:border-[#D6D2C4]'
                }`}
              >
                <div className="flex items-start space-x-3.5 flex-1 min-w-0">
                  <button
                    onClick={() => onToggleStatus(task.id, task.status)}
                    className="mt-0.5 text-[#74766F] hover:text-[#23845B] transition"
                    title={isCompleted ? 'Mark Pending' : 'Mark Completed'}
                  >
                    {isCompleted ? (
                      <CheckSquare className="w-4 h-4 text-[#23845B]" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>

                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3
                        className={`text-xs font-semibold ${
                          isCompleted ? 'line-through text-[#92938C]' : 'text-[#252821]'
                        }`}
                      >
                        {task.title}
                      </h3>

                      <span
                        className={`px-2 py-0.2 rounded text-[10px] uppercase font-mono font-medium ${
                          task.priority.toLowerCase() === 'high'
                            ? 'bg-[#FDF2F2] text-[#C24141] border border-[#F8D7D7]'
                            : task.priority.toLowerCase() === 'medium'
                            ? 'bg-[#FEF8ED] text-[#A66A12] border border-[#FCE6BE]'
                            : 'bg-[#EAEFFF] text-[#4263EB] border border-[#D0DBFF]'
                        }`}
                      >
                        {task.priority} Priority
                      </span>
                    </div>

                    {task.source_text && (
                      <p className="text-[11px] text-[#74766F] italic bg-[#FBFAF7] p-2.5 rounded-lg border border-[#E7E4DC]">
                        "{task.source_text}"
                      </p>
                    )}

                    <div className="flex items-center gap-4 pt-0.5 text-[11px] text-[#74766F] flex-wrap">
                      {task.deadline && (
                        <span className="flex items-center gap-1 text-[#A66A12] font-mono font-medium">
                          <Calendar className="w-3.5 h-3.5" />
                          Due: {task.deadline}
                        </span>
                      )}

                      {task.source_from && (
                        <span className="flex items-center gap-1 text-[#74766F]">
                          <Mail className="w-3.5 h-3.5" />
                          From: {task.source_from}
                        </span>
                      )}

                      {task.thread_id && task.thread_id !== 'manual' && onNavigateToEmail && (
                        <button
                          onClick={() => onNavigateToEmail(task.thread_id, task.source_from)}
                          className="flex items-center gap-1 text-[#4263EB] hover:underline font-medium transition cursor-pointer"
                        >
                          <span>View source email</span>
                          <ArrowUpRight className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => onDeleteTask(task.id)}
                  className="p-1.5 rounded-lg text-[#74766F] hover:text-[#C24141] hover:bg-[#FDF2F2] transition flex-shrink-0"
                  title="Delete task"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Manual Task Creation Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white border border-[#E7E4DC] rounded-xl w-full max-w-md shadow-dropdown p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#E7E4DC] pb-3">
              <h3 className="text-sm font-semibold text-[#252821] flex items-center gap-2">
                <Plus className="w-4 h-4 text-[#4263EB]" />
                Create Action Item
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-[#74766F] hover:text-[#252821] transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-[#74766F] font-medium mb-1">
                  Task Title <span className="text-[#C24141]">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Send updated budget proposal"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] placeholder-[#92938C] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#74766F] font-medium mb-1">
                    Deadline / Date
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Tomorrow, 5 PM"
                    value={newDeadline}
                    onChange={(e) => setNewDeadline(e.target.value)}
                    className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] placeholder-[#92938C] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
                  />
                </div>

                <div>
                  <label className="block text-[#74766F] font-medium mb-1">
                    Priority
                  </label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                    className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
                  >
                    <option value="high">High Priority</option>
                    <option value="medium">Medium Priority</option>
                    <option value="low">Low Priority</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[#74766F] font-medium mb-1">
                  Source Contact (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. alex@example.com"
                  value={newSourceFrom}
                  onChange={(e) => setNewSourceFrom(e.target.value)}
                  className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] placeholder-[#92938C] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#E7E4DC]">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="h-9 px-3.5 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] border border-[#E7E4DC] bg-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newTitle.trim()}
                  className="h-9 px-4 rounded-lg bg-[#4263EB] hover:bg-[#3451D1] text-white font-medium transition disabled:opacity-50 shadow-sm"
                >
                  {creating ? 'Saving...' : 'Create Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
