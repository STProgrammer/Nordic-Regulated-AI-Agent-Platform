import { z } from 'zod';

const errorDetailSchema = z.object({
  code: z.string().nullable().optional(),
  field: z.string().nullable().optional(),
  message: z.string(),
});

const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    details: z.array(errorDetailSchema).nullable().optional(),
    message: z.string(),
    request_id: z.string().nullable().optional(),
  }),
});

const responseMetaSchema = z.object({
  request_id: z.string().nullable().optional(),
});

export const currentUserSchema = z.object({
  display_name: z.string(),
  organization_id: z.string().uuid(),
  preferred_language: z.string(),
  roles: z.array(
    z.enum(['Admin', 'Compliance Reviewer', 'Case Worker', 'Manager', 'Read-only Auditor']),
  ),
  user_id: z.string().uuid(),
});

export const logoutDataSchema = z.object({
  logged_out: z.literal(true),
});

export const caseStatusSchema = z.enum([
  'new',
  'processing',
  'waiting_for_human_review',
  'needs_more_evidence',
  'approved',
  'rejected',
  'completed',
  'failed',
  'archived',
]);
export const casePrioritySchema = z.enum(['low', 'normal', 'high', 'urgent']);
export const caseDomainSchema = z.enum([
  'public_sector',
  'banking_compliance',
  'energy_operations',
  'internal_policy',
]);
export const caseLanguageSchema = z.enum(['nb', 'en']);
export const caseRiskLevelSchema = z.enum(['low', 'medium', 'high', 'critical']);
export const intakeCaseTypeSchema = z.enum([
  'case_support',
  'compliance_review',
  'operational_incident',
  'policy_question',
  'document_intelligence',
  'unknown',
]);
export const workflowRunStatusSchema = z.enum([
  'queued',
  'running',
  'waiting_for_human_review',
  'completed',
  'needs_more_evidence',
  'failed',
]);
export const detectedLanguageSchema = z.enum(['nb', 'en', 'unknown']);
export const suggestedWorkflowSchema = z.enum([
  'evidence',
  'extraction',
  'evidence_then_draft',
  'manual_review',
]);
export const intakeCorrectionReasonSchema = z.enum([
  'classification_review',
  'domain_review',
  'user_context',
]);

export const documentSourceStatusSchema = z.enum([
  'approved',
  'draft',
  'deprecated',
  'restricted',
  'archived',
]);
export const documentConfidentialityLevelSchema = z.enum([
  'public',
  'internal',
  'confidential',
  'restricted',
]);
export const documentParsingStatusSchema = z.enum(['pending', 'processing', 'parsed', 'failed']);
export const documentIndexingStatusSchema = z.enum([
  'not_ready',
  'pending',
  'indexing',
  'indexed',
  'failed',
]);

const isoDateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const isoTimestampSchema = z.string().datetime({ offset: true });

const caseSummarySchema = z.object({
  case_id: z.string().uuid(),
  case_number: z.string(),
  title: z.string(),
  language: caseLanguageSchema,
  domain: caseDomainSchema,
  priority: casePrioritySchema,
  status: caseStatusSchema,
  risk_level: caseRiskLevelSchema.nullable(),
  assigned_user_id: z.string().uuid().nullable(),
  submitted_by_user_id: z.string().uuid(),
  due_date: isoDateSchema.nullable(),
  inserted_at: isoTimestampSchema,
  updated_at: isoTimestampSchema,
});

export const caseDetailSchema = caseSummarySchema.extend({
  description: z.string(),
  case_type: z.string().nullable(),
  external_reference: z.string().nullable(),
  archived_at: isoTimestampSchema.nullable(),
});

export const caseListSchema = z.object({
  items: z.array(caseSummarySchema),
  limit: z.number().int().min(1).max(100),
  offset: z.number().int().min(0),
  total: z.number().int().min(0),
  has_more: z.boolean(),
});

export const caseAssigneeListSchema = z.object({
  items: z.array(
    z.object({
      user_id: z.string().uuid(),
      display_name: z.string().min(1),
    }),
  ),
});

export const documentDataSchema = z.object({
  document_id: z.string().uuid(),
  case_id: z.string().uuid(),
  uploaded_by_user_id: z.string().uuid(),
  title: z.string(),
  original_filename: z.string(),
  file_type: z.string(),
  mime_type: z.string(),
  file_size_bytes: z.number().int().nonnegative(),
  source_status: documentSourceStatusSchema,
  confidentiality_level: documentConfidentialityLevelSchema,
  parsing_status: documentParsingStatusSchema,
  language: z.string().nullable(),
  page_count: z.number().int().nonnegative().nullable(),
  parsing_error: z.string().nullable(),
  indexing_status: documentIndexingStatusSchema,
  indexing_error: z.string().nullable(),
  indexed_at: isoTimestampSchema.nullable(),
  inserted_at: isoTimestampSchema,
  updated_at: isoTimestampSchema,
});

export const documentListSchema = z.object({
  items: z.array(documentDataSchema),
  limit: z.number().int().min(1).max(100),
  offset: z.number().int().min(0),
  total: z.number().int().min(0),
  has_more: z.boolean(),
});

export const documentSourceContextSchema = z.object({
  document_id: z.string().uuid(),
  chunk_id: z.string().uuid(),
  document_title: z.string(),
  document_file_type: z.string(),
  source_status: documentSourceStatusSchema,
  page_number: z.number().int().nonnegative().nullable(),
  section_title: z.string().nullable(),
  context: z.string(),
  truncated: z.boolean(),
});

export const retrievalWarningCodeSchema = z.enum([
  'source_draft',
  'source_deprecated',
  'source_restricted',
  'source_archived',
]);
export const retrievalMethodSchema = z.enum(['semantic', 'keyword']);
export const retrievalSourceSchema = z.object({
  document_id: z.string().uuid(),
  document_title: z.string(),
  document_file_type: z.string(),
  chunk_id: z.string().uuid(),
  page_number: z.number().int().nonnegative().nullable(),
  section_title: z.string().nullable(),
  source_status: documentSourceStatusSchema,
  rank: z.number().int().min(1),
  rank_score: z.number().finite(),
  retrieval_methods: z.array(retrievalMethodSchema),
  excerpt: z.string(),
  warning_codes: z.array(retrievalWarningCodeSchema),
});

export const retrievalSearchInputSchema = z
  .object({
    case_id: z.string().uuid(),
    query: z.string().trim().min(1).max(2_000),
    limit: z.number().int().min(1).max(20).optional(),
    source_statuses: z.array(documentSourceStatusSchema).max(5).optional(),
    document_ids: z.array(z.string().uuid()).max(20).optional(),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.source_statuses &&
      new Set(value.source_statuses).size !== value.source_statuses.length
    ) {
      context.addIssue({ code: 'custom', message: 'Source statuses must be unique.' });
    }
    if (value.document_ids && new Set(value.document_ids).size !== value.document_ids.length) {
      context.addIssue({ code: 'custom', message: 'Document ids must be unique.' });
    }
  });

export const caseCreateInputSchema = z.object({
  title: z.string().trim().min(1).max(500),
  description: z.string().trim().min(1).max(20_000),
  domain: caseDomainSchema,
  priority: casePrioritySchema,
  language: caseLanguageSchema,
  due_date: isoDateSchema.optional(),
  external_reference: z.string().trim().min(1).max(255).optional(),
});

export const intakeStartInputSchema = z.object({ workflow: z.literal('intake') }).strict();
export const evidenceStartInputSchema = z.object({ workflow: z.literal('evidence') }).strict();
export const extractionStartInputSchema = z.object({ workflow: z.literal('extraction') }).strict();
export const draftingStartInputSchema = z
  .object({ workflow: z.literal('drafting'), output_language: caseLanguageSchema.optional() })
  .strict();
export const riskComplianceStartInputSchema = z
  .object({ workflow: z.literal('risk_compliance') })
  .strict();
export const intakeCorrectionInputSchema = z
  .object({
    case_type: intakeCaseTypeSchema,
    domain: caseDomainSchema,
    reason_code: intakeCorrectionReasonSchema.optional(),
  })
  .strict();

export const intakeResultSchema = z.object({
  declared_language: detectedLanguageSchema.nullable(),
  detected_language: detectedLanguageSchema.nullable(),
  language_mismatch: z.boolean().nullable(),
  case_type: intakeCaseTypeSchema.nullable(),
  recommended_domain: caseDomainSchema.nullable(),
  low_confidence: z.boolean().nullable(),
  pii_detected: z.boolean().nullable(),
  prompt_injection_detected: z.boolean().nullable(),
  preliminary_risk_level: caseRiskLevelSchema.nullable(),
  preliminary_risk_reasons: z.array(z.string()),
  preliminary_approval_required: z.boolean().nullable(),
  suggested_workflow: suggestedWorkflowSchema.nullable(),
  suggested_workflow_reasons: z.array(z.string()),
  classification_source: z.enum(['model', 'human_corrected']).nullable(),
});

export const evidenceReasonCodeSchema = z.enum([
  'no_eligible_sources',
  'insufficient_evidence',
  'contradictory_evidence',
]);
export const evidenceSourceSchema = z.object({
  citation_label: z.string().regex(/^S[1-9][0-9]*$/),
  document_id: z.string().uuid(),
  chunk_id: z.string().uuid(),
  source_status: z.literal('approved'),
  warning_codes: z.array(z.string()),
});
export const evidenceResultSchema = z.object({
  outcome: z.enum(['completed', 'needs_more_evidence']).nullable(),
  sufficient: z.boolean().nullable(),
  contradiction_detected: z.boolean().nullable(),
  reason_codes: z.array(evidenceReasonCodeSchema),
  citation_labels: z.array(z.string()),
  sources: z.array(evidenceSourceSchema),
});

export const extractionFieldKindSchema = z.enum([
  'people',
  'organizations',
  'dates',
  'deadlines',
  'amounts',
  'reference_numbers',
  'obligations',
  'tasks',
  'risks',
  'missing_information',
  'suggested_next_actions',
]);
export const confidenceBandSchema = z.enum(['high', 'low']);
export const stringItemsValueSchema = z
  .object({ items: z.array(z.string().min(1).max(500)).min(1).max(12) })
  .strict();
export const datesValueSchema = z.object({ dates: z.array(isoDateSchema).min(1).max(12) }).strict();
export const amountsValueSchema = z
  .object({
    amounts: z
      .array(
        z
          .object({
            amount: z.string().regex(/^\d+(\.\d{1,2})?$/),
            currency: z.string().regex(/^[A-Z]{3}$/),
            label: z.string().max(160).nullable(),
          })
          .strict(),
      )
      .min(1)
      .max(12),
  })
  .strict();
export const referencesValueSchema = z
  .object({ references: z.array(z.string().min(2).max(100)).min(1).max(12) })
  .strict();
export const extractionValueSchema = z.union([
  stringItemsValueSchema,
  datesValueSchema,
  amountsValueSchema,
  referencesValueSchema,
]);
export const extractionResultSchema = z.object({
  evidence_available: z.boolean().nullable(),
  extraction_schema: z.string().nullable(),
  extracted_field_count: z.number().int().nonnegative().nullable(),
  low_confidence_field_count: z.number().int().nonnegative().nullable(),
});
export const draftingResultSchema = z.object({
  evidence_available: z.boolean().nullable(),
  draft_available: z.boolean().nullable(),
  citation_count: z.number().int().nonnegative().nullable(),
  output_language: caseLanguageSchema.nullable(),
  draft_kind: z.enum(['response', 'internal_recommendation', 'summary', 'action_plan']).nullable(),
  reason_codes: z.array(z.string()),
});
export const riskReasonCodeSchema = z.enum([
  'pii_detected',
  'sensitive_domain',
  'weak_evidence',
  'contradictory_evidence',
  'missing_required_source',
  'low_confidence',
  'high_impact_action',
  'policy_conflict',
  'prompt_injection_detected',
]);
export const riskSafeNextStateSchema = z.enum([
  'assessment_complete',
  'human_review_required',
  'needs_more_evidence',
]);
export const riskResultSchema = z.object({
  final_risk_level: z.enum(['low', 'medium', 'high']).nullable(),
  risk_reasons: z.array(riskReasonCodeSchema),
  requires_approval: z.boolean().nullable(),
  safe_next_state: riskSafeNextStateSchema.nullable(),
});
export const riskAssessmentSchema = z.object({
  workflow_run_id: z.string().uuid(),
  risk_level: z.enum(['low', 'medium', 'high']),
  risk_reasons: z.array(riskReasonCodeSchema),
  requires_approval: z.boolean(),
  safe_next_state: riskSafeNextStateSchema,
});
export const draftCitationSchema = z.object({
  citation_label: z.string().regex(/^S[1-9][0-9]*$/),
  document_id: z.string().uuid(),
  chunk_id: z.string().uuid(),
});
export const draftSchema = z.object({
  workflow_run_id: z.string().uuid(),
  content: z.string().min(1).max(8_000),
  language: caseLanguageSchema,
  draft_kind: z.enum(['response', 'internal_recommendation', 'summary', 'action_plan']),
  citations: z.array(draftCitationSchema),
});
export const extractedFieldSchema = z.object({
  field_id: z.string().uuid(),
  workflow_run_id: z.string().uuid(),
  field_kind: extractionFieldKindSchema,
  field_value: extractionValueSchema,
  confidence_band: confidenceBandSchema,
  source_document_id: z.string().uuid().nullable(),
  source_chunk_id: z.string().uuid().nullable(),
  human_edited: z.boolean(),
  updated_at: isoTimestampSchema,
});
export const extractedFieldListSchema = z.object({ items: z.array(extractedFieldSchema) });
export const extractedFieldEditInputSchema = z
  .object({ field_value: extractionValueSchema })
  .strict();

export const workflowRunSchema = z.object({
  workflow_run_id: z.string().uuid(),
  workflow: z.enum([
    'intake',
    'evidence',
    'extraction',
    'drafting',
    'risk_compliance',
    'human_approval',
  ]),
  status: workflowRunStatusSchema,
  started_at: isoTimestampSchema,
  finished_at: isoTimestampSchema.nullable(),
  intake: intakeResultSchema.nullable().optional(),
  evidence: evidenceResultSchema.nullable().optional(),
  extraction: extractionResultSchema.nullable().optional(),
  drafting: draftingResultSchema.nullable().optional(),
  risk_compliance: riskResultSchema.nullable().optional(),
});

export const approvalLifecycleSchema = z.enum([
  'pending',
  'assigned',
  'approved',
  'rejected',
  'needs_more_evidence',
]);
export const reviewerDecisionSchema = z.enum([
  'approve',
  'edit_and_approve',
  'reject',
  'request_more_evidence',
]);
export const approvalSourceSchema = z
  .object({
    citation_label: z.string().regex(/^S[1-9][0-9]*$/),
    document_id: z.string().uuid(),
    chunk_id: z.string().uuid(),
  })
  .strict();
export const approvalExtractedFieldSchema = z
  .object({
    field_id: z.string().uuid(),
    field_kind: z.string(),
    field_value: z.record(z.string(), z.unknown()),
    source_document_id: z.string().uuid().nullable(),
    source_chunk_id: z.string().uuid().nullable(),
    human_edited: z.boolean(),
  })
  .strict();
export const approvalQueueItemSchema = z
  .object({
    approval_id: z.string().uuid(),
    case_id: z.string().uuid(),
    case_number: z.string(),
    case_title: z.string(),
    case_status: caseStatusSchema,
    risk_level: z.enum(['low', 'medium', 'high']),
    approval_status: approvalLifecycleSchema,
    assigned_user_id: z.string().uuid().nullable(),
    inserted_at: isoTimestampSchema,
  })
  .strict();
export const approvalQueueSchema = z
  .object({
    items: z.array(approvalQueueItemSchema),
    limit: z.number().int().min(1).max(100),
    offset: z.number().int().min(0),
    total: z.number().int().min(0),
    has_more: z.boolean(),
  })
  .strict();
export const approvalReviewPacketSchema = z
  .object({
    approval_id: z.string().uuid(),
    case_id: z.string().uuid(),
    case_number: z.string(),
    case_title: z.string(),
    case_status: caseStatusSchema,
    risk_level: z.enum(['low', 'medium', 'high']),
    risk_reasons: z.array(riskReasonCodeSchema),
    approval_status: approvalLifecycleSchema,
    workflow_status: z.enum([
      'queued',
      'running',
      'waiting_for_human_review',
      'completed',
      'failed',
    ]),
    assigned_user_id: z.string().uuid().nullable(),
    reviewer_user_id: z.string().uuid().nullable(),
    reviewer_comment: z.string().nullable(),
    decision: reviewerDecisionSchema.nullable(),
    decision_at: isoTimestampSchema.nullable(),
    ai_draft: z.string().min(1),
    final_text: z.string().nullable(),
    sources: z.array(approvalSourceSchema),
    extracted_fields: z.array(approvalExtractedFieldSchema),
  })
  .strict();
export const approvalActionResultSchema = z
  .object({
    approval_id: z.string().uuid(),
    approval_status: approvalLifecycleSchema,
    decision: reviewerDecisionSchema.nullable(),
    case_id: z.string().uuid(),
    workflow_status: z.enum([
      'queued',
      'running',
      'waiting_for_human_review',
      'completed',
      'failed',
    ]),
  })
  .strict();
export const approvalCommentInputSchema = z
  .object({ reviewer_comment: z.string().trim().min(1).max(2_000).optional() })
  .strict();
export const editAndApproveInputSchema = approvalCommentInputSchema.extend({
  final_text: z.string().trim().min(1).max(20_000),
});
export const approvalReassignInputSchema = z
  .object({ assigned_user_id: z.string().uuid() })
  .strict();

export function successEnvelopeSchema<DataSchema extends z.ZodType>(data: DataSchema) {
  return z.object({
    data,
    meta: responseMetaSchema,
  });
}

const unknownSuccessEnvelopeSchema = z.object({
  data: z.unknown(),
  meta: responseMetaSchema,
});

export type ApiErrorDetail = z.infer<typeof errorDetailSchema>;
export type CurrentUser = z.infer<typeof currentUserSchema>;
export type CaseStatus = z.infer<typeof caseStatusSchema>;
export type CasePriority = z.infer<typeof casePrioritySchema>;
export type CaseDomain = z.infer<typeof caseDomainSchema>;
export type CaseLanguage = z.infer<typeof caseLanguageSchema>;
export type CaseRiskLevel = z.infer<typeof caseRiskLevelSchema>;
export type CaseSummary = z.infer<typeof caseSummarySchema>;
export type CaseDetail = z.infer<typeof caseDetailSchema>;
export type CaseList = z.infer<typeof caseListSchema>;
export type CaseAssigneeList = z.infer<typeof caseAssigneeListSchema>;
export type CaseCreateInput = z.infer<typeof caseCreateInputSchema>;
export type IntakeCaseType = z.infer<typeof intakeCaseTypeSchema>;
export type WorkflowRunStatus = z.infer<typeof workflowRunStatusSchema>;
export type IntakeResult = z.infer<typeof intakeResultSchema>;
export type EvidenceResult = z.infer<typeof evidenceResultSchema>;
export type EvidenceSource = z.infer<typeof evidenceSourceSchema>;
export type ExtractionFieldKind = z.infer<typeof extractionFieldKindSchema>;
export type ExtractionValue = z.infer<typeof extractionValueSchema>;
export type ExtractedField = z.infer<typeof extractedFieldSchema>;
export type Draft = z.infer<typeof draftSchema>;
export type RiskReasonCode = z.infer<typeof riskReasonCodeSchema>;
export type RiskAssessment = z.infer<typeof riskAssessmentSchema>;
export type WorkflowRun = z.infer<typeof workflowRunSchema>;
export type ApprovalQueue = z.infer<typeof approvalQueueSchema>;
export type ApprovalReviewPacket = z.infer<typeof approvalReviewPacketSchema>;
export type ApprovalActionResult = z.infer<typeof approvalActionResultSchema>;
export type ApprovalCommentInput = z.infer<typeof approvalCommentInputSchema>;
export type EditAndApproveInput = z.infer<typeof editAndApproveInputSchema>;
export type ApprovalReassignInput = z.infer<typeof approvalReassignInputSchema>;
export type IntakeStartInput = z.infer<typeof intakeStartInputSchema>;
export type EvidenceStartInput = z.infer<typeof evidenceStartInputSchema>;
export type ExtractionStartInput = z.infer<typeof extractionStartInputSchema>;
export type DraftingStartInput = z.infer<typeof draftingStartInputSchema>;
export type RiskComplianceStartInput = z.infer<typeof riskComplianceStartInputSchema>;
export type ExtractedFieldEditInput = z.infer<typeof extractedFieldEditInputSchema>;
export type IntakeCorrectionInput = z.infer<typeof intakeCorrectionInputSchema>;
export type DocumentData = z.infer<typeof documentDataSchema>;
export type DocumentList = z.infer<typeof documentListSchema>;
export type DocumentSourceStatus = z.infer<typeof documentSourceStatusSchema>;
export type DocumentSourceContext = z.infer<typeof documentSourceContextSchema>;
export type RetrievalSource = z.infer<typeof retrievalSourceSchema>;
export type RetrievalSearchInput = z.infer<typeof retrievalSearchInputSchema>;
export type LoginInput = {
  email: string;
  password: string;
};

export class ApiFailure extends Error {
  readonly code: string;
  readonly details: readonly ApiErrorDetail[];
  readonly requestId: string | undefined;
  readonly retryAfterSeconds: number | undefined;
  readonly status: number;

  constructor({
    code,
    details = [],
    requestId,
    retryAfterSeconds,
    status,
  }: {
    code: string;
    details?: readonly ApiErrorDetail[];
    requestId?: string | undefined;
    retryAfterSeconds?: number | undefined;
    status: number;
  }) {
    super(code);
    this.name = 'ApiFailure';
    this.code = code;
    this.details = details;
    this.requestId = requestId;
    this.retryAfterSeconds = retryAfterSeconds;
    this.status = status;
  }
}

function responseRequestId(response: Response, bodyRequestId?: string | null): string | undefined {
  return response.headers.get('X-Request-ID') ?? bodyRequestId ?? undefined;
}

function retryAfterSeconds(response: Response): number | undefined {
  const retryAfter = response.headers.get('Retry-After');
  if (retryAfter === null || !/^\d+$/.test(retryAfter)) {
    return undefined;
  }

  const seconds = Number(retryAfter);
  return Number.isSafeInteger(seconds) && seconds >= 0 ? seconds : undefined;
}

async function readJson(response: Response): Promise<unknown> {
  const body = await response.text();
  if (!body) {
    return undefined;
  }

  try {
    return JSON.parse(body) as unknown;
  } catch {
    return undefined;
  }
}

export async function apiRequest<DataSchema extends z.ZodType>(
  path: string,
  dataSchema: DataSchema,
  init: RequestInit = {},
): Promise<z.infer<DataSchema>> {
  let response: Response;

  try {
    response = await fetch(path, {
      ...init,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...init.headers,
      },
    });
  } catch {
    throw new ApiFailure({ code: 'network_error', status: 0 });
  }

  const body = await readJson(response);
  if (!response.ok) {
    const parsedError = errorEnvelopeSchema.safeParse(body);
    if (!parsedError.success) {
      throw new ApiFailure({
        code: 'api_error',
        requestId: responseRequestId(response),
        retryAfterSeconds: retryAfterSeconds(response),
        status: response.status,
      });
    }

    const { error } = parsedError.data;
    throw new ApiFailure({
      code: error.code,
      details: error.details ?? [],
      requestId: responseRequestId(response, error.request_id),
      retryAfterSeconds: retryAfterSeconds(response),
      status: response.status,
    });
  }

  const parsedEnvelope = unknownSuccessEnvelopeSchema.safeParse(body);
  const parsedData = parsedEnvelope.success
    ? dataSchema.safeParse(parsedEnvelope.data.data)
    : undefined;
  if (parsedData === undefined || !parsedData.success) {
    throw new ApiFailure({
      code: 'invalid_response',
      requestId: responseRequestId(response),
      status: response.status,
    });
  }

  return parsedData.data;
}
