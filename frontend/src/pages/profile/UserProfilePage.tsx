import React, { useState } from 'react';
import { User, Phone, Lock, CheckCircle2, KeyRound } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { authApi } from '../../api/client';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';

export const UserProfilePage: React.FC = () => {
  const { user, updateUser } = useAuth();

  // Profile fields
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [phoneNumber, setPhoneNumber] = useState(user?.phone_number || '');
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);

  // Password fields
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) return;

    setIsUpdatingProfile(true);
    setProfileSuccess(false);
    try {
      const updated = await authApi.updateProfile({
        full_name: fullName.trim(),
        phone_number: phoneNumber.trim() || undefined,
      });
      updateUser(updated);
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch {
      // ignore
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(false);

    if (newPassword !== confirmPassword) {
      setPasswordError('አዲሱ የይለፍ ቃል እና ማረጋገጫው አይዛመዱም (Passwords do not match)');
      return;
    }

    setIsChangingPassword(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setPasswordSuccess(false), 3000);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const resp = (err as { response?: { data?: { detail?: string } } }).response;
        setPasswordError(resp?.data?.detail || 'የይለፍ ቃሉን መቀየር አልተቻለም');
      } else {
        setPasswordError('ስህተት ተከስቷል');
      }
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 select-none font-sans">
      {/* Header */}
      <div className="pb-4 border-b border-zinc-100">
        <h1 className="text-lg font-semibold text-zinc-900 tracking-tight">
          የተጠቃሚ መለያ እና ደህንነት (Account & Security)
        </h1>
        <p className="text-xs text-zinc-500 mt-0.5">
          የግል መረጃዎችን ማስተካከል እና የይለፍ ቃል መቀየር
        </p>
      </div>

      {/* Organization Info Box */}
      <div className="bg-white rounded-2xl p-5 border border-zinc-200/60 shadow-xs flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-zinc-900 text-white flex items-center justify-center font-bold text-sm">
            {user?.organization.name?.slice(0, 2).toUpperCase() || 'EO'}
          </div>
          <div>
            <h3 className="text-xs font-semibold text-zinc-900">{user?.organization.name}</h3>
            <p className="text-[11px] text-zinc-400">የስራ መለያ፦ {user?.email}</p>
          </div>
        </div>
        <Badge variant={user?.role === 'ADMIN' ? 'default' : 'neutral'}>
          {user?.role}
        </Badge>
      </div>

      {/* 1. Profile Update Form */}
      <div className="bg-white rounded-2xl p-6 border border-zinc-200/60 shadow-xs space-y-4">
        <h3 className="text-sm font-semibold text-zinc-900">የግል መረጃ (Profile Details)</h3>

        {profileSuccess && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 text-emerald-800 text-xs">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>መረጃዎ በተሳካ ሁኔታ ተሻሽሏል! (Profile updated successfully)</span>
          </div>
        )}

        <form onSubmit={handleUpdateProfile} className="space-y-4">
          <Input
            label="ሙሉ ስም (Full Name)"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            leftIcon={<User className="w-4 h-4" />}
            required
          />

          <Input
            label="ስልክ ቁጥር (Phone Number)"
            placeholder="+251 91 123 4567"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            leftIcon={<Phone className="w-4 h-4" />}
          />

          <div className="flex justify-end pt-2">
            <Button variant="primary" size="sm" type="submit" isLoading={isUpdatingProfile}>
              መረጃ አስቀምጥ (Save Profile)
            </Button>
          </div>
        </form>
      </div>

      {/* 2. Change Password Form */}
      <div className="bg-white rounded-2xl p-6 border border-zinc-200/60 shadow-xs space-y-4">
        <h3 className="text-sm font-semibold text-zinc-900">የይለፍ ቃል መቀየር (Change Password)</h3>

        {passwordSuccess && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 text-emerald-800 text-xs">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>የይለፍ ቃልዎ በተሳካ ሁኔታ ተቀይሯል! (Password changed)</span>
          </div>
        )}

        {passwordError && (
          <div className="p-3 rounded-lg bg-red-50 text-red-700 text-xs">
            {passwordError}
          </div>
        )}

        <form onSubmit={handleChangePassword} className="space-y-3.5">
          <Input
            label="የአሁኑ የይለፍ ቃል (Current Password)"
            type="password"
            placeholder="••••••••"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            leftIcon={<KeyRound className="w-4 h-4" />}
            required
          />

          <Input
            label="አዲስ የይለፍ ቃል (New Password)"
            type="password"
            placeholder="ቢያንስ 8 ፊደላት እና ቁጥር"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            leftIcon={<Lock className="w-4 h-4" />}
            required
          />

          <Input
            label="አዲሱን የይለፍ ቃል ያረጋግጡ (Confirm New Password)"
            type="password"
            placeholder="••••••••"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            leftIcon={<Lock className="w-4 h-4" />}
            required
          />

          <div className="flex justify-end pt-2">
            <Button variant="primary" size="sm" type="submit" isLoading={isChangingPassword}>
              የይለፍ ቃል ቀይር (Update Password)
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
