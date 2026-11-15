import ChangePasswordForm from '../components/ChangePasswordForm';
import ProfileForm from '../components/ProfileForm';

/** Configurações (F-11 e F-12): editar dados cadastrais e trocar a senha. */
export default function SettingsPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          Configurações
        </h1>
        <p className="mt-2 text-slate-400">Mantenha seus dados de cadastro e sua senha em dia.</p>
      </div>
      <ProfileForm />
      <ChangePasswordForm />
    </div>
  );
}
