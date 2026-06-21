import { afterEach, describe, expect, it, vi } from 'vitest';

import { evaluationsApi } from '@/lib/api/evaluations';
import { ApiFailure } from '@/lib/api/contracts';
import { evaluationQueryKeys } from '@/lib/evaluations/query';

const runId = '11111111-1111-4111-8111-111111111111';
const resultId = '22222222-2222-4222-8222-222222222222';

function response(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
}

function metrics() {
  return {
    average_latency_ms: null,
    case_total: 1,
    citation_mean: 1,
    cost_sample_count: 0,
    failed_case_total: 0,
    failure_code_counts: [],
    latency_sample_count: 0,
    passed_case_total: 1,
    refusal_mean: 1,
    retrieval_mean: 1,
    risk_mean: 1,
    routing_mean: 1,
    run_failure_code: null,
    structural_faithfulness_mean: 1,
    total_cost_estimate: null,
  };
}

function run() {
  return {
    dataset_content_hash: 'a'.repeat(64),
    dataset_key: 'nordic-regulated-core-v1',
    dataset_version: 'v1',
    evaluation_run_id: runId,
    finished_at: '2030-01-01T00:00:01Z',
    metrics: metrics(),
    pass_fail: 'pass',
    started_at: '2030-01-01T00:00:00Z',
    status: 'completed',
  };
}

afterEach(() => vi.unstubAllGlobals());

describe('Evaluation API client', () => {
  it('uses a credentialed, typed relative request for current-tenant run history', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        data: { has_more: false, items: [run()], limit: 25, offset: 0, total: 1 },
        meta: {},
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(evaluationsApi.listRuns()).resolves.toMatchObject({ total: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/evaluations/runs?limit=25&offset=0',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(evaluationQueryKeys.result(runId, resultId)).toEqual([
      'evaluations',
      'run',
      runId,
      'result',
      resultId,
    ]);
  });

  it('rejects an unallowlisted evaluation payload before it reaches the UI', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        response({
          data: {
            ...run(),
            metrics: { ...metrics(), summary_metrics: { prompt: 'phase26-hidden-sentinel' } },
          },
          meta: {},
        }),
      ),
    );

    await expect(evaluationsApi.start('nordic-regulated-core-v1')).rejects.toMatchObject({
      code: 'invalid_response',
      status: 200,
    } satisfies Partial<ApiFailure>);
  });

  it('downloads only the server-generated Markdown report contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('# Evalueringsrapport\n', {
        headers: {
          'Content-Disposition': 'attachment; filename="evaluation-report.md"',
          'Content-Type': 'text/markdown; charset=utf-8',
        },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(evaluationsApi.exportReport(runId, 'nb')).resolves.toEqual({
      content: '# Evalueringsrapport\n',
      filename: 'evaluation-report.md',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/evaluations/runs/${runId}/report`,
      expect.objectContaining({
        body: '{}',
        credentials: 'include',
        headers: expect.objectContaining({ 'Accept-Language': 'nb' }),
        method: 'POST',
      }),
    );
  });

  it('rejects an unsafe report response header', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response('unsafe', { headers: { 'Content-Type': 'text/plain' } })),
    );

    await expect(evaluationsApi.exportReport(runId, 'en')).rejects.toMatchObject({
      code: 'invalid_response',
      status: 200,
    } satisfies Partial<ApiFailure>);
  });
});
