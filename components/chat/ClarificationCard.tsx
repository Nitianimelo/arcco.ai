import React, { useState } from 'react';
import { MessageCircleQuestion, ArrowRight } from 'lucide-react';

export interface ClarificationQuestion {
  type: 'choice' | 'open';
  text: string;
  options: string[];
}

interface ClarificationCardProps {
  questions: ClarificationQuestion[];
  onSubmit: (answers: string[]) => void;
  disabled?: boolean;
}

const ClarificationCard: React.FC<ClarificationCardProps> = ({ questions, onSubmit, disabled }) => {
  const [answers, setAnswers] = useState<string[]>(() => questions.map(() => ''));

  const updateAnswer = (index: number, value: string) => {
    setAnswers(prev => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  };

  const allChoicesAnswered = questions.every((q, i) =>
    q.type === 'open' || answers[i] !== ''
  );

  const handleSubmit = () => {
    if (!allChoicesAnswered || disabled) return;
    onSubmit(answers);
  };

  return (
    <div className="my-3 rounded-xl border border-[#2a2a2a] bg-[#111113] overflow-hidden shadow-lg w-full max-w-md hover:border-amber-500/30 transition-all duration-200">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1e1e]">
        <div className="p-2 bg-amber-500/10 rounded-lg">
          <MessageCircleQuestion size={16} className="text-amber-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-neutral-100">Antes de comecar...</p>
          <p className="text-[10px] text-neutral-500 mt-0.5">Responda para um resultado melhor</p>
        </div>
      </div>

      {/* Questions */}
      <div className="px-4 py-3 space-y-4">
        {questions.map((q, qi) => (
          <div key={qi}>
            <p className="text-xs font-medium text-neutral-200 mb-2">{q.text}</p>

            {q.type === 'choice' && q.options.length > 0 ? (
              <div className="space-y-1.5">
                {q.options.map((opt, oi) => (
                  <button
                    key={oi}
                    onClick={() => updateAnswer(qi, opt)}
                    disabled={disabled}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all border ${
                      answers[qi] === opt
                        ? 'bg-amber-500/15 border-amber-500/50 text-amber-200'
                        : 'bg-[#1a1a1a] border-[#2a2a2a] text-neutral-400 hover:bg-[#222] hover:text-neutral-200'
                    } disabled:opacity-50`}
                  >
                    <span className="inline-flex items-center gap-2">
                      <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center ${
                        answers[qi] === opt ? 'border-amber-500' : 'border-neutral-600'
                      }`}>
                        {answers[qi] === opt && (
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        )}
                      </span>
                      {opt}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <input
                type="text"
                value={answers[qi]}
                onChange={(e) => updateAnswer(qi, e.target.value)}
                disabled={disabled}
                placeholder="Digite sua resposta..."
                className="w-full px-3 py-2 rounded-lg text-xs bg-[#1a1a1a] border border-[#2a2a2a] text-neutral-200 placeholder-neutral-600 focus:border-amber-500/50 focus:outline-none transition-colors disabled:opacity-50"
              />
            )}
          </div>
        ))}
      </div>

      {/* Submit */}
      <div className="px-4 pb-3">
        <button
          onClick={handleSubmit}
          disabled={!allChoicesAnswered || disabled}
          className="flex items-center justify-center gap-1.5 w-full px-4 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Continuar
          <ArrowRight size={13} />
        </button>
      </div>
    </div>
  );
};

export default ClarificationCard;
