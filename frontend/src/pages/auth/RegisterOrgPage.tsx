import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Building2, Mail, Lock, User, Hash, ArrowRight, CheckCircle2 } from 'lucide-react';
import { authApi } from '../../api/client';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

export const RegisterOrgPage: React.FC = () => {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    organization_name: '',
    slug: '',
    tin_number: '',
    admin_full_name: '',
    admin_email: '',
    admin_password: '',
  });

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleNameChange = (name: string) => {
    // Generate clean slug from organization name
    const cleanSlug = name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');

    setFormData((prev) => ({
      ...prev,
      organization_name: name,
      slug: cleanSlug,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await authApi.provisionTenant({
        organization_name: formData.organization_name.trim(),
        slug: formData.slug.trim(),
        tin_number: formData.tin_number.trim() || undefined,
        admin_full_name: formData.admin_full_name.trim(),
        admin_email: formData.admin_email.trim(),
        admin_password: formData.admin_password,
      });

      setSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const resp = (err as { response?: { data?: { detail?: string | { message?: string } } } }).response;
        const detail = resp?.data?.detail;
        const msg = typeof detail === 'string' ? detail : detail?.message || 'Failed to register organization. Please check details.';
        setError(msg);
      } else {
        setError('Network connection error. Please verify the server is running.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-slate-50/70 p-4 font-sans select-none">
      <div className="w-full max-w-md">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-50 border border-blue-100 text-blue-600 mb-3 shadow-xs">
            <Building2 className="w-6 h-6 text-blue-600" />
          </div>
          <h1 className="text-xl font-semibold text-slate-900 tracking-tight">Organization Setup</h1>
          <p className="text-xs text-slate-500 mt-1">Provision a new tenant and configure your enterprise workspace</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xs border border-slate-200/80 p-6 sm:p-8">
          {success ? (
            <div className="text-center py-6">
              <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-slate-900">Workspace Created Successfully!</h3>
              <p className="text-xs text-slate-500 mt-1.5">Redirecting to sign in...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3.5">
              {error && (
                <div className="p-3 rounded-lg bg-red-50 text-red-700 text-xs border border-red-100">
                  {error}
                </div>
              )}

              <Input
                label="Organization name"
                placeholder="Abyssinia Technology PLC"
                value={formData.organization_name}
                onChange={(e) => handleNameChange(e.target.value)}
                leftIcon={<Building2 className="w-4 h-4" />}
                required
                autoFocus
              />

              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Workspace slug"
                  placeholder="abyssinia"
                  value={formData.slug}
                  onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                  required
                />
                <Input
                  label="Tax ID (TIN)"
                  placeholder="10-digit number"
                  value={formData.tin_number}
                  onChange={(e) => setFormData({ ...formData, tin_number: e.target.value })}
                  leftIcon={<Hash className="w-4 h-4" />}
                />
              </div>

              <div className="pt-2 border-t border-slate-100">
                <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Administrator Account
                </p>
              </div>

              <Input
                label="Administrator full name"
                placeholder="Abebe Kebede"
                value={formData.admin_full_name}
                onChange={(e) => setFormData({ ...formData, admin_full_name: e.target.value })}
                leftIcon={<User className="w-4 h-4" />}
                required
              />

              <Input
                label="Work email"
                type="email"
                placeholder="admin@abyssinia.et"
                value={formData.admin_email}
                onChange={(e) => setFormData({ ...formData, admin_email: e.target.value })}
                leftIcon={<Mail className="w-4 h-4" />}
                required
              />

              <Input
                label="Password"
                type="password"
                placeholder="Minimum 8 characters"
                value={formData.admin_password}
                onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                leftIcon={<Lock className="w-4 h-4" />}
                required
              />

              <Button
                type="submit"
                variant="primary"
                className="w-full mt-4"
                isLoading={isLoading}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Create Workspace
              </Button>
            </form>
          )}
        </div>

        {/* Footer Link to Login */}
        <div className="text-center mt-6">
          <Link
            to="/login"
            className="text-xs text-slate-500 hover:text-blue-600 transition-colors"
          >
            Already have a workspace? <span className="font-medium underline underline-offset-2">Sign in</span>
          </Link>
        </div>
      </div>
    </div>
  );
};
