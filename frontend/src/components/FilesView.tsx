import React, { useState, useEffect } from 'react';
import {
  Paperclip,
  FileText,
  Upload,
  RefreshCw,
  Trash2,
  Search,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  FileArchive,
  Image,
  Tag,
  X,
  Folder,
  FolderPlus,
  HardDrive,
} from 'lucide-react';
import { IndexedFile, ConnectedDirectory } from '../types';
import { api } from '../api';

export const FilesView: React.FC = () => {
  const [files, setFiles] = useState<IndexedFile[]>([]);
  const [directories, setDirectories] = useState<ConnectedDirectory[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanningAll, setScanningAll] = useState(false);
  const [scanningDirId, setScanningDirId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDirFilter, setSelectedDirFilter] = useState<string>('all');
  const [statusBanner, setStatusBanner] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  // Connect folder modal/form state
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [customPath, setCustomPath] = useState('');
  const [customLabel, setCustomLabel] = useState('');
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [filesRes, dirsRes] = await Promise.all([
        api.getFiles(),
        api.getDirectories(),
      ]);
      setFiles(filesRes.files || []);
      setDirectories(dirsRes.directories || []);
    } catch (e: any) {
      console.error('Failed to load files and directories:', e);
      setStatusBanner({ type: 'error', message: 'Failed to load indexed files and directories.' });
    } finally {
      setLoading(false);
    }
  };

  const handleConnectFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customPath.trim()) return;

    setConnecting(true);
    setStatusBanner(null);
    try {
      const res = await api.connectDirectory(customPath.trim(), customLabel.trim() || undefined);
      setDirectories(res.directories || []);
      setFiles(res.files || []);
      setShowConnectModal(false);
      setCustomPath('');
      setCustomLabel('');
      setStatusBanner({
        type: 'success',
        message: `Successfully connected "${res.directory.label || res.directory.dir_path}". Indexed ${res.directory.indexed_now ?? 0} files.`,
      });
    } catch (err: any) {
      console.error('Connect directory error:', err);
      setStatusBanner({
        type: 'error',
        message: err.message || 'Could not connect directory. Verify the folder path exists on your laptop.',
      });
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnectFolder = async (dir: ConnectedDirectory) => {
    if (!confirm(`Disconnect "${dir.label || dir.dir_path}"? This will remove its files from the PersonalMail index.`)) {
      return;
    }

    try {
      const res = await api.disconnectDirectory(dir.id, true);
      setDirectories(res.directories || []);
      setFiles(res.files || []);
      setStatusBanner({
        type: 'info',
        message: `Disconnected folder "${dir.label || dir.dir_path}". Removed from indexed search.`,
      });
    } catch (err: any) {
      console.error('Disconnect directory error:', err);
      setStatusBanner({ type: 'error', message: err.message || 'Failed to disconnect directory.' });
    }
  };

  const handleScanSingleDirectory = async (dirId: string, label: string) => {
    setScanningDirId(dirId);
    setStatusBanner(null);
    try {
      const res = await api.scanDirectoryById(dirId);
      setDirectories(res.directories || []);
      setFiles(res.files || []);
      setStatusBanner({
        type: 'success',
        message: `Scanned "${label}": indexed ${res.newly_indexed} new/updated document(s). Total: ${res.total_files}.`,
      });
    } catch (err: any) {
      console.error('Scan error:', err);
      setStatusBanner({ type: 'error', message: err.message || 'Failed to scan directory.' });
    } finally {
      setScanningDirId(null);
    }
  };

  const handleScanAllDirectories = async () => {
    setScanningAll(true);
    setStatusBanner(null);
    try {
      const res = await api.scanAllDirectories();
      setDirectories(res.directories || []);
      setFiles(res.files || []);
      setStatusBanner({
        type: 'success',
        message: `Scan complete: crawled ${res.directories_scanned} folder(s), indexed ${res.newly_indexed} new/updated file(s). Total: ${res.total_files}.`,
      });
    } catch (e: any) {
      console.error('Scan all error:', e);
      setStatusBanner({ type: 'error', message: 'Failed to scan all directories.' });
    } finally {
      setScanningAll(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (!selected || selected.length === 0) return;

    setUploading(true);
    setStatusBanner(null);
    try {
      let uploadedCount = 0;
      for (let i = 0; i < selected.length; i++) {
        await api.uploadFile(selected[i]);
        uploadedCount++;
      }
      await loadAll();
      setStatusBanner({
        type: 'success',
        message: `Successfully uploaded and indexed ${uploadedCount} file(s).`,
      });
    } catch (err: any) {
      console.error('Upload error:', err);
      setStatusBanner({ type: 'error', message: `Upload failed: ${err.message || 'Unknown error'}` });
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteFile = async (fileId: string, filename: string) => {
    if (!confirm(`Remove "${filename}" from indexed attachments?`)) return;
    try {
      await api.deleteFile(fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      setStatusBanner({ type: 'info', message: `Removed "${filename}" from indexed documents.` });
    } catch (e: any) {
      console.error('Delete error:', e);
      setStatusBanner({ type: 'error', message: 'Failed to remove file.' });
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf':
        return <FileText className="w-4 h-4 text-[#C24141]" />;
      case 'docx':
      case 'doc':
        return <FileText className="w-4 h-4 text-[#4263EB]" />;
      case 'xlsx':
      case 'xls':
      case 'csv':
        return <FileSpreadsheet className="w-4 h-4 text-[#23845B]" />;
      case 'zip':
        return <FileArchive className="w-4 h-4 text-[#A66A12]" />;
      case 'png':
      case 'jpg':
      case 'jpeg':
        return <Image className="w-4 h-4 text-[#7C3AED]" />;
      default:
        return <FileText className="w-4 h-4 text-[#74766F]" />;
    }
  };

  // Filter files by search keyword and directory selection
  const filteredFiles = files.filter((f) => {
    const matchesSearch =
      f.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (f.tags && f.tags.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (f.file_path && f.file_path.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;
    if (selectedDirFilter === 'all') return true;

    return (
      (f.directory_path && f.directory_path.toLowerCase() === selectedDirFilter.toLowerCase()) ||
      (f.file_path && f.file_path.toLowerCase().startsWith(selectedDirFilter.toLowerCase()))
    );
  });

  return (
    <div className="max-w-5xl mx-auto p-6 sm:p-8 space-y-6 select-none">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-[#E7E4DC] pb-4 flex-wrap gap-4">
        <div>
          <h2 className="text-base font-semibold text-[#252821] flex items-center gap-2">
            <Paperclip className="w-4 h-4 text-[#4263EB]" />
            Document and Attachment Repository
          </h2>
          <p className="text-xs text-[#74766F] mt-1">
            Connect local folders or drives across your laptop so PersonalMail AI can scan, rank, and suggest matching files when drafting email replies.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {/* Connect custom folder button */}
          <button
            onClick={() => setShowConnectModal(true)}
            className="h-9 px-3.5 rounded-lg text-xs font-medium bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] flex items-center gap-1.5 transition whitespace-nowrap shadow-sm"
            title="Connect any folder or drive from your laptop"
          >
            <FolderPlus className="w-3.5 h-3.5 text-[#4263EB]" />
            <span>Connect Folder</span>
          </button>

          {/* Scan all directories button */}
          <button
            onClick={handleScanAllDirectories}
            disabled={scanningAll}
            className="h-9 px-3 rounded-lg text-xs font-medium bg-white border border-[#E7E4DC] text-[#252821] hover:bg-[#F0EEE7] flex items-center gap-1.5 transition whitespace-nowrap shadow-sm disabled:opacity-50"
            title="Scan all connected directories for new or modified files"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#74766F] ${scanningAll ? 'animate-spin' : ''}`} />
            <span>{scanningAll ? 'Scanning All...' : 'Scan All Folders'}</span>
          </button>

          {/* Upload Document Button */}
          <label className="h-9 px-3.5 rounded-lg text-xs font-medium bg-[#4263EB] hover:bg-[#3451D1] text-white cursor-pointer transition flex items-center gap-1.5 whitespace-nowrap shadow-sm">
            <Upload className="w-3.5 h-3.5" />
            <span>{uploading ? 'Uploading...' : 'Upload File'}</span>
            <input
              type="file"
              multiple
              onChange={handleFileUpload}
              className="hidden"
              accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.zip,.png,.jpg,.jpeg"
            />
          </label>
        </div>
      </div>

      {/* Status banner */}
      {statusBanner && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center justify-between ${
            statusBanner.type === 'success'
              ? 'bg-[#F0FDF4] border-[#DCFCE7] text-[#23845B]'
              : statusBanner.type === 'error'
              ? 'bg-[#FDF2F2] border-[#F8D7D7] text-[#C24141]'
              : 'bg-white border-[#E7E4DC] text-[#74766F]'
          }`}
        >
          <div className="flex items-center space-x-2">
            {statusBanner.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-[#23845B]" />
            ) : statusBanner.type === 'error' ? (
              <AlertCircle className="w-4 h-4 text-[#C24141]" />
            ) : (
              <Paperclip className="w-4 h-4 text-[#4263EB]" />
            )}
            <span>{statusBanner.message}</span>
          </div>
          <button
            onClick={() => setStatusBanner(null)}
            className="text-[#74766F] hover:text-[#252821] p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Connect Folder Dialog / Modal */}
      {showConnectModal && (
        <div className="p-4 sm:p-5 rounded-xl bg-white border border-[#4263EB]/30 shadow-card space-y-4 ring-1 ring-[#4263EB]/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FolderPlus className="w-4 h-4 text-[#4263EB]" />
              <h3 className="text-xs font-semibold text-[#252821]">Connect Custom Folder or Drive</h3>
            </div>
            <button
              onClick={() => setShowConnectModal(false)}
              className="text-[#74766F] hover:text-[#252821] p-1 rounded-md"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-xs text-[#74766F]">
            Enter any folder or drive path on your laptop (e.g. <code className="font-mono bg-[#FBFAF7] px-1 py-0.5 rounded border border-[#E7E4DC]">D:\Documents</code>, <code className="font-mono bg-[#FBFAF7] px-1 py-0.5 rounded border border-[#E7E4DC]">C:\Users\Vidhansh\Desktop\Reports</code>, or <code className="font-mono bg-[#FBFAF7] px-1 py-0.5 rounded border border-[#E7E4DC]">D:\College</code>). PersonalMail AI will scan and index all supported documents inside it.
          </p>

          <form onSubmit={handleConnectFolder} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="md:col-span-2 space-y-1">
                <label className="text-[11px] font-medium text-[#252821] block">
                  Folder / Drive Path <span className="text-[#C24141]">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={customPath}
                  onChange={(e) => setCustomPath(e.target.value)}
                  placeholder="e.g. D:\Documents or C:\Users\Vidhansh\OneDrive"
                  className="w-full h-9 bg-[#FBFAF7] border border-[#E7E4DC] rounded-lg px-3 text-xs text-[#252821] placeholder-[#92938C] focus:bg-white focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-medium text-[#252821] block">
                  Friendly Label <span className="text-[#92938C] font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={customLabel}
                  onChange={(e) => setCustomLabel(e.target.value)}
                  placeholder="e.g. Work Documents"
                  className="w-full h-9 bg-[#FBFAF7] border border-[#E7E4DC] rounded-lg px-3 text-xs text-[#252821] placeholder-[#92938C] focus:bg-white focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setShowConnectModal(false)}
                className="h-8 px-3 rounded-lg text-xs font-medium text-[#74766F] hover:bg-[#F0EEE7] transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={connecting || !customPath.trim()}
                className="h-8 px-4 rounded-lg text-xs font-medium bg-[#4263EB] hover:bg-[#3451D1] text-white disabled:opacity-50 transition shadow-sm flex items-center gap-1.5"
              >
                {connecting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Connecting & Scanning...</span>
                  </>
                ) : (
                  <>
                    <FolderPlus className="w-3.5 h-3.5" />
                    <span>Connect & Index Now</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Connected Folders and Drives Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <HardDrive className="w-4 h-4 text-[#4263EB]" />
            <h3 className="text-xs font-semibold text-[#252821] uppercase tracking-wider">
              Connected Folders & Drives ({directories.length})
            </h3>
          </div>
          <span className="text-[11px] text-[#74766F]">
            {files.length} total active documents indexed
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {directories.map((dir) => (
            <div
              key={dir.id}
              className="p-3.5 rounded-xl bg-white border border-[#E7E4DC] shadow-card flex flex-col justify-between space-y-3 hover:border-[#4263EB]/30 transition"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 min-w-0">
                    <Folder className="w-4 h-4 text-[#4263EB] flex-shrink-0" />
                    <span className="font-semibold text-xs text-[#252821] truncate block" title={dir.label || dir.dir_path}>
                      {dir.label || dir.dir_path}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded font-medium bg-[#F0FDF4] text-[#23845B] border border-[#DCFCE7] flex-shrink-0">
                    {dir.file_count} file{dir.file_count === 1 ? '' : 's'}
                  </span>
                </div>

                <div
                  className="font-mono text-[11px] text-[#74766F] bg-[#FBFAF7] px-2 py-1 rounded border border-[#E7E4DC] truncate"
                  title={dir.dir_path}
                >
                  {dir.dir_path}
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-[#E7E4DC]/70 text-[10px] text-[#92938C]">
                <span>
                  {dir.last_scanned_at
                    ? `Scanned ${new Date(dir.last_scanned_at).toLocaleDateString([], {
                        month: 'short',
                        day: 'numeric',
                      })}`
                    : 'Not scanned'}
                </span>

                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => handleScanSingleDirectory(dir.id, dir.label || dir.dir_path)}
                    disabled={scanningDirId === dir.id}
                    className="p-1.5 rounded-lg text-[#74766F] hover:text-[#4263EB] hover:bg-[#F0EEE7] transition disabled:opacity-50"
                    title="Re-scan this folder"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${scanningDirId === dir.id ? 'animate-spin' : ''}`} />
                  </button>

                  {dir.label !== 'PersonalMail Default Directory' && (
                    <button
                      onClick={() => handleDisconnectFolder(dir)}
                      className="p-1.5 rounded-lg text-[#74766F] hover:text-[#C24141] hover:bg-[#FDF2F2] transition"
                      title="Disconnect folder"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Files List Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center space-x-2">
            <h3 className="text-xs font-semibold text-[#252821] uppercase tracking-wider">
              Indexed Documents
            </h3>
            <span className="text-xs bg-white border border-[#E7E4DC] px-2 py-0.5 rounded text-[#74766F] font-mono shadow-sm">
              {filteredFiles.length}
            </span>
          </div>

          <div className="flex items-center space-x-2 flex-wrap gap-2">
            {/* Filter by directory */}
            <select
              value={selectedDirFilter}
              onChange={(e) => setSelectedDirFilter(e.target.value)}
              className="h-9 bg-white border border-[#E7E4DC] rounded-lg px-2.5 text-xs text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition shadow-sm cursor-pointer"
            >
              <option value="all">All Folders ({files.length})</option>
              {directories.map((d) => (
                <option key={d.id} value={d.dir_path}>
                  {d.label || d.dir_path} ({d.file_count})
                </option>
              ))}
            </select>

            {/* Search bar */}
            <div className="relative w-64">
              <Search className="w-3.5 h-3.5 text-[#74766F] absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search filename or path..."
                className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg pl-8 pr-3 text-xs text-[#252821] placeholder-[#92938C] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition shadow-sm"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs text-[#74766F] bg-white rounded-xl border border-[#E7E4DC] shadow-card">
            Loading indexed files...
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="p-12 text-center text-xs text-[#74766F] bg-white rounded-xl border border-[#E7E4DC] space-y-2 shadow-card">
            <FileText className="w-8 h-8 text-[#92938C]/50 mx-auto" />
            <p className="font-medium text-[#252821]">No documents found</p>
            <p className="text-[#92938C] max-w-sm mx-auto">
              Connect a folder from your laptop or drop files into ~/.langmail/files/ to index them.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[#E7E4DC] rounded-xl bg-white border border-[#E7E4DC] overflow-hidden shadow-card">
            {filteredFiles.map((file) => (
              <div
                key={file.id}
                className="p-3.5 hover:bg-[#F0EEE7]/50 flex items-center justify-between transition flex-wrap gap-2"
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-[#FBFAF7] flex items-center justify-center flex-shrink-0 border border-[#E7E4DC]">
                    {getFileIcon(file.filename)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-xs text-[#252821] truncate block" title={file.filename}>
                        {file.filename}
                      </span>
                      {file.tags && (
                        <span className="text-[10px] bg-[#FBFAF7] text-[#74766F] border border-[#E7E4DC] px-1.5 py-0.2 rounded flex items-center gap-1 font-mono">
                          <Tag className="w-2.5 h-2.5" />
                          {file.tags}
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-[#92938C] flex items-center space-x-2 font-mono mt-0.5">
                      <span>{formatFileSize(file.size_bytes)}</span>
                      <span>•</span>
                      <span>
                        {file.modified_at
                          ? new Date(file.modified_at).toLocaleDateString([], {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric',
                            })
                          : 'Unknown date'}
                      </span>
                      <span>•</span>
                      <span className="text-[#92938C]/80 truncate max-w-md" title={file.file_path}>
                        {file.file_path}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleDeleteFile(file.id, file.filename)}
                    className="p-1.5 rounded-lg text-[#74766F] hover:text-[#C24141] hover:bg-[#FDF2F2] transition"
                    title="Remove from index"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
