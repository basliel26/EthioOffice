import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, ShieldAlert, ArrowRight } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(email.trim(), password);
      navigate('/drive');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const resp = (err as { response?: { status?: number; data?: { detail?: string | { message?: string } } } }).response;
        if (resp?.status === 423) {
          const detail = resp.data?.detail;
          const msg = typeof detail === 'string' ? detail : detail?.message || 'አካውንቱ ለጊዜው ታግዷል (Account is temporarily locked)';
          setError(msg);
        } else {
          const detail = resp?.data?.detail;
          const msg = typeof detail === 'string' ? detail : detail?.message || 'የተሳሳተ ኢሜይል ወይም የይለፍ ቃል (Invalid email or password)';
          setError(msg);
        }
      } else {
        setError('የግንኙነት ስህተት ተከስቷል (Network connection error)');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoSignIn = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-zinc-50/60 p-4 font-sans select-none">
      <div className="w-full max-w-sm">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-zinc-900 text-white shadow-md mb-3">
            <span className="font-semibold text-lg tracking-wider">EO</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 tracking-tight">EthioOffice</h1>
          <p className="text-xs text-zinc-500 mt-1">የኢትዮጵያ ኢንተርፕራይዝ የቢሮ ሰነዶች እና ደብዳቤዎች ስርዓት</p>
        </div>

        {/* Form Container */}
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200/60 p-6 sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-50 text-red-700 text-xs">
                <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{error}</span>
              </div>
            )}

            <Input
              label="የስራ ኢሜይል (Work Email)"
              type="email"
              placeholder="name@company.et"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              leftIcon={<Mail className="w-4 h-4" />}
              required
              autoFocus
            />

            <div>
              <Input
                label="የይለፍ ቃል (Password)"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                leftIcon={<Lock className="w-4 h-4" />}
                rightIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-zinc-400 hover:text-zinc-600 focus:outline-none"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                }
                required
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={isLoading}
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              ግባ (Sign In)
            </Button>
          </form>

          {/* Demo Quick Fills */}
          <div className="mt-6 pt-6 border-t border-zinc-100">
            <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-2 text-center">
              ፈጣን መግቢያ (Demo Credentials)
            </p>
            <div className="flex flex-col gap-1.5">
              <button
                type="button"
                onClick={() => handleDemoSignIn('admin@abyssinia.et', 'Admin123!')}
                className="text-left text-xs py-1.5 px-2.5 rounded-md hover:bg-zinc-50 text-zinc-600 hover:text-zinc-900 transition-colors flex items-center justify-between"
              >
                <span>አስተዳዳሪ (Admin)</span>
                <span className="text-[11px] text-zinc-400">admin@abyssinia.et</span>
              </button>
            </div>
          </div>
        </div>

        {/* Footer Link to Org Onboarding */}
        <div className="text-center mt-6">
          <Link
            to="/register"
            className="text-xs text-zinc-500 hover:text-zinc-800 transition-colors"
          >
            አዲስ ድርጅት መመዝገብ ይፈልጋሉ? (Setup New Organization)
          </Link>
        </div>
      </div>
    </div>
  );
};
