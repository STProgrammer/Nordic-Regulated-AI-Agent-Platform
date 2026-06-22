import {
  apiRequest,
  ApiFailure,
  evaluationDatasetListSchema,
  evaluationResultSchema,
  evaluationRunDetailSchema,
  evaluationRunListSchema,
  evaluationRunSchema,
  jsonRequest,
  type EvaluationDatasetList,
  type EvaluationResult,
  type EvaluationRun,
  type EvaluationRunDetail,
  type EvaluationRunList,
  type EvaluationStatus,
} from '@/lib/api/contracts';

function evaluationsPath(path = ''): string {
  return `/api/evaluations${path}`;
}

function runPath(runId: string, path = ''): string {
  return evaluationsPath(`/runs/${encodeURIComponent(runId)}${path}`);
}

export type EvaluationReport = {
  content: string;
  filename: 'evaluation-report.md';
};

export const evaluationsApi = {
  listDatasets(): Promise<EvaluationDatasetList> {
    return apiRequest(evaluationsPath('/datasets'), evaluationDatasetListSchema);
  },

  start(datasetKey: string): Promise<EvaluationRun> {
    return apiRequest(
      evaluationsPath(`/datasets/${encodeURIComponent(datasetKey)}/runs`),
      evaluationRunSchema,
      jsonRequest('POST', {}),
    );
  },

  listRuns({
    limit = 25,
    offset = 0,
    status,
  }: {
    limit?: number;
    offset?: number;
    status?: EvaluationStatus;
  } = {}): Promise<EvaluationRunList> {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (status) query.set('status', status);
    return apiRequest(`${evaluationsPath('/runs')}?${query.toString()}`, evaluationRunListSchema);
  },

  getRun(runId: string): Promise<EvaluationRunDetail> {
    return apiRequest(runPath(runId), evaluationRunDetailSchema);
  },

  getResult(runId: string, resultId: string): Promise<EvaluationResult> {
    return apiRequest(
      runPath(runId, `/results/${encodeURIComponent(resultId)}`),
      evaluationResultSchema,
    );
  },

  async exportReport(runId: string, locale: 'nb' | 'en'): Promise<EvaluationReport> {
    let response: Response;
    try {
      response = await fetch(runPath(runId, '/report'), {
        body: JSON.stringify({}),
        credentials: 'include',
        headers: {
          Accept: 'text/markdown',
          'Accept-Language': locale,
          'Content-Type': 'application/json',
        },
        method: 'POST',
      });
    } catch {
      throw new ApiFailure({ code: 'network_error', status: 0 });
    }

    if (!response.ok) {
      throw new ApiFailure({ code: 'api_error', status: response.status });
    }
    const contentType = response.headers.get('content-type') ?? '';
    const disposition = response.headers.get('content-disposition');
    if (
      !contentType.startsWith('text/markdown') ||
      disposition !== 'attachment; filename="evaluation-report.md"'
    ) {
      throw new ApiFailure({ code: 'invalid_response', status: response.status });
    }
    const content = await response.text();
    if (!content) {
      throw new ApiFailure({ code: 'invalid_response', status: response.status });
    }
    return { content, filename: 'evaluation-report.md' };
  },
};
