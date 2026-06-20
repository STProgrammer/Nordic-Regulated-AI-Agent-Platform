import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().trim().email(),
  password: z.string().min(1).max(512),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
