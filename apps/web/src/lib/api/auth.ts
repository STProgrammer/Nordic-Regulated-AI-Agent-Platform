import {
  apiRequest,
  currentUserSchema,
  jsonRequest,
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
    return apiRequest('/api/auth/login', currentUserSchema, jsonRequest('POST', input));
  },

  logout(): Promise<{ logged_out: true }> {
    return apiRequest('/api/auth/logout', logoutDataSchema, { method: 'POST' });
  },

  updatePreferredLanguage(preferredLanguage: 'nb' | 'en'): Promise<CurrentUser> {
    return apiRequest(
      '/api/auth/me/preferred-language',
      currentUserSchema,
      jsonRequest(
        'PUT',
        languagePreferenceInputSchema.parse({ preferred_language: preferredLanguage }),
      ),
    );
  },
};
