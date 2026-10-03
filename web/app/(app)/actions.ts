'use server';

import { revalidatePath } from 'next/cache';
import { currentUser } from '@/auth';
import { dismissAction } from '@/lib/data';

export async function dismiss(formData: FormData) {
  if (!(await currentUser())) throw new Error('Not signed in');
  const id = Number(formData.get('orderId'));
  if (!Number.isInteger(id) || id <= 0) throw new Error('Bad order id');
  await dismissAction(id);
  revalidatePath('/');
}
