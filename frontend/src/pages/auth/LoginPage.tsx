import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, ShieldAlert, FolderKanban } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { systemApi } from '../../api/client';
import type { SystemContext } from '../../api/types';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [systemContext, setSystemContext] = useState<SystemContext | null>(null);

  useEffect(() => {
    const probeContext = async () => {
      try {
        const ctx = await systemApi.getContext();
        setSystemContext(ctx);
      } catch {
        // Safe fallback for disconnected intranet
        setSystemContext({
          deployment_mode: 'ON_PREMISE',
          allow_public_registration: false,
          system_name: 'Wine Technologies — Private Workspace',
        });
      }
    };
    probeContext();
  }, []);

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
          const msg = typeof detail === 'string' ? detail : detail?.message || 'Account is temporarily locked due to failed attempts. Please try again later.';
          setError(msg);
        } else {
          const detail = resp?.data?.detail;
          const msg = typeof detail === 'string' ? detail : detail?.message || 'Invalid email or password. Please check your credentials.';
          setError(msg);
        }
      } else {
        setError('Network connection error. Please verify the server is running.');
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
    <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-slate-100 via-slate-50 to-blue-100/90 p-4 sm:p-6 font-sans select-none relative overflow-hidden">
      {/* Clearly visible soft blue ambient gradient in the bottom right corner */}
      <div className="pointer-events-none absolute -bottom-28 -right-28 w-[500px] h-[500px] bg-gradient-to-tl from-blue-400/50 via-blue-200/40 to-transparent rounded-full blur-3xl" />
      <div className="pointer-events-none absolute -bottom-10 -right-10 w-80 h-80 bg-blue-300/35 rounded-full blur-2xl" />

      {/* Slightly more compact card container */}
      <div className="w-full max-w-[365px] relative z-10">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-50 border border-blue-200/80 text-blue-600 mb-3 shadow-xs">
            <FolderKanban className="w-7 h-7 text-blue-600" />
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            {systemContext?.organization_name || 'Wine Technologies'}
          </h1>
          <p className="text-sm text-slate-500 mt-1.5 font-medium">
            {systemContext?.deployment_mode === 'ON_PREMISE'
              ? 'Private Intranet Document & Correspondence Suite'
              : 'Enterprise Document & Correspondence Suite'}
          </p>
        </div>

        {/* Form Container: slightly smaller & more compact footprint */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/90 p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-50 text-red-700 text-sm border border-red-100">
                <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{error}</span>
              </div>
            )}

            <Input
              label="Work email"
              labelClassName="text-sm font-bold text-slate-950 mb-1.5"
              inputSize="lg"
              type="email"
              placeholder="name@organization.et"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              leftIcon={<Mail className="w-4 h-4" />}
              required
              autoFocus
            />

            <div>
              <Input
                label="Password"
                labelClassName="text-sm font-bold text-slate-950 mb-1.5"
                inputSize="lg"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                leftIcon={<Lock className="w-4 h-4" />}
                rightIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-slate-400 hover:text-slate-600 focus:outline-none"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
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
              size="lg"
              className="w-full mt-2 font-bold text-base py-3 rounded-xl shadow-sm tracking-wide"
              isLoading={isLoading}
            >
              <span className="font-bold text-base tracking-wide text-white">Sign in</span>
            </Button>
          </form>

          {/* Demo Quick Fills */}
          <div className="mt-5 pt-4 border-t border-slate-100">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 text-center">
              Quick Demo Access
            </p>
            <div className="flex flex-col gap-1.5">
              <button
                type="button"
                onClick={() => handleDemoSignIn('admin@abyssinia.et', 'Admin123!')}
                className="text-left py-2 px-3 rounded-xl bg-slate-50 hover:bg-blue-50/70 hover:text-blue-700 text-slate-700 transition-colors flex items-center justify-between border border-slate-200/60"
              >
                <span className="font-semibold text-sm">Administrator</span>
                <span className="text-xs text-slate-400">admin@abyssinia.et</span>
              </button>
            </div>
          </div>
        </div>

        {/* Footer Link to Org Onboarding - Only visible on Cloud SaaS with public registration enabled */}
        {systemContext?.allow_public_registration && (
          <div className="text-center mt-5">
            <Link
              to="/register"
              className="text-sm text-slate-500 hover:text-blue-600 transition-colors"
            >
              Need to setup an organization? <span className="font-semibold underline underline-offset-2">Register workspace</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};
