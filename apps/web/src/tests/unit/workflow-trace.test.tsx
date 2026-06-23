import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { WorkflowTrace } from '@/components/workflow/workflow-trace';
import { authApi } from '@/lib/api/auth';
import { documentsApi } from '@/lib/api/documents';
import { workflowsApi } from '@/lib/api/workflows';
import { renderWithProviders } from '@/tests/test-utils';

vi.mock('@/lib/api/auth', () => ({
  authApi: { getCurrentUser: vi.fn(), login: vi.fn(), logout: vi.fn() },
}));
vi.mock('@/lib/api/documents', () => ({ documentsApi: { getContext: vi.fn() } }));
vi.mock('@/lib/api/workflows', () => ({ workflowsApi: { getTrace: vi.fn() } }));

const runId = '33333333-3333-4333-8333-333333333333';
const caseId = '44444444-4444-4444-8444-444444444444';

describe('WorkflowTrace', () => {
  it('renders safe empty states without inventing tool, model, or source calls', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      display_name: 'Synthetic auditor',
      organization_id: '11111111-1111-4111-8111-111111111111',
      preferred_language: 'nb',
      roles: ['Read-only Auditor'],
      user_id: '22222222-2222-4222-8222-222222222222',
    });
    vi.mocked(workflowsApi.getTrace).mockResolvedValue({
      final_state: { status: 'completed' },
      header: {
        case_id: caseId,
        duration_ms: 12,
        final_error_code: null,
        finished_at: '2030-01-01T00:00:01Z',
        started_at: '2030-01-01T00:00:00Z',
        status: 'completed',
        total_cost_estimate: null,
        total_tokens: null,
        workflow_name: 'synthetic',
        workflow_run_id: runId,
        workflow_version: 'v1',
      },
      model_calls: [],
      nodes: [],
      sources: [],
      tool_calls: [],
      unavailable_source_count: 0,
    });

    renderWithProviders(<WorkflowTrace workflowRunId={runId} />);

    expect(await screen.findByRole('heading', { name: 'Arbeidsflytspor' })).toBeInTheDocument();
    expect(screen.getByText('Ingen verktøykall ble registrert.')).toBeInTheDocument();
    expect(screen.getByText('Ingen modellkall ble registrert.')).toBeInTheDocument();
    expect(
      screen.getByText('Ingen tilgjengelige kildereferanser ble registrert.'),
    ).toBeInTheDocument();
    expect(documentsApi.getContext).not.toHaveBeenCalled();
  });

  it('uses a non-plural label for the tool-call retry column', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      display_name: 'Synthetic auditor',
      organization_id: '11111111-1111-4111-8111-111111111111',
      preferred_language: 'nb',
      roles: ['Read-only Auditor'],
      user_id: '22222222-2222-4222-8222-222222222222',
    });
    vi.mocked(workflowsApi.getTrace).mockResolvedValue({
      final_state: {},
      header: {
        case_id: caseId,
        duration_ms: 12,
        final_error_code: null,
        finished_at: '2030-01-01T00:00:01Z',
        started_at: '2030-01-01T00:00:00Z',
        status: 'completed',
        total_cost_estimate: null,
        total_tokens: null,
        workflow_name: 'synthetic',
        workflow_run_id: runId,
        workflow_version: 'v1',
      },
      model_calls: [],
      nodes: [],
      sources: [],
      tool_calls: [
        {
          duration_ms: 5,
          error_code: null,
          finished_at: '2030-01-01T00:00:01Z',
          input_summary: {},
          node_run_id: null,
          output_summary: {},
          retry_count: 0,
          started_at: '2030-01-01T00:00:00Z',
          status: 'completed',
          tool_call_id: '55555555-5555-4555-8555-555555555555',
          tool_name: 'synthetic_tool',
        },
      ],
      unavailable_source_count: 0,
    });

    renderWithProviders(<WorkflowTrace workflowRunId={runId} />);

    expect(await screen.findByRole('columnheader', { name: 'Nye forsøk' })).toBeInTheDocument();
  });
});
