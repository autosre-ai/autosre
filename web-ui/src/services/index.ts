/**
 * AutoSRE V2 - API Services
 * 
 * Central export for all API services.
 */

// Base API client and utilities
export {
  default as api,
  ApiException,
  tokenManager,
  apiRequest,
  apiGet,
  apiPost,
  apiPut,
  apiPatch,
  apiDelete,
  type UnwrapApiResponse,
} from './api';

// Alerts API
export {
  alertsApi,
  default as alertsApiDefault,
  type AlertsListResponse,
  type AlertResponse,
  type AlertGroupsResponse,
  type AlertSummaryResponse,
  type SilencesListResponse,
  type SilenceResponse,
  type AcknowledgeAlertRequest,
  type ResolveAlertRequest,
  type BulkAlertActionRequest,
  type InvestigateAlertResponse,
} from './alerts';

// Investigations API
export {
  investigationsApi,
  default as investigationsApiDefault,
  type InvestigationsListResponse,
  type InvestigationResponse,
  type InvestigationSummaryResponse,
  type ObservationsResponse,
  type HypothesesResponse,
  type FindingsResponse,
  type AddObservationRequest,
  type CreateHypothesisRequest,
  type UpdateHypothesisRequest,
  type CreateFindingRequest,
  type RunAnalysisRequest,
  type InvestigationActionResponse,
} from './investigations';

// Chat API
export {
  chatApi,
  chatWebSocket,
  ChatWebSocket,
  default as chatApiDefault,
  type ChatSessionsListResponse,
  type ChatSessionResponse,
  type MessagesResponse,
  type MessageResponse,
  type ChatStatsResponse,
} from './chat';

// Runbooks API
export {
  runbooksApi,
  default as runbooksApiDefault,
  type RunbooksListResponse,
  type RunbookResponse,
  type RunbookExecutionsListResponse,
  type RunbookExecutionResponse,
  type RunbookSummaryResponse,
  type ValidateRunbookRequest,
  type ValidateRunbookResponse,
  type ApproveStepRequest,
  type CloneRunbookRequest,
  type RunbookVersionInfo,
} from './runbooks';
