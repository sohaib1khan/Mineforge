/** Thin wrappers around Lucide for consistent stroke/size across the UI. */

import type { LucideIcon, LucideProps } from "lucide-react";
import {
  Activity,
  Archive,
  Box,
  Boxes,
  Car,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Cpu,
  Database,
  Globe2,
  HardDrive,
  Home,
  KeyRound,
  Layers,
  LayoutDashboard,
  LogIn,
  LogOut,
  MemoryStick,
  Menu,
  Moon,
  MoreHorizontal,
  Package,
  Pause,
  Play,
  Radio,
  Server,
  Shield,
  Sparkles,
  Sun,
  Swords,
  Terminal,
  Timer,
  Users,
  X,
} from "lucide-react";

const DEFAULT_SIZE = 18;

export function Icon({
  icon: Lucide,
  className,
  size = DEFAULT_SIZE,
  strokeWidth = 1.75,
  ...rest
}: LucideProps & { icon: LucideIcon }) {
  return (
    <Lucide
      aria-hidden
      className={className}
      size={size}
      strokeWidth={strokeWidth}
      {...rest}
    />
  );
}

export const Icons = {
  Home,
  Stream: Radio,
  Worlds: Globe2,
  Addons: Package,
  Backups: Archive,
  Metrics: Activity,
  Help: CircleHelp,
  Server,
  Console: Terminal,
  Users,
  Account: KeyRound,
  More: MoreHorizontal,
  Menu,
  Close: X,
  Logout: LogOut,
  Login: LogIn,
  Sun,
  Moon,
  Status: Play,
  Offline: Pause,
  Players: Users,
  Cpu,
  Memory: MemoryStick,
  Disk: HardDrive,
  Packs: Boxes,
  Items: Box,
  Entities: Sparkles,
  Structures: Layers,
  Weapons: Swords,
  Vehicles: Car,
  Seed: Database,
  Shield,
  Timer,
  Check: CheckCircle2,
  Chevron: ChevronRight,
  Layout: LayoutDashboard,
} as const;
