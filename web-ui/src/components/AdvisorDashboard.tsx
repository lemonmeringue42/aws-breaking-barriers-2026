import React, { useState, useEffect } from 'react';
import { generateClient } from 'aws-amplify/data';
// @ts-ignore
import type { Schema } from '../../amplify/data/resource';

const client = generateClient<Schema>();

interface Case {
  caseId: string;
  urgencyLevel: 'CRISIS' | 'URGENT' | 'STANDARD' | 'GENERAL';
  issueCategory: string;
  summary: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';
  createdAt: string;
  scheduledCallbackTime?: string;
  assignedAdvisor?: string;
  advisorNotes?: string;
}

const URGENCY_COLORS = {
  CRISIS: 'bg-red-100 border-red-500 text-red-900',
  URGENT: 'bg-orange-100 border-orange-500 text-orange-900',
  STANDARD: 'bg-yellow-100 border-yellow-500 text-yellow-900',
  GENERAL: 'bg-blue-100 border-blue-500 text-blue-900',
};

const URGENCY_BADGES = {
  CRISIS: '🚨',
  URGENT: '⚠️',
  STANDARD: '📋',
  GENERAL: 'ℹ️',
};

export default function AdvisorDashboard() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('ALL');
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [notes, setNotes] = useState('');

  useEffect(() => {
    fetchCases();
  }, []);

  const fetchCases = async () => {
    try {
      setLoading(true);
      const { data } = await client.models.Case.list({});
      setCases(data as Case[]);
    } catch (error) {
      console.error('Error fetching cases:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateCaseStatus = async (caseId: string, status: string) => {
    try {
      await client.models.Case.update({
        caseId,
        status: status as any,
        lastUpdated: new Date().toISOString(),
      });
      fetchCases();
    } catch (error) {
      console.error('Error updating case:', error);
    }
  };

  const addNotes = async (caseId: string) => {
    try {
      await client.models.Case.update({
        caseId,
        advisorNotes: notes,
        lastUpdated: new Date().toISOString(),
      });
      setNotes('');
      setSelectedCase(null);
      fetchCases();
    } catch (error) {
      console.error('Error adding notes:', error);
    }
  };

  const filteredCases = cases
    .filter(c => filter === 'ALL' || c.urgencyLevel === filter)
    .sort((a, b) => {
      const priorityOrder = { CRISIS: 1, URGENT: 2, STANDARD: 3, GENERAL: 4 };
      return priorityOrder[a.urgencyLevel] - priorityOrder[b.urgencyLevel];
    });

  const stats = {
    total: cases.length,
    crisis: cases.filter(c => c.urgencyLevel === 'CRISIS').length,
    urgent: cases.filter(c => c.urgencyLevel === 'URGENT').length,
    pending: cases.filter(c => c.status === 'PENDING').length,
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Advisor Dashboard</h1>
          <p className="text-gray-600 mt-2">Manage and respond to citizen cases</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
            <div className="text-sm text-gray-600">Total Cases</div>
          </div>
          <div className="bg-red-50 p-4 rounded-lg shadow border-l-4 border-red-500">
            <div className="text-2xl font-bold text-red-900">{stats.crisis}</div>
            <div className="text-sm text-red-700">Crisis Cases</div>
          </div>
          <div className="bg-orange-50 p-4 rounded-lg shadow border-l-4 border-orange-500">
            <div className="text-2xl font-bold text-orange-900">{stats.urgent}</div>
            <div className="text-sm text-orange-700">Urgent Cases</div>
          </div>
          <div className="bg-blue-50 p-4 rounded-lg shadow border-l-4 border-blue-500">
            <div className="text-2xl font-bold text-blue-900">{stats.pending}</div>
            <div className="text-sm text-blue-700">Pending</div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white p-4 rounded-lg shadow mb-6">
          <div className="flex gap-2">
            {['ALL', 'CRISIS', 'URGENT', 'STANDARD', 'GENERAL'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  filter === f
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Cases List */}
        {loading ? (
          <div className="text-center py-12">
            <div className="text-gray-600">Loading cases...</div>
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="bg-white p-12 rounded-lg shadow text-center">
            <div className="text-gray-400 text-lg">No cases found</div>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredCases.map(c => (
              <div
                key={c.caseId}
                className={`bg-white p-6 rounded-lg shadow border-l-4 ${URGENCY_COLORS[c.urgencyLevel]}`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-2xl">{URGENCY_BADGES[c.urgencyLevel]}</span>
                      <span className="font-bold text-lg">{c.urgencyLevel}</span>
                      <span className="px-3 py-1 bg-gray-100 rounded-full text-sm">
                        {c.issueCategory}
                      </span>
                      <span className={`px-3 py-1 rounded-full text-sm ${
                        c.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' :
                        c.status === 'IN_PROGRESS' ? 'bg-blue-100 text-blue-800' :
                        'bg-green-100 text-green-800'
                      }`}>
                        {c.status}
                      </span>
                    </div>
                    <p className="text-gray-700 mb-3">{c.summary}</p>
                    <div className="text-sm text-gray-500">
                      <div>Case ID: {c.caseId}</div>
                      <div>Created: {new Date(c.createdAt).toLocaleString()}</div>
                      {c.scheduledCallbackTime && (
                        <div>Callback: {new Date(c.scheduledCallbackTime).toLocaleString()}</div>
                      )}
                    </div>
                    {c.advisorNotes && (
                      <div className="mt-3 p-3 bg-gray-50 rounded">
                        <div className="text-sm font-medium text-gray-700">Advisor Notes:</div>
                        <div className="text-sm text-gray-600">{c.advisorNotes}</div>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col gap-2 ml-4">
                    {c.status === 'PENDING' && (
                      <button
                        onClick={() => updateCaseStatus(c.caseId, 'IN_PROGRESS')}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                      >
                        Start Working
                      </button>
                    )}
                    {c.status === 'IN_PROGRESS' && (
                      <button
                        onClick={() => updateCaseStatus(c.caseId, 'RESOLVED')}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                      >
                        Mark Resolved
                      </button>
                    )}
                    <button
                      onClick={() => setSelectedCase(c)}
                      className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
                    >
                      Add Notes
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Notes Modal */}
        {selectedCase && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg p-6 max-w-lg w-full">
              <h3 className="text-xl font-bold mb-4">Add Advisor Notes</h3>
              <p className="text-sm text-gray-600 mb-4">Case: {selectedCase.caseId}</p>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full p-3 border rounded-lg mb-4 h-32"
                placeholder="Enter your notes about this case..."
              />
              <div className="flex gap-2">
                <button
                  onClick={() => addNotes(selectedCase.caseId)}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Save Notes
                </button>
                <button
                  onClick={() => {
                    setSelectedCase(null);
                    setNotes('');
                  }}
                  className="flex-1 px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
