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
        const msg = typeof detail === 'string' ? detail : detail?.message || 'ድርጅቱን መመዝገብ አልተቻለም (Failed to register organization)';
        setError(msg);
      } else {
        setError('የግንኙነት ስህተት ተከስቷል');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-zinc-50/60 p-4 font-sans select-none">
      <div className="w-full max-w-md">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-zinc-900 text-white shadow-md mb-3">
            <Building2 className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 tracking-tight">የድርጅት ምዝገባ (Organization Setup)</h1>
          <p className="text-xs text-zinc-500 mt-1">አዲስ ድርጅት እና የደመና ወይም የውስጥ ቢሮ ስርዓት ማዘጋጀት</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200/60 p-6 sm:p-8">
          {success ? (
            <div className="text-center py-6">
              <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-zinc-900">ድርጅቱ በተሳካ ሁኔታ ተመዝግቧል!</h3>
              <p className="text-xs text-zinc-500 mt-1.5">ወደ መግቢያ ገጽ እየተዛወሩ ነው...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3.5">
              {error && (
                <div className="p-3 rounded-lg bg-red-50 text-red-700 text-xs">
                  {error}
                </div>
              )}

              <Input
                label="የድርጅት ስም (Organization Name)"
                placeholder="Abyssinia Technology PLC"
                value={formData.organization_name}
                onChange={(e) => handleNameChange(e.target.value)}
                leftIcon={<Building2 className="w-4 h-4" />}
                required
                autoFocus
              />

              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="መለያ ስም (Tenant Slug)"
                  placeholder="abyssinia"
                  value={formData.slug}
                  onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                  required
                />
                <Input
                  label="የግብር ከፋይ መለያ (TIN Number)"
                  placeholder="10 አሃዝ ቁጥር"
                  value={formData.tin_number}
                  onChange={(e) => setFormData({ ...formData, tin_number: e.target.value })}
                  leftIcon={<Hash className="w-4 h-4" />}
                />
              </div>

              <div className="pt-2 border-t border-zinc-100">
                <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-2">
                  የዋና አስተዳዳሪ መረጃ (Admin Account)
                </p>
              </div>

              <Input
                label="የአስተዳዳሪ ሙሉ ስም (Full Name)"
                placeholder="አበበ ከበደ"
                value={formData.admin_full_name}
                onChange={(e) => setFormData({ ...formData, admin_full_name: e.target.value })}
                leftIcon={<User className="w-4 h-4" />}
                required
              />

              <Input
                label="የአስተዳዳሪ ኢሜይል (Admin Email)"
                type="email"
                placeholder="admin@abyssinia.et"
                value={formData.admin_email}
                onChange={(e) => setFormData({ ...formData, admin_email: e.target.value })}
                leftIcon={<Mail className="w-4 h-4" />}
                required
              />

              <Input
                label="የይለፍ ቃል (Password)"
                type="password"
                placeholder="ቢያንስ 8 ፊደላት እና ቁጥር"
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
                ድርጅቱን ፍጠር (Provision Organization)
              </Button>
            </form>
          )}
        </div>

        <div className="text-center mt-6">
          <Link
            to="/login"
            className="text-xs text-zinc-500 hover:text-zinc-800 transition-colors"
          >
            አስቀድመው አካውንት አሎት? (Already have an account? Sign In)
          </Link>
        </div>
      </div>
    </div>
  );
};
