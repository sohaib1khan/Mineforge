export type UserRole = "admin" | "player";

export type UserPublic = {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type MeResponse = {
  user: UserPublic;
  csrf_token: string;
};

export type SetupStatusResponse = {
  needs_setup: boolean;
  app_name: string;
};

export type MessageResponse = {
  detail: string;
};

export type UserListResponse = {
  users: UserPublic[];
};

export type ContainerResources = {
  cpu_pct: number;
  mem_bytes: number;
  mem_limit_bytes: number;
  mem_pct: number | null;
  net_rx_bytes: number;
  net_tx_bytes: number;
};

export type ServerStatusResponse = {
  container: {
    name: string;
    exists: boolean;
    running: boolean;
    status: string;
    image: string | null;
    started_at: string | null;
    uptime_seconds: number | null;
    finished_at: string | null;
    created_at: string | null;
    exit_code: number | null;
    pid: number | null;
    restart_count: number;
    oom_killed: boolean;
    error: string | null;
    health: string | null;
    restart_policy: string | null;
    platform: string | null;
  };
  resources: ContainerResources | null;
  ports: Array<{ private: string; public: string | null }>;
  mounts: Array<{ destination: string; mode: string; type: string }>;
  safe_env: Record<string, string>;
  server_settings: Record<string, string>;
  warnings: string[];
  level_name: string | null;
  players_online: Array<{
    gamertag: string;
    xuid: string | null;
    joined_at: string | null;
  }>;
  player_count: number;
  properties_present: boolean;
};

export type PropertyCatalogItem = {
  key: string;
  description: string;
  value_type: string;
  allowed_values: string[] | null;
  editable: boolean;
};

export type PropertiesResponse = {
  values: Record<string, string>;
  catalog: PropertyCatalogItem[];
  world_synced?: boolean;
  restarted?: boolean;
  note?: string | null;
};

export type ConsoleLinesResponse = {
  lines: Array<{ ts: string; stream: string; text: string }>;
};

export type AllowlistResponse = {
  entries: Array<Record<string, unknown>>;
};

export type PermissionsResponse = {
  entries: Array<Record<string, unknown>>;
};

export type OperationStatus =
  "queued" | "running" | "succeeded" | "failed" | "rolled_back";

export type OperationResponse = {
  id: number;
  type: string;
  status: OperationStatus;
  params: Record<string, unknown> | null;
  started_by: number | null;
  started_at: string | null;
  finished_at: string | null;
  log: string;
  rollback_performed: boolean;
  created_at: string | null;
};

export type OperationListResponse = {
  operations: OperationResponse[];
  active_id: number | null;
};

export type BackupResponse = {
  id: number;
  world_id: number;
  world_folder: string;
  kind: string;
  path: string;
  size_bytes: number;
  sha256: string;
  verified: boolean;
  created_at: string | null;
  created_by: number | null;
};

export type BackupListResponse = {
  backups: BackupResponse[];
  storage: { backups_bytes?: number; backup_file_count?: number };
};

export type BackupCreateResponse = {
  operation: OperationResponse;
};

export type RestoreResponse = {
  operation: OperationResponse;
};

export type WorldResponse = {
  id: number;
  display_name: string;
  folder_name: string;
  description: string | null;
  gamemode: string | null;
  difficulty: string | null;
  seed: string | null;
  size_bytes: number;
  is_active: boolean;
  created_at: string | null;
  last_played_at: string | null;
  needs_experiments: boolean;
  valid: boolean;
  on_disk: boolean;
  icon_present: boolean;
  warnings: string[];
};

export type WorldListResponse = {
  worlds: WorldResponse[];
};

export type WorldImportResponse = {
  world: WorldResponse;
  warnings: string[];
};

export type SwitchConsentResponse = {
  id: string;
  target_world_id: number;
  target_folder: string;
  requested_by: number;
  required_count: number;
  approval_count: number;
  online_gamertags: string[];
  expires_at: string;
  satisfied: boolean;
};

export type SwitchStatusResponse = {
  players_online: number;
  online_gamertags: string[];
  cooldown_remaining_seconds: number;
  countdown_seconds: number;
  open_consent_requests: SwitchConsentResponse[];
};

export type SwitchStartResponse = {
  operation: OperationResponse;
};

export type AddonResponse = {
  id: number;
  name: string;
  pack_uuid: string;
  version: string;
  kind: string;
  pair_addon_id: number | null;
  pair_name: string | null;
  source_filename: string;
  sha256: string;
  size_bytes: number;
  missing_pair: boolean;
  encrypted: boolean;
  needs_beta_apis: boolean;
  flags: string[];
  uploaded_by: number | null;
  created_at: string | null;
  notes: string | null;
  used_by_world_ids: number[];
};

export type AddonListResponse = {
  addons: AddonResponse[];
};

export type AddonUploadResponse = {
  addons: AddonResponse[];
};

export type WorldAddonEntry = {
  world_addon_id?: number | null;
  addon_id: number;
  enabled: boolean;
  load_order: number;
  addon?: AddonResponse | null;
};

export type WorldProfileResponse = {
  world_id: number;
  entries: WorldAddonEntry[];
  download_size: { enabled_pack_bytes?: number; enabled_pack_count?: number };
};

export type AddonApplyResponse = {
  operation: OperationResponse;
};

export type AddonLibraryBackupResponse = {
  id: number;
  path: string;
  size_bytes: number;
  sha256: string;
  verified: boolean;
  pack_count: number;
  note: string | null;
  created_at: string | null;
  created_by: number | null;
};

export type AddonLibraryBackupListResponse = {
  backups: AddonLibraryBackupResponse[];
};

export type AddonLibraryBackupCreateResponse = {
  operation: OperationResponse;
};

export type AddonLibraryRestoreResponse = {
  operation: OperationResponse;
};

export type MetricSample = {
  id: number;
  ts: string;
  cpu_pct: number;
  mem_bytes: number;
  mem_limit_bytes: number;
  net_rx_bytes: number;
  net_tx_bytes: number;
  players_online: number;
};

export type PlaytimeEntry = {
  gamertag: string;
  seconds: number;
  hours: number;
};

export type JoinsDayEntry = {
  day: string;
  joins: number;
};

export type MetricsDiskSummary = {
  worlds: Array<{
    id: number | null;
    display_name: string;
    folder_name: string;
    size_bytes: number;
    is_active: boolean;
    last_played_at: string | null;
    gamemode: string | null;
    difficulty: string | null;
  }>;
  worlds_bytes: number;
  backups_bytes: number;
  backup_count: number;
};

export type MetricsBackupHistoryEntry = {
  id: number | null;
  world_folder: string;
  kind: string;
  size_bytes: number;
  verified: boolean;
  created_at: string | null;
};

export type WorldInsightPackEntry = {
  name: string;
  kind: string;
  pack_uuid: string;
  folder: string;
  category: string;
  size_bytes: number;
  counts: Record<string, number>;
  weapon_like_items: number;
  structure_files: number;
};

export type WorldInsightResponse = {
  available: boolean;
  reason: string | null;
  world: {
    id?: number | null;
    display_name?: string;
    folder_name?: string;
    size_bytes?: number;
    db_bytes?: number;
    gamemode?: string | null;
    difficulty?: string | null;
    seed?: string | null;
    last_played_at?: string | null;
  } | null;
  level: Record<string, unknown> | null;
  packs: WorldInsightPackEntry[];
  all_pack_names: string[];
  totals: Record<string, number>;
  categories: Record<string, number>;
};

export type LoginActivityResponse = {
  recent: Array<{
    ts: string;
    user_id: number | null;
    username: string;
    ip: string | null;
  }>;
  logins_by_day: Array<{ day: string; logins: number }>;
  users: Array<{
    id: number | null;
    username: string;
    role: string;
    is_active: boolean;
    last_login_at: string | null;
    created_at: string | null;
  }>;
  login_count_window: number;
  users_total: number;
  users_active: number;
  users_never_logged_in: number;
};

export type MetricsOverviewResponse = {
  samples: MetricSample[];
  playtime: PlaytimeEntry[];
  joins: JoinsDayEntry[];
  disk: MetricsDiskSummary;
  backups: MetricsBackupHistoryEntry[];
  sample_interval_seconds: number;
  retention_days: number;
  world_insight?: WorldInsightResponse | null;
  login_activity?: LoginActivityResponse | null;
};

export type MetricsDashboardResponse = {
  latest: MetricSample | null;
  playtime_week: PlaytimeEntry[];
  disk: {
    worlds_bytes?: number;
    backups_bytes?: number;
    backup_count?: number;
  };
  players_online: number;
  world_insight?: WorldInsightResponse | null;
  login_activity?: LoginActivityResponse | null;
};

export type NetworkChecklistItem = {
  id: string;
  title: string;
  detail: string;
};

export type NetworkStatusResponse = {
  server_port: string;
  server_udp_ports: string | null;
  advertised_public_ip: string | null;
  detected_public_ip?: string | null;
  proposed_server_udp_ports?: string | null;
  matches_advertised?: boolean | null;
  udp_range: string;
  transport: string;
  checklist: NetworkChecklistItem[];
  lookup_url: string;
  note: string;
  restarted?: boolean | null;
};

export type VersionInfoResponse = {
  image: string | null;
  version_env: string | null;
  pinned: boolean;
  guidance: string;
};

export type HelpGuideListItem = {
  slug: string;
  title: string;
  summary: string;
  order: number;
};

export type HelpGuideListResponse = {
  guides: HelpGuideListItem[];
};

export type HelpGuideResponse = {
  slug: string;
  title: string;
  summary: string;
  markdown: string;
};

export type StreamStatusResponse = {
  live: boolean;
  enabled: boolean;
  title: string;
  description: string;
  started_at: string | null;
  viewers: number;
  bitrate_kbps: number | null;
  video_codec: string | null;
  resolution: string | null;
  last_ended_at: string | null;
  hls_path: string | null;
};

export type StreamSettingsResponse = {
  title: string;
  description: string;
  enabled: boolean;
  key_configured: boolean;
  key_rotated_at: string | null;
  rtmp_server: string;
  rtmp_host: string;
  rtmp_port: number;
  rtmp_stream_key_hint: string;
  obs_notes: string[];
};

export type StreamKeyRotateResponse = {
  stream_key: string;
  obs_stream_key: string;
  rtmp_server: string;
  rtmp_url_example: string;
  key_rotated_at: string;
  warning: string;
};
