import { redirect } from 'next/navigation';

/** Старый адрес каталога. */
export default function TalentRedirect() {
  redirect('/freelancers');
}
