import React, { useState } from 'react';
import { MessageSquare, Plus, X, Edit3, Save, Trash2, User, Clock } from 'lucide-react';
import { VoiceInputButton } from './VoiceInput';
import { useTheme } from '../../context/ThemeContext';

// Single Note/Comment Component
function NoteItem({ note, onEdit, onDelete }) {
  const { isDark } = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(note.text);

  const handleSave = () => {
    onEdit(note.id, editText);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditText(note.text);
    setIsEditing(false);
  };

  return (
    <div className={`rounded-lg p-3 border ${isDark ? 'bg-white/5 border-white/10' : 'bg-white/60 border-slate-200'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          {isEditing ? (
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className={`w-full px-2 py-1 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 resize-none ${
                isDark 
                  ? 'bg-white/5 border-[var(--accent-primary)]/30 text-white' 
                  : 'border-[var(--accent-primary)]/30 bg-white text-slate-800'
              }`}
              rows={2}
              autoFocus
            />
          ) : (
            <p className={`text-sm ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{note.text}</p>
          )}
        </div>
        <div className="flex items-center gap-1">
          {isEditing ? (
            <>
              <button
                onClick={handleSave}
                className={`p-1 rounded ${isDark ? 'text-green-400 hover:bg-green-500/20' : 'text-green-600 hover:bg-green-50'}`}
                title="Save"
              >
                <Save className="w-4 h-4" />
              </button>
              <button
                onClick={handleCancel}
                className={`p-1 rounded ${isDark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-50'}`}
                title="Cancel"
              >
                <X className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setIsEditing(true)}
                className={`p-1 rounded ${isDark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-50'}`}
                title="Edit"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => onDelete(note.id)}
                className={`p-1 rounded ${isDark ? 'text-red-400 hover:bg-red-500/20' : 'text-red-500 hover:bg-red-50'}`}
                title="Delete"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          )}
        </div>
      </div>
      <div className={`flex items-center gap-3 mt-2 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
        <span className="flex items-center gap-1">
          <User className="w-3 h-3" />
          {note.author}
        </span>
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {note.timestamp}
        </span>
      </div>
    </div>
  );
}

// Notes/Comments Section for a Recommendation
export function NotesSection({ itemId, notes = [], onAddNote, onEditNote, onDeleteNote }) {
  const { isDark } = useTheme();
  const [isAdding, setIsAdding] = useState(false);
  const [newNote, setNewNote] = useState('');

  const handleAddNote = () => {
    if (newNote.trim()) {
      onAddNote(itemId, {
        id: Date.now().toString(),
        text: newNote.trim(),
        author: 'Dr. Current User',
        timestamp: new Date().toLocaleString()
      });
      setNewNote('');
      setIsAdding(false);
    }
  };

  const handleVoiceTranscript = (transcript) => {
    setNewNote((prev) => prev + (prev ? ' ' : '') + transcript);
  };

  const itemNotes = notes.filter(note => note.itemId === itemId);

  return (
    <div className={`mt-3 border-t pt-3 ${isDark ? 'border-white/10' : 'border-slate-200/50'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs font-medium flex items-center gap-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          <MessageSquare className="w-3.5 h-3.5" />
          Notes ({itemNotes.length})
        </span>
        {!isAdding && (
          <button
            onClick={() => setIsAdding(true)}
            className={`text-xs flex items-center gap-1 ${isDark ? 'text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)]' : 'text-[var(--accent-primary)] hover:opacity-80'}`}
          >
            <Plus className="w-3.5 h-3.5" />
            Add Note
          </button>
        )}
      </div>

      {/* Existing Notes */}
      {itemNotes.length > 0 && (
        <div className="space-y-2 mb-2">
          {itemNotes.map((note) => (
            <NoteItem
              key={note.id}
              note={note}
              onEdit={(noteId, text) => onEditNote(itemId, noteId, text)}
              onDelete={(noteId) => onDeleteNote(itemId, noteId)}
            />
          ))}
        </div>
      )}

      {/* Add New Note */}
      {isAdding && (
        <div className={`rounded-lg p-3 border ${isDark ? 'bg-white/5 border-[var(--accent-primary)]/30' : 'bg-white/60 border-[var(--accent-primary)]/20'}`}>
          <textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Add a note or comment..."
            className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 resize-none ${
              isDark 
                ? 'bg-white/5 border-white/20 text-white placeholder-slate-500' 
                : 'bg-white/80 border-slate-300 text-slate-800 placeholder-slate-400'
            }`}
            rows={2}
            autoFocus
          />
          <div className="flex items-center justify-between mt-2">
            <VoiceInputButton
              onTranscript={handleVoiceTranscript}
              className="text-xs"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setIsAdding(false);
                  setNewNote('');
                }}
                className={`px-3 py-1.5 text-xs rounded-lg ${isDark ? 'text-slate-300 hover:bg-white/10' : 'text-slate-600 hover:bg-slate-100'}`}
              >
                Cancel
              </button>
              <button
                onClick={handleAddNote}
                disabled={!newNote.trim()}
                className="px-3 py-1.5 text-xs bg-[var(--accent-primary)] text-white rounded-lg hover:bg-[var(--accent-primary-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Add Note
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Compact Notes Indicator
export function NotesIndicator({ count = 0, onClick }) {
  const { isDark } = useTheme();
  
  if (count === 0) {
    return (
      <button
        onClick={onClick}
        className={`flex items-center gap-1 text-xs ${isDark ? 'text-slate-400 hover:text-[var(--accent-primary)]' : 'text-slate-500 hover:text-[var(--accent-primary)]'}`}
        title="Add a note"
      >
        <MessageSquare className="w-3.5 h-3.5" />
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1 text-xs ${isDark ? 'text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)]' : 'text-[var(--accent-primary)] hover:opacity-80'}`}
      title={`${count} note${count > 1 ? 's' : ''}`}
    >
      <MessageSquare className="w-3.5 h-3.5" />
      <span className="font-medium">{count}</span>
    </button>
  );
}
