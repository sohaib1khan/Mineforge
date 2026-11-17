import type {
  AddonApplyResponse,
  AddonLibraryBackupCreateResponse,
  AddonLibraryBackupListResponse,
  AddonLibraryRestoreResponse,
  AddonListResponse,
  AddonUploadResponse,
  AllowlistResponse,
  BackupCreateResponse,
  BackupListResponse,
  BackupResponse,
  ConsoleLinesResponse,
  MeResponse,
  MessageResponse,
  OperationListResponse,
  OperationResponse,
  PermissionsResponse,
  PropertiesResponse,
  RestoreResponse,
  ServerStatusResponse,
  SetupStatusResponse,
  SwitchConsentResponse,
  SwitchStartResponse,
  SwitchStatusResponse,
  UserListResponse,
  UserPublic,
  UserRole,
  WorldImportResponse,
  WorldListResponse,
  HelpGuideListResponse,
  HelpGuideResponse,
  MetricsDashboardResponse,
  MetricsOverviewResponse,
  NetworkStatusResponse,
  VersionInfoResponse,
  WorldProfileResponse,
  WorldResponse,
  WorldAddonEntry,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

/** Turn FastAPI `detail` (string | validation list | object) into UI text. */
export function formatErrorDetail(detail: unknown): string | null {
  if (detail == null) {
    return null;
  }
  if (typeof detail === "string") {
    return detail;
  }
  // FastAPI / Pydantic validation errors: [{ loc, msg, type }, ...]
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (item && typeof item === "object" && "msg" in item) {
          const loc = Array.isArray((item as { loc?: unknown }).loc)
            ? (item as { loc: unknown[] }).loc.filter((p) => p !== "body").join(".")
            : "";
          const msg = String((item as { msg: unknown }).msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return null;
      })
      .filter((part): part is string => Boolean(part));
    if (parts.length > 0) {
      return parts.join("; ");
    }
  }
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return null;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let message = response.statusText || "Request failed";
  try {
    const body = (await response.json()) as { detail?: unknown };
    const formatted = formatErrorDetail(body.detail);
    if (formatted) {
      message = formatted;
    }
  } catch {
    // ignore non-JSON error bodies
  }
  return new ApiError(response.status, message);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options?: { csrf?: boolean },
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (options?.csrf) {
    if (!csrfToken) {
      throw new ApiError(403, "CSRF token missing");
    }
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function fetchSetupStatus(): Promise<SetupStatusResponse> {
  return request<SetupStatusResponse>("/api/setup/status");
}

export async function completeSetup(input: {
  username: string;
  password: string;
}): Promise<UserPublic> {
  return request<UserPublic>("/api/setup", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function login(input: {
  username: string;
  password: string;
}): Promise<MeResponse> {
  const me = await request<MeResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
  setCsrfToken(me.csrf_token);
  return me;
}

export async function logout(): Promise<MessageResponse> {
  const result = await request<MessageResponse>(
    "/api/auth/logout",
    { method: "POST" },
    { csrf: true },
  );
  setCsrfToken(null);
  return result;
}

export async function fetchMe(): Promise<MeResponse> {
  const me = await request<MeResponse>("/api/auth/me");
  setCsrfToken(me.csrf_token);
  return me;
}

export async function changePassword(input: {
  current_password: string;
  new_password: string;
}): Promise<MessageResponse> {
  return request<MessageResponse>(
    "/api/auth/change-password",
    { method: "POST", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function fetchUsers(): Promise<UserListResponse> {
  return request<UserListResponse>("/api/users");
}

export async function createUser(input: {
  username: string;
  password: string;
  role: UserRole;
}): Promise<UserPublic> {
  return request<UserPublic>(
    "/api/users",
    { method: "POST", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function updateUser(
  userId: number,
  input: { role?: UserRole; is_active?: boolean },
): Promise<UserPublic> {
  return request<UserPublic>(
    `/api/users/${userId}`,
    { method: "PATCH", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function resetUserPassword(
  userId: number,
  new_password: string,
): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/users/${userId}/reset-password`,
    { method: "POST", body: JSON.stringify({ new_password }) },
    { csrf: true },
  );
}

export async function deleteUser(userId: number): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/users/${userId}`,
    { method: "DELETE" },
    { csrf: true },
  );
}

export async function fetchServerStatus(): Promise<ServerStatusResponse> {
  return request<ServerStatusResponse>("/api/server/status");
}

export async function serverAction(
  action: "start" | "stop" | "restart",
): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/server/${action}`,
    { method: "POST" },
    { csrf: true },
  );
}

export async function fetchProperties(): Promise<PropertiesResponse> {
  return request<PropertiesResponse>("/api/server/properties");
}

export async function updateProperties(
  updates: Record<string, string>,
): Promise<PropertiesResponse> {
  return request<PropertiesResponse>(
    "/api/server/properties",
    { method: "PUT", body: JSON.stringify({ updates }) },
    { csrf: true },
  );
}

export async function fetchAllowlist(): Promise<AllowlistResponse> {
  return request<AllowlistResponse>("/api/server/allowlist");
}

export async function addAllowlist(
  name: string,
  xuid?: string,
): Promise<AllowlistResponse> {
  return request<AllowlistResponse>(
    "/api/server/allowlist",
    { method: "POST", body: JSON.stringify({ name, xuid }) },
    { csrf: true },
  );
}

export async function removeAllowlist(name: string): Promise<AllowlistResponse> {
  return request<AllowlistResponse>(
    `/api/server/allowlist/${encodeURIComponent(name)}`,
    { method: "DELETE" },
    { csrf: true },
  );
}

export async function fetchPermissions(): Promise<PermissionsResponse> {
  return request<PermissionsResponse>("/api/server/permissions");
}

export async function setPermission(input: {
  xuid: string;
  permission: string;
  name?: string;
}): Promise<PermissionsResponse> {
  return request<PermissionsResponse>(
    "/api/server/permissions",
    { method: "PUT", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function fetchConsoleHistory(): Promise<ConsoleLinesResponse> {
  return request<ConsoleLinesResponse>("/api/console/history");
}

export async function sendConsoleCommand(command: string): Promise<MessageResponse> {
  return request<MessageResponse>(
    "/api/console/command",
    { method: "POST", body: JSON.stringify({ command }) },
    { csrf: true },
  );
}

export async function fetchBackups(worldId?: number): Promise<BackupListResponse> {
  const q = worldId != null ? `?world_id=${worldId}` : "";
  return request<BackupListResponse>(`/api/backups${q}`);
}

export async function createBackup(): Promise<BackupCreateResponse> {
  return request<BackupCreateResponse>(
    "/api/backups",
    { method: "POST" },
    { csrf: true },
  );
}

export async function restoreBackup(backupId: number): Promise<RestoreResponse> {
  return request<RestoreResponse>(
    `/api/backups/${backupId}/restore`,
    { method: "POST" },
    { csrf: true },
  );
}

export async function deleteBackup(backupId: number): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/backups/${backupId}`,
    { method: "DELETE" },
    { csrf: true },
  );
}

export async function fetchBackup(backupId: number): Promise<BackupResponse> {
  return request<BackupResponse>(`/api/backups/${backupId}`);
}

/** Trigger a same-origin authenticated file download to the user's machine. */
export async function downloadAuthenticatedFile(
  path: string,
  fallbackFilename: string,
): Promise<void> {
  const response = await fetch(path, {
    method: "GET",
    credentials: "include",
  });
  if (!response.ok) {
    throw await parseError(response);
  }

  const disposition = response.headers.get("Content-Disposition");
  let filename = fallbackFilename;
  const utfMatch = disposition?.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  const plainMatch = disposition?.match(/filename\s*=\s*"?([^";]+)"?/i);
  if (utfMatch?.[1]) {
    filename = decodeURIComponent(utfMatch[1]);
  } else if (plainMatch?.[1]) {
    filename = plainMatch[1];
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export function backupDownloadPath(backupId: number): string {
  return `/api/backups/${backupId}/download`;
}

export function addonLibraryBackupDownloadPath(backupId: number): string {
  return `/api/addons/library-backups/${backupId}/download`;
}

export async function fetchOperations(limit = 50): Promise<OperationListResponse> {
  return request<OperationListResponse>(`/api/operations?limit=${limit}`);
}

export async function fetchOperation(operationId: number): Promise<OperationResponse> {
  return request<OperationResponse>(`/api/operations/${operationId}`);
}

export async function fetchActiveOperation(): Promise<OperationResponse | null> {
  const response = await fetch("/api/operations/active", { credentials: "include" });
  if (response.status === 204 || response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  const text = await response.text();
  if (!text || text === "null") {
    return null;
  }
  return JSON.parse(text) as OperationResponse;
}

export async function fetchWorlds(): Promise<WorldListResponse> {
  return request<WorldListResponse>("/api/worlds");
}

export async function createWorld(input: {
  display_name: string;
  folder_name?: string;
  description?: string;
  gamemode?: string;
  difficulty?: string;
  seed?: string;
}): Promise<WorldResponse> {
  return request<WorldResponse>(
    "/api/worlds",
    { method: "POST", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function renameWorld(
  worldId: number,
  input: { display_name?: string; folder_name?: string },
): Promise<WorldResponse> {
  return request<WorldResponse>(
    `/api/worlds/${worldId}`,
    { method: "PATCH", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function cloneWorld(
  worldId: number,
  input: { folder_name: string; display_name?: string },
): Promise<WorldResponse> {
  return request<WorldResponse>(
    `/api/worlds/${worldId}/clone`,
    { method: "POST", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function deleteWorld(worldId: number): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/worlds/${worldId}`,
    { method: "DELETE" },
    { csrf: true },
  );
}

export async function importWorld(input: {
  file: File;
  display_name?: string;
  folder_name?: string;
}): Promise<WorldImportResponse> {
  const form = new FormData();
  form.append("file", input.file);
  if (input.display_name) form.append("display_name", input.display_name);
  if (input.folder_name) form.append("folder_name", input.folder_name);

  const headers = new Headers();
  const token = getCsrfToken();
  if (!token) {
    throw new ApiError(403, "CSRF token missing");
  }
  headers.set("X-CSRF-Token", token);

  const response = await fetch("/api/worlds/import", {
    method: "POST",
    headers,
    body: form,
    credentials: "include",
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as WorldImportResponse;
}

export async function fetchSwitchStatus(): Promise<SwitchStatusResponse> {
  return request<SwitchStatusResponse>("/api/worlds/switch-status");
}

export async function switchWorld(
  worldId: number,
  input: { force?: boolean; skip_countdown?: boolean; consent_id?: string } = {},
): Promise<SwitchStartResponse> {
  return request<SwitchStartResponse>(
    `/api/worlds/${worldId}/switch`,
    { method: "POST", body: JSON.stringify(input) },
    { csrf: true },
  );
}

export async function createSwitchRequest(
  worldId: number,
): Promise<SwitchConsentResponse> {
  return request<SwitchConsentResponse>(
    `/api/worlds/${worldId}/switch-request`,
    { method: "POST" },
    { csrf: true },
  );
}

export async function approveSwitchRequest(
  requestId: string,
): Promise<SwitchConsentResponse> {
  return request<SwitchConsentResponse>(
    `/api/worlds/switch-requests/${requestId}/approve`,
    { method: "POST" },
    { csrf: true },
  );
}

export async function fetchAddons(): Promise<AddonListResponse> {
  return request<AddonListResponse>("/api/addons");
}

export async function fetchAddonLibraryBackups(): Promise<AddonLibraryBackupListResponse> {
  return request<AddonLibraryBackupListResponse>("/api/addons/library-backups");
}

export async function createAddonLibraryBackup(): Promise<AddonLibraryBackupCreateResponse> {
  return request<AddonLibraryBackupCreateResponse>(
    "/api/addons/library-backups",
    { method: "POST" },
    { csrf: true },
  );
}

export async function restoreAddonLibraryBackup(
  backupId: number,
): Promise<AddonLibraryRestoreResponse> {
  return request<AddonLibraryRestoreResponse>(
    `/api/addons/library-backups/${backupId}/restore`,
    { method: "POST" },
    { csrf: true },
  );
}

export async function deleteAddonLibraryBackup(
  backupId: number,
): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/addons/library-backups/${backupId}`,
    { method: "DELETE" },
    { csrf: true },
  );
}

export async function uploadAddon(file: File): Promise<AddonUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const headers = new Headers();
  const token = getCsrfToken();
  if (!token) throw new ApiError(403, "CSRF token missing");
  headers.set("X-CSRF-Token", token);
  const response = await fetch("/api/addons/upload", {
    method: "POST",
    headers,
    body: form,
    credentials: "include",
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as AddonUploadResponse;
}

export async function deleteAddon(addonId: number): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/addons/${addonId}`,
    { method: "DELETE" },
    { csrf: true },
  );
}

export async function fetchWorldProfile(
  worldId: number,
): Promise<WorldProfileResponse> {
  return request<WorldProfileResponse>(`/api/addons/worlds/${worldId}`);
}

export async function saveWorldProfile(
  worldId: number,
  entries: WorldAddonEntry[],
): Promise<WorldProfileResponse> {
  return request<WorldProfileResponse>(
    `/api/addons/worlds/${worldId}`,
    {
      method: "PUT",
      body: JSON.stringify({
        entries: entries.map((e) => ({
          addon_id: e.addon_id,
          enabled: e.enabled,
          load_order: e.load_order,
        })),
      }),
    },
    { csrf: true },
  );
}

export async function applyWorldAddons(
  worldId: number,
  testMode = false,
): Promise<AddonApplyResponse> {
  return request<AddonApplyResponse>(
    `/api/addons/worlds/${worldId}/apply`,
    { method: "POST", body: JSON.stringify({ test_mode: testMode }) },
    { csrf: true },
  );
}

export async function keepAddonTest(worldId: number): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/addons/worlds/${worldId}/keep`,
    { method: "POST" },
    { csrf: true },
  );
}

export async function revertAddonTest(worldId: number): Promise<MessageResponse> {
  return request<MessageResponse>(
    `/api/addons/worlds/${worldId}/revert`,
    { method: "POST" },
    { csrf: true },
  );
}

export async function setTexturepackRequired(
  required: boolean,
): Promise<MessageResponse> {
  return request<MessageResponse>(
    "/api/addons/texturepack-required",
    { method: "PUT", body: JSON.stringify({ required }) },
    { csrf: true },
  );
}

export async function fetchMetricsOverview(
  hours = 24,
  playtimeDays = 7,
): Promise<MetricsOverviewResponse> {
  const params = new URLSearchParams({
    hours: String(hours),
    playtime_days: String(playtimeDays),
  });
  return request<MetricsOverviewResponse>(`/api/metrics/overview?${params}`);
}

export async function fetchMetricsDashboard(): Promise<MetricsDashboardResponse> {
  return request<MetricsDashboardResponse>("/api/metrics/dashboard");
}

export async function fetchNetworkStatus(): Promise<NetworkStatusResponse> {
  return request<NetworkStatusResponse>("/api/server/network");
}

export async function detectPublicIp(): Promise<NetworkStatusResponse> {
  return request<NetworkStatusResponse>(
    "/api/server/network/detect",
    { method: "POST" },
    { csrf: true },
  );
}

export async function applyPublicIp(input?: {
  ip_address?: string;
  restart?: boolean;
}): Promise<NetworkStatusResponse> {
  return request<NetworkStatusResponse>(
    "/api/server/network/apply",
    {
      method: "POST",
      body: JSON.stringify({
        ip_address: input?.ip_address ?? null,
        restart: input?.restart ?? true,
      }),
    },
    { csrf: true },
  );
}

export async function fetchVersionInfo(): Promise<VersionInfoResponse> {
  return request<VersionInfoResponse>("/api/server/version");
}

export async function fetchHelpGuides(): Promise<HelpGuideListResponse> {
  return request<HelpGuideListResponse>("/api/help");
}

export async function fetchHelpGuide(slug: string): Promise<HelpGuideResponse> {
  return request<HelpGuideResponse>(`/api/help/${encodeURIComponent(slug)}`);
}
