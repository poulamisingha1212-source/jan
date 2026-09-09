import React from 'react';
import logoMark from '@/assets/Gemini_Generated_Image_a9h75ra9h75ra9h7.png';
import {
  UserCheck, AlertTriangle, CheckCircle, Landmark, RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip';

const NAV_TABS = [
  { id: 'overview', label: 'Dashboard' },
  { id: 'queue', label: 'Priority Queue' },
  { id: 'mps', label: 'MPs' },
  { id: 'states', label: 'States' },
  { id: 'compare', label: 'Compare' },
];

export default function Header({
  activeTab,
  setActiveTab,
  currentRole,
  setCurrentRole,
  syncStatus,
  onTriggerSync,
  isSyncing,
  house,
  setHouse
}) {
  return (
    <header className="glass-panel border-b sticky top-0 z-40 px-4 sm:px-6 py-2">
      <div className="max-w-7xl mx-auto flex flex-col gap-1.5">

        {/* Row 1: brand + controls */}
        <div className="flex items-center justify-between gap-3 flex-wrap lg:flex-nowrap">

          {/* Branding */}
          <div className="flex items-center min-w-0 py-0.5">
            <img
              src={logoMark}
              alt="JanNidhi logo"
              className="h-12 w-[170px] object-cover object-center shrink-0 sm:h-14 sm:w-[205px]"
            />
          </div>

        {/* Sync status + house scope + RBAC role switcher */}
        <div className="flex items-center justify-end gap-1.5 flex-wrap max-w-full lg:flex-nowrap">

          <Select value={house || "ALL"} onValueChange={(v) => setHouse(v === "ALL" ? '' : v)}>
            <SelectTrigger size="sm" className="gap-1 border text-[11px] w-[112px] sm:w-[124px]">
              <Landmark className="w-3.5 h-3.5 text-primary shrink-0" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Both Houses</SelectItem>
              <SelectItem value="Lok Sabha">Lok Sabha</SelectItem>
              <SelectItem value="Rajya Sabha">Rajya Sabha</SelectItem>
            </SelectContent>
          </Select>

          <Tooltip>
            <TooltipTrigger asChild>
              <Badge
                variant="outline"
                className={`gap-1 px-2.5 py-1.5 text-[11px] font-medium cursor-default whitespace-nowrap ${
                  syncStatus?.is_data_stale
                    ? 'border-amber-200 bg-amber-50 text-amber-700'
                    : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                }`}
              >
                {syncStatus?.is_data_stale ? (
                  <AlertTriangle className="w-3.5 h-3.5 animate-pulse" />
                ) : (
                  <CheckCircle className="w-3.5 h-3.5" />
                )}
                {syncStatus?.mode === 'prototype' ? 'Snapshot Loaded' : syncStatus?.is_data_stale ? 'Data Stale' : 'Data Fresh'}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              {syncStatus?.source || syncStatus?.staleness_message || 'Data status'}
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                onClick={onTriggerSync}
                disabled={isSyncing || currentRole !== 'MoSPI Reviewer'}
                className="h-8 gap-1.5 px-2.5 text-[11px]"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">Reload snapshot</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {currentRole === 'MoSPI Reviewer'
                ? 'Re-score the active cached MPLADS snapshot'
                : 'Only MoSPI Reviewer can reload the active snapshot'}
            </TooltipContent>
          </Tooltip>

          <Select value={currentRole} onValueChange={setCurrentRole}>
            <SelectTrigger size="sm" className="gap-1 border text-[11px] w-[140px] sm:w-[152px] max-w-full">
              <UserCheck className="w-3.5 h-3.5 text-primary shrink-0" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="MoSPI Reviewer">MoSPI Reviewer (Admin)</SelectItem>
              <SelectItem value="District Authority Auditor">District Auditor</SelectItem>
              <SelectItem value="Read-Only Public Tier">Public Tier (Read-Only)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        </div>

        {/* Row 2: navigation */}
        <nav className="flex flex-wrap items-center justify-center gap-0.5 rounded-xl bg-muted/60 border p-1 max-w-full mx-auto">
          {NAV_TABS.map((tab) => (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setActiveTab(tab.id)}
              className={`h-8 px-3 text-xs font-medium rounded-lg whitespace-nowrap ${
                activeTab === tab.id ? 'shadow-md shadow-primary/30' : 'text-muted-foreground'
              }`}
            >
              {tab.label}
            </Button>
          ))}
        </nav>

      </div>
    </header>
  );
}
