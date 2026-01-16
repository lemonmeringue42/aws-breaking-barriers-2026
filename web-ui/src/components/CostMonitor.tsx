import React, { useState, useEffect } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';

interface CostData {
  today: {
    cost: number;
    conversations: number;
    input_tokens: number;
    output_tokens: number;
    avg_cost_per_conversation: number;
  };
  month: {
    cost: number;
    conversations: number;
    input_tokens: number;
    output_tokens: number;
  };
  pricing?: {
    input_per_1k: number;
    output_per_1k: number;
    model: string;
  };
  timestamp: string;
}

const COST_API_URL = import.meta.env.VITE_COST_API_URL || '';

export default function CostMonitor() {
  const [costData, setCostData] = useState<CostData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!COST_API_URL) {
      setLoading(false);
      setError('Cost monitoring not configured');
      return;
    }
    fetchCosts();
    const interval = setInterval(fetchCosts, 300000);
    return () => clearInterval(interval);
  }, []);

  const fetchCosts = async () => {
    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();

      const response = await fetch(`${COST_API_URL}/costs`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setCostData(data);
        setError(null);
      } else {
        setError('Failed to fetch cost data');
      }
    } catch (err) {
      console.error('Error fetching costs:', err);
      setError('Error loading costs');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-sm text-gray-500">Loading costs...</div>
      </div>
    );
  }

  if (error || !costData) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-sm text-red-600">{error || 'No data available'}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Cost Monitor</h3>
        <button
          onClick={fetchCosts}
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          Refresh
        </button>
      </div>

      {/* Today's Stats */}
      <div className="border-b pb-3">
        <div className="text-sm text-gray-600 mb-2">Today</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-2xl font-bold text-gray-900">
              ${costData.today.cost.toFixed(2)}
            </div>
            <div className="text-xs text-gray-500">Total Cost</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900">
              {costData.today.conversations}
            </div>
            <div className="text-xs text-gray-500">Conversations</div>
          </div>
        </div>
        <div className="mt-2 text-xs text-gray-600">
          Avg: ${costData.today.avg_cost_per_conversation.toFixed(4)} per conversation
        </div>
      </div>

      {/* This Month */}
      <div className="border-b pb-3">
        <div className="text-sm text-gray-600 mb-2">This Month</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-xl font-bold text-gray-900">
              ${costData.month.cost.toFixed(2)}
            </div>
            <div className="text-xs text-gray-500">Total Cost</div>
          </div>
          <div>
            <div className="text-xl font-bold text-gray-900">
              {costData.month.conversations}
            </div>
            <div className="text-xs text-gray-500">Conversations</div>
          </div>
        </div>
      </div>

      {/* Token Usage */}
      <div>
        <div className="text-sm text-gray-600 mb-2">Token Usage (Today)</div>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-gray-600">Input:</span>
            <span className="font-medium">{costData.today.input_tokens.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Output:</span>
            <span className="font-medium">{costData.today.output_tokens.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Pricing Info */}
      {costData.pricing && (
        <div className="text-xs text-gray-500 pt-2 border-t">
          <div className="font-medium mb-1">{costData.pricing.model}</div>
          <div>Input: ${costData.pricing.input_per_1k.toFixed(3)}/1K tokens</div>
          <div>Output: ${costData.pricing.output_per_1k.toFixed(3)}/1K tokens</div>
        </div>
      )}

      <div className="text-xs text-gray-400 pt-2 border-t">
        Last updated: {new Date(costData.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}
