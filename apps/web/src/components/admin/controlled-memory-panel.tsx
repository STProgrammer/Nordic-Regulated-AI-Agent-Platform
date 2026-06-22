'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { formatTimestamp } from '@/lib/formatting';
import { useCurrentUser } from '@/lib/auth/query';
import {
  type ControlledMemoryEntry,
  type ControlledMemoryInput,
  type ControlledMemoryType,
} from '@/lib/api/contracts';
import { useControlledMemory, useControlledMemoryActions } from '@/lib/memory/query';
import type { AppLocale } from '@/i18n/routing';
import { useLocale } from 'next-intl';

const adminRole = 'Admin';

type EditorState = {
  entryId: string | null;
  hintCategory: 'drafting_clarity' | 'workflow_presentation';
  locale: 'nb' | 'en';
  preferredTerm: string;
  sourceTerm: string;
  style: 'plain' | 'formal';
  type: ControlledMemoryType;
  guidance: string;
};

type PresentationContent = { style: 'plain' | 'formal'; workflow: 'drafting' };
type TerminologyContent = { locale: 'nb' | 'en'; preferred_term: string; source_term: string };
type HintContent = { category: EditorState['hintCategory']; guidance: string };

const initialEditor: EditorState = {
  entryId: null,
  hintCategory: 'drafting_clarity',
  locale: 'nb',
  preferredTerm: '',
  sourceTerm: '',
  style: 'plain',
  type: 'approved_terminology',
  guidance: '',
};

/** Admin UI for only the Phase-24 closed, inspectable memory categories. */
export function ControlledMemoryPanel() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations('controlledMemory');
  const user = useCurrentUser();
  const canManage = user.data?.roles.includes(adminRole) ?? false;
  const { entries, settings } = useControlledMemory(canManage);
  const actions = useControlledMemoryActions();
  const [editor, setEditor] = useState<EditorState>(initialEditor);
  const [notice, setNotice] = useState<string | null>(null);

  function setField<Key extends keyof EditorState>(key: Key, value: EditorState[Key]) {
    setEditor((current) => ({ ...current, [key]: value }));
  }

  async function save() {
    const input = editorInput(editor);
    try {
      if (editor.entryId) {
        await actions.revise.mutateAsync({ entryId: editor.entryId, input });
        setNotice(t('updated'));
      } else {
        await actions.create.mutateAsync(input);
        setNotice(t('created'));
      }
      setEditor(initialEditor);
    } catch {
      setNotice(t('operationUnavailable'));
    }
  }

  async function setEnabled(enabled: boolean) {
    if (!enabled && !window.confirm(t('disableConfirm'))) return;
    try {
      await actions.settings.mutateAsync(enabled);
      setNotice(enabled ? t('enabled') : t('disabled'));
    } catch {
      setNotice(t('operationUnavailable'));
    }
  }

  async function archive(entry: ControlledMemoryEntry) {
    if (!window.confirm(t('archiveConfirm'))) return;
    try {
      await actions.archive.mutateAsync(entry.memory_entry_id);
      setNotice(t('archivedNotice'));
    } catch {
      setNotice(t('operationUnavailable'));
    }
  }

  if (user.isPending) {
    return <p role="status">{t('loading')}</p>;
  }
  if (!canManage) {
    return <Alert>{t('denied')}</Alert>;
  }

  const isBusy = actions.create.isPending || actions.revise.isPending || actions.settings.isPending;
  return (
    <section
      aria-labelledby="controlled-memory-title"
      className="space-y-6"
      data-testid="controlled-memory"
    >
      <div>
        <h1 className="text-3xl font-semibold tracking-tight" id="controlled-memory-title">
          {t('title')}
        </h1>
        <p className="mt-2 text-slate-700">{t('description')}</p>
      </div>
      <Alert>
        <p className="font-medium">{t('allowedTitle')}</p>
        <p className="mt-1">{t('allowedDescription')}</p>
        <p className="mt-1">{t('forbiddenDescription')}</p>
      </Alert>
      <div className="nordic-surface rounded-xl p-5">
        <h2 className="text-xl font-semibold">{t('settingTitle')}</h2>
        {settings.isPending ? (
          <p className="mt-2" role="status">
            {t('loading')}
          </p>
        ) : null}
        {settings.isError ? <Alert>{t('unavailable')}</Alert> : null}
        {settings.data ? (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <p>{settings.data.enabled ? t('statusEnabled') : t('statusDisabled')}</p>
            <Button
              disabled={isBusy}
              onClick={() => void setEnabled(!settings.data?.enabled)}
              type="button"
            >
              {settings.data.enabled ? t('disable') : t('enable')}
            </Button>
          </div>
        ) : null}
      </div>
      <form
        className="nordic-surface space-y-4 rounded-xl p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">
            {editor.entryId ? t('reviseTitle') : t('createTitle')}
          </h2>
          {editor.entryId ? (
            <Button onClick={() => setEditor(initialEditor)} type="button">
              {t('cancel')}
            </Button>
          ) : null}
        </div>
        <label className="block font-medium" htmlFor="memory-type">
          {t('typeLabel')}
        </label>
        <select
          className="mt-1 min-h-10 w-full rounded-md border border-slate-300 bg-white px-3"
          disabled={editor.entryId !== null}
          id="memory-type"
          onChange={(event) => setField('type', event.target.value as ControlledMemoryType)}
          value={editor.type}
        >
          <option value="approved_terminology">{t('typeTerminology')}</option>
          <option value="workflow_presentation_preference">{t('typePresentation')}</option>
          <option value="process_hint">{t('typeHint')}</option>
        </select>
        <EditorFields editor={editor} setField={setField} />
        <Button disabled={isBusy} type="submit">
          {editor.entryId ? t('saveRevision') : t('create')}
        </Button>
      </form>
      <section aria-labelledby="memory-entries-title" className="space-y-3">
        <h2 className="text-xl font-semibold" id="memory-entries-title">
          {t('entriesTitle')}
        </h2>
        {entries.isPending ? <p role="status">{t('loading')}</p> : null}
        {entries.isError ? <Alert>{t('unavailable')}</Alert> : null}
        {entries.data?.items.length === 0 ? <p>{t('empty')}</p> : null}
        <ul aria-label={t('entriesTitle')} className="space-y-3">
          {entries.data?.items.map((entry) => (
            <li className="nordic-surface rounded-xl p-5" key={entry.memory_entry_id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{entryTitle(entry, t)}</h3>
                  <p className="mt-1 text-slate-700">{entryDescription(entry)}</p>
                  <p className="mt-2 text-sm text-slate-600">
                    {entry.is_active ? t('active') : t('archivedStatus')} ·{' '}
                    {formatTimestamp(entry.updated_at, locale)}
                  </p>
                </div>
                {entry.is_active ? (
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => setEditor(editorFromEntry(entry))} type="button">
                      {t('revise')}
                    </Button>
                    <Button onClick={() => void archive(entry)} type="button">
                      {t('archive')}
                    </Button>
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </section>
      <p aria-live="polite" role="status">
        {notice}
      </p>
    </section>
  );
}

function EditorFields({
  editor,
  setField,
}: {
  editor: EditorState;
  setField: <Key extends keyof EditorState>(key: Key, value: EditorState[Key]) => void;
}) {
  const t = useTranslations('controlledMemory');
  if (editor.type === 'workflow_presentation_preference') {
    return (
      <label className="block font-medium" htmlFor="presentation-style">
        {t('styleLabel')}
        <select
          className="mt-1 min-h-10 w-full rounded-md border border-slate-300 bg-white px-3"
          id="presentation-style"
          onChange={(event) => setField('style', event.target.value as EditorState['style'])}
          value={editor.style}
        >
          <option value="plain">{t('stylePlain')}</option>
          <option value="formal">{t('styleFormal')}</option>
        </select>
      </label>
    );
  }
  if (editor.type === 'approved_terminology') {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block font-medium" htmlFor="term-locale">
          {t('localeLabel')}
          <select
            className="mt-1 min-h-10 w-full rounded-md border border-slate-300 bg-white px-3"
            id="term-locale"
            onChange={(event) => setField('locale', event.target.value as EditorState['locale'])}
            value={editor.locale}
          >
            <option value="nb">{t('localeNb')}</option>
            <option value="en">{t('localeEn')}</option>
          </select>
        </label>
        <label className="block font-medium" htmlFor="source-term">
          {t('sourceTermLabel')}
          <input
            className="mt-1 min-h-10 w-full rounded-md border border-slate-300 px-3"
            id="source-term"
            maxLength={80}
            onChange={(event) => setField('sourceTerm', event.target.value)}
            required
            value={editor.sourceTerm}
          />
        </label>
        <label className="block font-medium" htmlFor="preferred-term">
          {t('preferredTermLabel')}
          <input
            className="mt-1 min-h-10 w-full rounded-md border border-slate-300 px-3"
            id="preferred-term"
            maxLength={80}
            onChange={(event) => setField('preferredTerm', event.target.value)}
            required
            value={editor.preferredTerm}
          />
        </label>
      </div>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="block font-medium" htmlFor="hint-category">
        {t('hintCategoryLabel')}
        <select
          className="mt-1 min-h-10 w-full rounded-md border border-slate-300 bg-white px-3"
          id="hint-category"
          onChange={(event) =>
            setField('hintCategory', event.target.value as EditorState['hintCategory'])
          }
          value={editor.hintCategory}
        >
          <option value="drafting_clarity">{t('hintClarity')}</option>
          <option value="workflow_presentation">{t('hintPresentation')}</option>
        </select>
      </label>
      <label className="block font-medium" htmlFor="hint-guidance">
        {t('guidanceLabel')}
        <input
          className="mt-1 min-h-10 w-full rounded-md border border-slate-300 px-3"
          id="hint-guidance"
          maxLength={240}
          onChange={(event) => setField('guidance', event.target.value)}
          required
          value={editor.guidance}
        />
      </label>
    </div>
  );
}

function editorInput(editor: EditorState): ControlledMemoryInput {
  if (editor.type === 'workflow_presentation_preference')
    return { memory_type: editor.type, content: { workflow: 'drafting', style: editor.style } };
  if (editor.type === 'approved_terminology')
    return {
      memory_type: editor.type,
      content: {
        locale: editor.locale,
        source_term: editor.sourceTerm,
        preferred_term: editor.preferredTerm,
      },
    };
  return {
    memory_type: editor.type,
    content: { category: editor.hintCategory, guidance: editor.guidance },
  };
}

function editorFromEntry(entry: ControlledMemoryEntry): EditorState {
  if (entry.memory_type === 'workflow_presentation_preference') {
    const content = entry.content as PresentationContent;
    return {
      ...initialEditor,
      entryId: entry.memory_entry_id,
      type: entry.memory_type,
      style: content.style,
    };
  }
  if (entry.memory_type === 'approved_terminology') {
    const content = entry.content as TerminologyContent;
    return {
      ...initialEditor,
      entryId: entry.memory_entry_id,
      type: entry.memory_type,
      locale: content.locale,
      sourceTerm: content.source_term,
      preferredTerm: content.preferred_term,
    };
  }
  const content = entry.content as HintContent;
  return {
    ...initialEditor,
    entryId: entry.memory_entry_id,
    type: entry.memory_type,
    hintCategory: content.category,
    guidance: content.guidance,
  };
}

function entryTitle(
  entry: ControlledMemoryEntry,
  t: ReturnType<typeof useTranslations<'controlledMemory'>>,
) {
  return t(
    entry.memory_type === 'approved_terminology'
      ? 'typeTerminology'
      : entry.memory_type === 'process_hint'
        ? 'typeHint'
        : 'typePresentation',
  );
}

function entryDescription(entry: ControlledMemoryEntry): string {
  if (entry.memory_type === 'approved_terminology') {
    const content = entry.content as TerminologyContent;
    return `${content.source_term} → ${content.preferred_term}`;
  }
  if (entry.memory_type === 'process_hint') return (entry.content as HintContent).guidance;
  return (entry.content as PresentationContent).style;
}
