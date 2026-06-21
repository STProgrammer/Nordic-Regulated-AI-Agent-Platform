import {
  apiRequest,
  controlledMemoryEntryListSchema,
  controlledMemoryEntrySchema,
  controlledMemoryInputSchema,
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
    return apiRequest(memoryPath('/settings'), memorySettingsSchema, {
      body: JSON.stringify({ enabled }),
      headers: { 'Content-Type': 'application/json' },
      method: 'PUT',
    });
  },

  listEntries(includeArchived = true) {
    return apiRequest(
      `${memoryPath('/entries')}?include_archived=${includeArchived ? 'true' : 'false'}`,
      controlledMemoryEntryListSchema,
    );
  },

  createEntry(input: ControlledMemoryInput) {
    return apiRequest(memoryPath('/entries'), controlledMemoryEntrySchema, {
      body: JSON.stringify(controlledMemoryInputSchema.parse(input)),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
  },

  reviseEntry(entryId: string, input: ControlledMemoryInput) {
    return apiRequest(
      memoryPath(`/entries/${encodeURIComponent(entryId)}`),
      controlledMemoryEntrySchema,
      {
        body: JSON.stringify({ content: controlledMemoryInputSchema.parse(input).content }),
        headers: { 'Content-Type': 'application/json' },
        method: 'PUT',
      },
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
