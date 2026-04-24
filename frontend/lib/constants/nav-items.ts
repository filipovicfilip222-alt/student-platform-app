/**
 * nav-items.ts — Sidebar navigation configuration per role.
 *
 * Read by `components/shared/sidebar.tsx`. Each entry defines the href, label
 * and a lucide icon. RBAC redirection is enforced by middleware / layouts —
 * this map only drives what the current user *sees* in the sidebar.
 */

import {
  AlertTriangle,
  Calendar,
  FileText,
  History,
  Home,
  LayoutDashboard,
  Megaphone,
  Search,
  Settings,
  Users,
  type LucideIcon,
} from "lucide-react"

import type { Role } from "@/types/common"
import { ROUTES } from "./routes"

export interface NavItem {
  href: string
  label: string
  icon: LucideIcon
}

export const NAV_ITEMS: Record<Role, NavItem[]> = {
  STUDENT: [
    { href: ROUTES.dashboard, label: "Početna", icon: Home },
    { href: ROUTES.search, label: "Pretraga profesora", icon: Search },
    { href: ROUTES.myAppointments, label: "Moji termini", icon: Calendar },
    { href: ROUTES.documentRequests, label: "Zahtevi za dokumente", icon: FileText },
  ],
  PROFESOR: [
    { href: ROUTES.professorDashboard, label: "Dashboard", icon: LayoutDashboard },
    { href: ROUTES.professorSettings, label: "Podešavanja", icon: Settings },
  ],
  ASISTENT: [
    { href: ROUTES.professorDashboard, label: "Dashboard", icon: LayoutDashboard },
    { href: ROUTES.professorSettings, label: "Podešavanja", icon: Settings },
  ],
  ADMIN: [
    { href: ROUTES.admin, label: "Pregled", icon: LayoutDashboard },
    { href: ROUTES.adminUsers, label: "Korisnici", icon: Users },
    { href: ROUTES.adminDocumentRequests, label: "Zahtevi", icon: FileText },
    { href: ROUTES.adminStrikes, label: "Strike-ovi", icon: AlertTriangle },
    { href: ROUTES.adminBroadcast, label: "Broadcast", icon: Megaphone },
    { href: ROUTES.adminAuditLog, label: "Audit log", icon: History },
  ],
}
