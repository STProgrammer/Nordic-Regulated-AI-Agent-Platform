import {
  apiRequest,
  controlledMemoryEntryListSchema,
  controlledMemoryEntrySchema,
  controlledMemoryInputSchema,
  jsonRequest,
  memorySettingsSchema,
  type ControlledMemoryInput,
} from '@/lib/api/contracts';

function memoryPath(path = ''): string {
  return `/api/admin/memory${path}`;
}

export const memoryApi = {
  getSettings() {
    return apiRequest(memoryPath('/settings'), memorySettingsSchema);
  },

  updateSettings(enabled: boolean) {
    return apiRequest(
      memoryPath('/settings'),
      memorySettingsSchema,
      jsonRequest('PUT', { enabled }),
    );
  },

  listEntries(includeArchived = true) {
    return apiRequest(
      `${memoryPath('/entries')}?include_archived=${includeArchived ? 'true' : 'false'}`,
      controlledMemoryEntryListSchema,
    );
  },

  addEntry(input: ControlledMemoryInput) {
    return apiRequest(
      memoryPath('/entries'),
      controlledMemoryEntrySchema,
      jsonRequest('POST', controlledMemoryInputSchema.parse(input)),
    );
  },

  reviseEntry(entryId: string, input: ControlledMemoryInput) {
    return apiRequest(
      memoryPath(`/entries/${encodeURIComponent(entryId)}`),
      controlledMemoryEntrySchema,
      jsonRequest('PUT', { content: controlledMemoryInputSchema.parse(input).content }),
    );
  },

  archiveEntry(entryId: string) {
    return apiRequest(
      memoryPath(`/entries/${encodeURIComponent(entryId)}/archive`),
      controlledMemoryEntrySchema,
      {
        method: 'POST',
      },
    );
  },
};
