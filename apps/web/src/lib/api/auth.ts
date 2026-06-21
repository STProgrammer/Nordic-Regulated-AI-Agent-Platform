import {
  apiRequest,
  currentUserSchema,
  logoutDataSchema,
  type CurrentUser,
  languagePreferenceInputSchema,
  type LoginInput,
} from './contracts';

export const authApi = {
  getCurrentUser(): Promise<CurrentUser> {
    return apiRequest('/api/auth/me', currentUserSchema);
  },

  login(input: LoginInput): Promise<CurrentUser> {
    return apiRequest('/api/auth/login', currentUserSchema, {
      body: JSON.stringify(input),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },

  logout(): Promise<{ logged_out: true }> {
    return apiRequest('/api/auth/logout', logoutDataSchema, { method: 'POST' });
  },

  updatePreferredLanguage(preferredLanguage: 'nb' | 'en'): Promise<CurrentUser> {
    return apiRequest('/api/auth/me/preferred-language', currentUserSchema, {
      body: JSON.stringify(
        languagePreferenceInputSchema.parse({ preferred_language: preferredLanguage }),
      ),
      headers: { 'Content-Type': 'application/json' },
      method: 'PUT',
    });
  },
};
