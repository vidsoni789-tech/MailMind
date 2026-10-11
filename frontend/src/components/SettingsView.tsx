import React, { useState, useEffect } from 'react';
import {
  Save,
  Trash2,
  Sliders,
  UserCheck,
  Plus,
  Edit2,
  Check,
  X,
  Sparkles,
} from 'lucide-react';
import { UserProfile, StylePreference } from '../types';
import { api } from '../api';

export const SettingsView: React.FC = () => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [preferences, setPreferences] = useState<StylePreference[]>([]);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [loading, setLoading] = useState(true);

  // Add preference modal / form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newType, setNewType] = useState('greeting');
  const [newValue, setNewValue] = useState('');
  const [newContactEmail, setNewContactEmail] = useState('');
  const [newConfidence, setNewConfidence] = useState(0.85);

  // Inline edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editConfidence, setEditConfidence] = useState(0.85);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [prof, prefs] = await Promise.all([api.getProfile(), api.getPreferences()]);
      setProfile(prof);
      setPreferences(prefs.preferences || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    try {
      const updated = await api.updateProfile(profile);
      setProfile(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddPreference = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newValue.trim()) return;
    try {
      const added = await api.addPreference({
        pref_type: newType,
        value: newValue.trim(),
        contact_email: newContactEmail.trim() || undefined,
        confidence: newConfidence,
      });
      setPreferences((prev) => [added, ...prev.filter((p) => p.id !== added.id)]);
      setNewValue('');
      setNewContactEmail('');
      setShowAddForm(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleStartEdit = (pref: StylePreference) => {
    setEditingId(pref.id);
    setEditValue(pref.value);
    setEditConfidence(pref.confidence);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue('');
  };

  const handleSaveEdit = async (prefId: string) => {
    if (!editValue.trim()) return;
    try {
      const updated = await api.updatePreference(prefId, {
        value: editValue.trim(),
        confidence: editConfidence,
      });
      setPreferences((prev) => prev.map((p) => (p.id === prefId ? updated : p)));
      setEditingId(null);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeletePreference = async (id: string) => {
    try {
      await api.deletePreference(id);
      setPreferences((prev) => prev.filter((p) => p.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  if (loading || !profile) {
    return <div className="p-12 text-center text-xs text-text-secondary">Loading settings...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto p-6 sm:p-8 space-y-8 select-none">
      {/* Profile Section */}
      <div className="space-y-4">
        <div className="border-b border-[#E7E4DC] pb-3">
          <h2 className="text-base font-semibold text-[#252821] flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-[#4263EB]" />
            User Personalization Profile
          </h2>
          <p className="text-xs text-[#74766F] mt-1">
            Personal context and tone injected into the AI agent to draft customized email responses.
          </p>
        </div>

        <form
          onSubmit={handleSaveProfile}
          className="bg-white p-5 sm:p-6 rounded-xl border border-[#E7E4DC] space-y-4 text-xs shadow-card"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[#74766F] mb-1 font-medium">Your Role / Title</label>
              <input
                type="text"
                value={profile.role || ''}
                onChange={(e) => setProfile({ ...profile, role: e.target.value })}
                placeholder="e.g. Software Engineer / Lead"
                className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition"
              />
            </div>

            <div>
              <label className="block text-[#74766F] mb-1 font-medium">Organization / Company</label>
              <input
                type="text"
                value={profile.organization || ''}
                onChange={(e) => setProfile({ ...profile, organization: e.target.value })}
                placeholder="e.g. Acme Inc"
                className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition"
              />
            </div>

            <div>
              <label className="block text-[#74766F] mb-1 font-medium">College / University</label>
              <input
                type="text"
                value={profile.college || ''}
                onChange={(e) => setProfile({ ...profile, college: e.target.value })}
                placeholder="e.g. University of California"
                className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition"
              />
            </div>

            <div>
              <label className="block text-[#74766F] mb-1 font-medium">Default Tone</label>
              <select
                value={profile.default_tone || 'professional'}
                onChange={(e) => setProfile({ ...profile, default_tone: e.target.value })}
                className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition"
              >
                <option value="professional">Professional</option>
                <option value="concise">Concise & Direct</option>
                <option value="casual">Casual & Friendly</option>
                <option value="formal">Strictly Formal</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[#74766F] mb-1 font-medium">Email Signature</label>
            <textarea
              value={profile.signature || ''}
              onChange={(e) => setProfile({ ...profile, signature: e.target.value })}
              rows={2}
              placeholder="e.g. Best regards, Alex"
              className="w-full bg-white border border-[#E7E4DC] rounded-lg p-3 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 leading-relaxed font-sans transition"
            />
          </div>

          <div className="flex items-center justify-between pt-2">
            {savedSuccess ? (
              <span className="text-[#23845B] text-xs font-medium flex items-center gap-1.5">
                <Check className="w-3.5 h-3.5" />
                Settings saved successfully.
              </span>
            ) : (
              <span />
            )}

            <button
              type="submit"
              className="h-9 px-4 rounded-lg bg-[#4263EB] hover:bg-[#3451D1] text-white text-xs font-medium flex items-center gap-2 transition shadow-sm"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save Profile</span>
            </button>
          </div>
        </form>
      </div>

      {/* Style Preferences Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-[#E7E4DC] pb-3">
          <div>
            <h2 className="text-base font-semibold text-[#252821] flex items-center gap-2">
              <Sliders className="w-4 h-4 text-[#4263EB]" />
              Learned Style Preferences
            </h2>
            <p className="text-xs text-[#74766F] mt-1">
              Preferences automatically learned from your edits on drafts. You can view, fine-tune, or remove them.
            </p>
          </div>

          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="h-9 px-3 rounded-lg bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] text-xs font-medium flex items-center gap-1.5 transition shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Preference</span>
          </button>
        </div>

        {/* Add Preference Form */}
        {showAddForm && (
          <form
            onSubmit={handleAddPreference}
            className="p-4 sm:p-5 rounded-xl bg-white border border-[#E7E4DC] space-y-3 text-xs shadow-card"
          >
            <div className="font-medium text-[#252821] flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-[#4263EB]" />
              <span>Add Custom Style Rule</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-[#74766F] mb-1">Rule Type</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-2.5 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
                >
                  <option value="greeting">Preferred Greeting</option>
                  <option value="signoff">Preferred Sign-off</option>
                  <option value="conciseness">Conciseness / Length</option>
                  <option value="avoid_phrase">Phrase to Avoid</option>
                  <option value="preferred_phrase">Preferred Phrase</option>
                  <option value="tone">Tone (formal / casual)</option>
                  <option value="formatting">Formatting</option>
                </select>
              </div>

              <div>
                <label className="block text-[#74766F] mb-1">Value / Phrase</label>
                <input
                  type="text"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  placeholder="e.g. Cheers, or I hope all is well"
                  className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-2.5 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
                />
              </div>

              <div>
                <label className="block text-[#74766F] mb-1">Target Contact (Optional)</label>
                <input
                  type="email"
                  value={newContactEmail}
                  onChange={(e) => setNewContactEmail(e.target.value)}
                  placeholder="Leave empty for global"
                  className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-2.5 text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center gap-2 text-[#74766F]">
                <span>Confidence: {(newConfidence * 100).toFixed(0)}%</span>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={newConfidence}
                  onChange={(e) => setNewConfidence(parseFloat(e.target.value))}
                  className="w-24 accent-[#4263EB]"
                />
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="h-8 px-3 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="h-8 px-3.5 rounded-lg bg-[#4263EB] hover:bg-[#3451D1] text-white font-medium transition shadow-sm"
                >
                  Save Preference
                </button>
              </div>
            </div>
          </form>
        )}

        {preferences.length === 0 ? (
          <div className="p-8 text-center text-[#74766F] text-xs bg-white rounded-xl border border-[#E7E4DC] shadow-card">
            No learned style preferences recorded yet. They will appear here automatically when you edit AI drafts.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {preferences.map((pref) => {
              const isEditingThis = editingId === pref.id;

              return (
                <div
                  key={pref.id}
                  className="p-4 rounded-xl bg-white border border-[#E7E4DC] flex flex-col justify-between space-y-2 shadow-card hover:border-[#D6D2C4] transition"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0 pr-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-[#FBFAF7] text-[#252821] border border-[#E7E4DC] font-medium">
                          {pref.type}
                        </span>
                        {pref.contact_email ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#EAEFFF] text-[#4263EB] border border-[#D0DBFF]">
                            {pref.contact_email}
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#FBFAF7] text-[#74766F] border border-[#E7E4DC]">
                            Global
                          </span>
                        )}
                      </div>

                      {isEditingThis ? (
                        <div className="mt-2 space-y-2">
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="w-full h-8 bg-white border border-[#4263EB] rounded px-2 text-xs text-[#252821]"
                          />
                          <div className="flex items-center gap-2 text-[10px] text-[#74766F]">
                            <span>Confidence: {(editConfidence * 100).toFixed(0)}%</span>
                            <input
                              type="range"
                              min="0.1"
                              max="1.0"
                              step="0.05"
                              value={editConfidence}
                              onChange={(e) => setEditConfidence(parseFloat(e.target.value))}
                              className="w-20 accent-[#4263EB]"
                            />
                          </div>
                        </div>
                      ) : (
                        <p className="text-xs font-medium text-[#252821] mt-2">
                          "{pref.value}"
                        </p>
                      )}

                      <p className="text-[10px] text-[#92938C] mt-1">
                        Confidence: {(pref.confidence * 100).toFixed(0)}% • Evidence: {pref.evidence_count}x
                      </p>
                    </div>

                    <div className="flex items-center gap-1 flex-shrink-0">
                      {isEditingThis ? (
                        <>
                          <button
                            onClick={() => handleSaveEdit(pref.id)}
                            className="p-1 rounded text-[#23845B] hover:bg-[#F0FDF4] transition"
                            title="Save"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={handleCancelEdit}
                            className="p-1 rounded text-[#74766F] hover:bg-[#F0EEE7] transition"
                            title="Cancel"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => handleStartEdit(pref)}
                            className="p-1.5 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] transition"
                            title="Edit preference"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeletePreference(pref.id)}
                            className="p-1.5 rounded-lg text-[#74766F] hover:text-[#C24141] hover:bg-[#FDF2F2] transition"
                            title="Delete preference"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
