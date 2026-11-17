import ChangePasswordForm from '../components/ChangePasswordForm';
import DeleteAccountSection from '../components/DeleteAccountSection';
import ProfileForm from '../components/ProfileForm';

/** Configurações (F-11 a F-13): editar dados cadastrais, trocar a senha e excluir a conta. */
export default function SettingsPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          Configurações
        </h1>
        <p className="mt-2 text-slate-400">Seus dados de cadastro, sua senha e sua conta.</p>
      </div>
      <ProfileForm />
      <ChangePasswordForm />
      <DeleteAccountSection />
    </div>
  );
}
