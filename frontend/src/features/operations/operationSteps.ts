/** Derive human-readable progress steps from streamed operation logs. */

export type StepState = "pending" | "active" | "done" | "failed";

export type OperationStep = {
  id: string;
  label: string;
  state: StepState;
  detail?: string;
};

type StepDef = {
  id: string;
  label: string;
  match: (line: string) => boolean;
  detail?: (line: string) => string | undefined;
};

const SWITCH_STEPS: StepDef[] = [
  {
    id: "warn",
    label: "Warn players",
    match: (l) =>
      /warning players|countdown:|countdown skipped/i.test(l) &&
      !/failed|rolling back/i.test(l),
    detail: (l) => {
      const m = l.match(/Countdown:\s*(\d+)s/i);
      return m ? `${m[1]}s remaining` : undefined;
    },
  },
  {
    id: "backup",
    label: "Pre-switch backup",
    match: (l) => /pre-switch backup/i.test(l),
  },
  {
    id: "stop",
    label: "Stop Bedrock",
    match: (l) => /stopping bedrock/i.test(l),
  },
  {
    id: "configure",
    label: "Set world & packs",
    match: (l) => /setting level-name|merged pack|pack merge skipped/i.test(l),
  },
  {
    id: "start",
    label: "Start Bedrock",
    match: (l) => /starting bedrock/i.test(l),
  },
  {
    id: "health",
    label: "Wait for health",
    match: (l) => /waiting for server health|healthy/i.test(l),
  },
  {
    id: "done",
    label: "World ready",
    match: (l) => /^Switched to /i.test(l.trim()),
  },
];

const BACKUP_STEPS: StepDef[] = [
  {
    id: "hold",
    label: "Hold world saves",
    match: (l) => /save hold|save query|save resume/i.test(l),
  },
  {
    id: "archive",
    label: "Create archive",
    match: (l) => /archiv|compress|writing backup|backup file/i.test(l),
  },
  {
    id: "done",
    label: "Backup complete",
    match: (l) => /backup (complete|succeeded|finished)|created backup/i.test(l),
  },
];

const GENERIC_STEPS: StepDef[] = [
  {
    id: "run",
    label: "Running",
    match: () => true,
  },
];

function defsForType(type: string | undefined): StepDef[] {
  switch (type) {
    case "switch":
      return SWITCH_STEPS;
    case "backup":
    case "addon_backup":
      return BACKUP_STEPS;
    default:
      return GENERIC_STEPS;
  }
}

function linesOf(log: string): string[] {
  return log
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

/**
 * Map operation type + log text into ordered step states for the progress UI.
 * Latest matching step becomes active; earlier matches are done.
 */
export function deriveOperationSteps(
  type: string | undefined,
  log: string,
  status: string,
): OperationStep[] {
  const defs = defsForType(type);
  const lines = linesOf(log);
  const failed =
    status === "failed" ||
    status === "rolled_back" ||
    lines.some((l) => /switch failed|rollback failed/i.test(l));
  const succeeded = status === "succeeded";

  let highest = -1;
  const details: Record<string, string | undefined> = {};

  for (const line of lines) {
    defs.forEach((def, index) => {
      if (def.match(line)) {
        highest = Math.max(highest, index);
        const d = def.detail?.(line);
        if (d) details[def.id] = d;
      }
    });
  }

  if (succeeded) {
    highest = defs.length - 1;
  }

  return defs.map((def, index) => {
    let state: StepState = "pending";
    if (failed && index === Math.max(highest, 0) && highest >= 0) {
      state = index <= highest ? (index < highest ? "done" : "failed") : "pending";
      if (index === highest) state = "failed";
      else if (index < highest) state = "done";
    } else if (index < highest) {
      state = "done";
    } else if (index === highest) {
      state = succeeded || def.id === "done" ? "done" : "active";
    } else if (highest < 0 && status === "running" && index === 0) {
      state = "active";
    } else if (
      highest < 0 &&
      (status === "queued" || status === "running") &&
      index === 0
    ) {
      state = status === "queued" ? "pending" : "active";
    }

    if (succeeded && index <= highest) state = "done";

    return {
      id: def.id,
      label: def.label,
      state,
      detail: details[def.id],
    };
  });
}

export function operationTitle(type: string | undefined): string {
  switch (type) {
    case "switch":
      return "Switching world";
    case "backup":
      return "Creating backup";
    case "restore":
      return "Restoring backup";
    case "addon_apply":
      return "Applying add-ons";
    case "addon_test":
      return "Testing add-ons";
    case "addon_backup":
      return "Backing up add-ons";
    case "addon_restore":
      return "Restoring add-ons";
    default:
      return "Operation in progress";
  }
}
