import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Brain, Sparkles, Zap, Loader2, CheckCircle2, AlertTriangle,
  Layers, GitCompare, Lightbulb, Target, ArrowRight, Users, Cpu,
} from 'lucide-react';
import { toast } from 'sonner';

const PROVIDER_COLORS = {
  deepseek: 'border-blue-400 bg-blue-50',
  openai: 'border-emerald-400 bg-emerald-50',
  gemini: 'border-amber-400 bg-amber-50',
  anthropic: 'border-purple-400 bg-purple-50',
  cloudflare: 'border-orange-400 bg-orange-50',
};

const PROVIDER_NAMES = {
  deepseek: 'DeepSeek',
  openai: 'GPT',
  gemini: 'Gemini',
  anthropic: 'Claude',
  cloudflare: 'Cloudflare AI',
};

export default function MultiAIAnalysis({ content, mode, disabled, label }) {
  const { slug } = useParams();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!content || !content.trim()) {
      toast.error('Please enter some content first');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`/api/${slug}/multi-ai/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          content: content.trim(),
          mode: mode,
          panel_size: 3,
          synthesize: true,
        }),
      });

      if (!res.ok) {
        const clone = res.clone();
        const msg = (await clone.json().catch(() => ({ detail: `HTTP ${res.status}` }))).detail;
        throw new Error(msg);
      }

      const data = await res.json();
      setResult(data);
      toast.success(`Analysis complete — ${data.panel_size} AIs responded${data.synthesis ? ' + synthesis' : ''}`);
    } catch (err) {
      setError(err.message);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Trigger button */}
      <button
        onClick={handleAnalyze}
        disabled={disabled || loading || !content?.trim()}
        className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-amber-500 to-orange-500 text-white text-sm font-semibold rounded-lg hover:from-amber-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md"
      >
        {loading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Brain size={16} />
        )}
        {loading ? 'Analyzing with multiple AIs...' : (label || 'Multi-AI Analysis')}
      </button>

      {loading && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 text-sm text-amber-700">
            <Sparkles size={16} className="animate-pulse" />
            <span>Sending to multiple AI models in parallel...</span>
            <span className="text-xs text-amber-500 ml-auto">This may take 10-30 seconds</span>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          <AlertTriangle size={16} className="inline mr-2" />
          {error}
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-4">
          {/* Synthesis (if available) */}
          {result.synthesis && (
            <div className="bg-gradient-to-r from-purple-50 to-pink-50 border-2 border-purple-300 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center">
                  <GitCompare size={16} className="text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-purple-900">Synthesis</h3>
                  <p className="text-xs text-purple-500">
                    by {PROVIDER_NAMES[result.synthesis.provider] || result.synthesis.provider} / {result.synthesis.model}
                    {result.synthesis.tokens && ` · ${result.synthesis.tokens.input + result.synthesis.tokens.output} tokens`}
                    {result.synthesis.latency_ms && ` · ${(result.synthesis.latency_ms / 1000).toFixed(1)}s`}
                  </p>
                </div>
              </div>
              <pre className="text-sm text-gray-800 whitespace-pre-wrap font-sans leading-relaxed">
                {result.synthesis.content || result.synthesis.error || 'No synthesis'}
              </pre>
            </div>
          )}

          {/* Individual AI panels */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {result.panel.map((p, i) => {
              const colorClass = PROVIDER_COLORS[p.provider] || 'border-gray-300 bg-gray-50';
              const isError = !!p.error;

              return (
                <div key={i} className={`border rounded-xl p-4 ${isError ? 'border-red-300 bg-red-50' : colorClass}`}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${isError ? 'bg-red-200' : 'bg-white'}`}>
                        {isError ? (
                          <AlertTriangle size={14} className="text-red-500" />
                        ) : (
                          <Cpu size={14} className="text-gray-600" />
                        )}
                      </div>
                      <div>
                        <div className="text-xs font-bold text-gray-700">
                          Analyst {String.fromCharCode(65 + i)}
                        </div>
                        <div className="text-xs text-gray-500">
                          {PROVIDER_NAMES[p.provider] || p.provider} / {p.model}
                        </div>
                      </div>
                    </div>
                    {!isError && p.tokens && (
                      <div className="text-right">
                        <div className="text-xs text-gray-400">
                          {p.tokens.input + p.tokens.output} tokens
                        </div>
                        <div className="text-xs text-gray-400">
                          {(p.latency_ms / 1000).toFixed(1)}s
                        </div>
                      </div>
                    )}
                  </div>

                  {isError ? (
                    <p className="text-xs text-red-600">{p.error}</p>
                  ) : (
                    <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed max-h-80 overflow-y-auto">
                      {p.content || 'No response'}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>

          {/* Summary stats */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-3 flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Users size={13} />
              {result.panel_size} analysts
            </span>
            <span className="flex items-center gap-1">
              <Layers size={13} />
              {new Set(result.panel.filter(p => !p.error).map(p => p.provider)).size} providers
            </span>
            <span className="flex items-center gap-1">
              <CheckCircle2 size={13} className="text-emerald-500" />
              {result.panel.filter(p => !p.error).length}/{result.panel_size} succeeded
            </span>
            {result.synthesis && (
              <span className="flex items-center gap-1 ml-auto text-purple-600">
                <GitCompare size={13} />
                Synthesized by {PROVIDER_NAMES[result.synthesis.provider] || result.synthesis.provider}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
