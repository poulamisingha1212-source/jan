import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import Header from './components/Header';
import PriorityQueue from './components/PriorityQueue';
import CasePacketModal from './components/CasePacketModal';
import PortfolioOverview from './components/PortfolioOverview';
import MPDirectory from './components/MPDirectory';
import StatesView from './components/StatesView';
import CompareView from './components/CompareView';
import MPProfileModal from './components/MPProfileModal';
import { Toaster } from '@/components/ui/sonner';
import { DotPattern } from '@/components/magicui/dot-pattern';
import { apiUrl } from '@/lib/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('queue'); // 'queue' is the mandatory default view!
  const [currentRole, setCurrentRole] = useState('MoSPI Reviewer');

  // Works state (Priority Queue)
  const [works, setWorks] = useState([]);
  const [totalWorks, setTotalWorks] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoadingWorks, setIsLoadingWorks] = useState(true);
  const [worksError, setWorksError] = useState(null);
  const [appError, setAppError] = useState(null);

  // Filters — mp_name lets the MP Directory deep-link into the audit queue.
  // Global house scope: '' = Both Houses; applied to every data view.
  const [house, setHouse] = useState('');
  const [filters, setFilters] = useState({
    state: '',
    mp_name: '',
    risk_tier: '',
    work_category: '',
    work_status: '',
    ida: '',
    search: '',
  });
  const [filterOptions, setFilterOptions] = useState({
    states: [],
    categories: [],
    statuses: [],
    mps: [],
    risk_tiers: ["High Risk - Review", "Medium Risk - Monitor", "Low Risk"]
  });

  // Selected work for Case Packet modal
  const [selectedWorkId, setSelectedWorkId] = useState(null);
  const [casePacket, setCasePacket] = useState(null);
  const [isLoadingPacket, setIsLoadingPacket] = useState(false);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // MP profile modal state (stacks beneath the case packet modal)
  const [selectedMP, setSelectedMP] = useState(null);

  // Portfolio Overview state
  const [stats, setStats] = useState(null);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncLogs, setSyncLogs] = useState([]);
  const [isSyncing, setIsSyncing] = useState(false);

  // Fetch filter options (scoped to the selected house)
  useEffect(() => {
    const qs = house ? `?house=${encodeURIComponent(house)}` : '';
    fetch(apiUrl(`/api/filter-options${qs}`))
      .then((res) => {
        if (!res.ok) throw new Error(`Filter options failed (${res.status})`);
        return res.json();
      })
      .then((data) => setFilterOptions(data))
      .catch((err) => {
        console.error('Failed to load filter options:', err);
        setAppError('Some filter options could not be loaded.');
      });
  }, [house]);

  // Fetch works when page, pageSize, or filters change
  useEffect(() => {
    setIsLoadingWorks(true);
    setWorksError(null);
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      sort_by: 'priority_rank',
      order: 'asc',
    });

    if (house) params.append('house', house);
    if (filters.state) params.append('state', filters.state);
    if (filters.mp_name) params.append('mp_name', filters.mp_name);
    if (filters.risk_tier) params.append('risk_tier', filters.risk_tier);
    if (filters.work_category) params.append('work_category', filters.work_category);
    if (filters.work_status) params.append('work_status', filters.work_status);
    if (filters.ida) params.append('ida', filters.ida);
    if (filters.work_status) params.append('work_status', filters.work_status);
    if (filters.ida) params.append('ida', filters.ida);
    if (filters.search) params.append('search', filters.search);

    fetch(apiUrl(`/api/works?${params.toString()}`), {
      headers: { 'X-User-Role': currentRole }
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Works request failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        setWorks(data.items || []);
        setTotalWorks(data.total || 0);
        setTotalPages(data.total_pages || 1);
        setIsLoadingWorks(false);
      })
      .catch((err) => {
        console.error('Error fetching works:', err);
        setWorks([]);
        setTotalWorks(0);
        setTotalPages(1);
        setWorksError('The audit queue could not be loaded. Check that the backend is running.');
        setIsLoadingWorks(false);
      });
  }, [page, pageSize, filters, house, currentRole]);

  // Fetch stats and sync status (scoped by house)
  const fetchStats = () => {
    const hqs = house ? `?house=${encodeURIComponent(house)}` : '';
    fetch(apiUrl(`/api/stats/overview${hqs}`))
      .then((res) => {
        if (!res.ok) throw new Error(`Overview request failed (${res.status})`);
        return res.json();
      })
      .then((data) => setStats(data))
      .catch((err) => {
        console.error('Error fetching stats:', err);
        setStats(null);
        setAppError('The dashboard summary could not be loaded.');
      });

    fetch(apiUrl('/api/sync/status'))
      .then((res) => res.json())
      .then((data) => setSyncStatus(data))
      .catch((err) => console.error('Error fetching sync status:', err));

    fetch(apiUrl('/api/sync/logs'))
      .then((res) => res.json())
      .then((data) => setSyncLogs(data))
      .catch((err) => console.error('Error fetching sync logs:', err));
  };

  useEffect(() => {
    fetchStats();
  }, [house]);

  // Handle work selection for Case Packet modal
  const handleSelectWork = (workId) => {
    setSelectedWorkId(workId);
    setIsLoadingPacket(true);
    fetch(apiUrl(`/api/works/${encodeURIComponent(workId)}`), {
      headers: { 'X-User-Role': currentRole }
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Case packet failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        setCasePacket(data);
        setIsLoadingPacket(false);
      })
      .catch((err) => {
        console.error('Error fetching case packet:', err);
        toast.error('The case packet could not be loaded.');
        setSelectedWorkId(null);
        setCasePacket(null);
        setIsLoadingPacket(false);
      });
  };

  // Submit human review outcome — resolves true when the determination is recorded.
  const handleSubmitReview = async (workId, outcome, notes) => {
    setIsSubmittingReview(true);
    try {
      const res = await fetch(apiUrl(`/api/works/${encodeURIComponent(workId)}/review`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentRole
        },
        body: JSON.stringify({
          outcome,
          notes,
          reviewer_name: currentRole === 'MoSPI Reviewer' ? 'MoSPI Senior Auditor' : 'District Review Officer',
          reviewer_role: currentRole
        })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        toast.error(errorData.detail || 'Review submission failed');
        setIsSubmittingReview(false);
        return false;
      }

      // Re-fetch updated case packet & list
      const updatedRes = await fetch(apiUrl(`/api/works/${encodeURIComponent(workId)}`), {
        headers: { 'X-User-Role': currentRole }
      });
      const updatedPacket = await updatedRes.json();
      setCasePacket(updatedPacket);

      // Update in local works list
      setWorks((prev) =>
        prev.map((w) => (w.work_id === workId ? { ...w, human_review_outcome: outcome } : w))
      );

      setIsSubmittingReview(false);
      return true;
    } catch (err) {
      console.error('Review submit failed:', err);
      toast.error('Review submission failed — is the backend reachable?');
      setIsSubmittingReview(false);
      return false;
    }
  };

  // Re-score the bundled sample dataset in prototype mode.
  const handleTriggerSync = async () => {
    setIsSyncing(true);
    const toastId = toast.loading('Reloading the MPLADS sample dataset…');
    try {
      const res = await fetch(apiUrl('/api/sync/run'), {
        method: 'POST',
        headers: { 'X-User-Role': currentRole }
      });
      const result = await res.json();
      if (!res.ok) {
        toast.error(result.detail || 'Sync failed', { id: toastId });
      } else if (result.status === 'success') {
        toast.success('Prototype dataset reloaded', {
          id: toastId,
          description: `${(result.processed || 0).toLocaleString('en-IN')} MPLADS works rescored by five agents`,
        });
      } else {
        toast.error(result.error || 'Sample reload failed — existing data preserved.', { id: toastId });
      }
      fetchStats();
      setIsSyncing(false);
      return result;
    } catch (err) {
      console.error('Sync failed:', err);
      toast.error('Sync failed — is the backend reachable?', { id: toastId });
      setIsSyncing(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleFilterByEntity = (filterKey, filterVal) => {
    handleFilterChange(filterKey, filterVal);
    setActiveTab('queue');
  };

  // MP Directory interactions
  const handleOpenMP = useCallback((mpName) => setSelectedMP(mpName), []);
  const handleCloseMP = useCallback(() => setSelectedMP(null), []);
  const handleViewMPWorksInQueue = useCallback((mpName) => {
    setSelectedMP(null);
    handleFilterByEntity('mp_name', mpName);
  }, []);

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">

      {/* Toast notifications */}
      <Toaster richColors position="top-right" />

      {/* Subtle dotted texture behind the whole app */}
      <DotPattern className="fixed inset-0 opacity-30 [mask-image:radial-gradient(ellipse_at_top,white_15%,transparent_65%)]" />

      {/* Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        currentRole={currentRole}
        setCurrentRole={setCurrentRole}
        syncStatus={syncStatus}
        onTriggerSync={handleTriggerSync}
        isSyncing={isSyncing}
        house={house}
        setHouse={setHouse}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {(appError || worksError) && (
          <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
            {appError || worksError}
          </div>
        )}
        {activeTab === 'queue' && (
          <PriorityQueue
            works={works}
            totalWorks={totalWorks}
            page={page}
            pageSize={pageSize}
            totalPages={totalPages}
            onPageChange={setPage}
            filters={filters}
            onFilterChange={handleFilterChange}
            filterOptions={filterOptions}
            onSelectWork={handleSelectWork}
            isLoading={isLoadingWorks}
            activeFilterCount={activeFilterCount}
            house={house}
            syncStatus={syncStatus}
          />
        )}

        {activeTab === 'mps' && (
          <MPDirectory
            filterOptions={filterOptions}
            onOpenMP={handleOpenMP}
            house={house}
          />
        )}

        {activeTab === 'states' && (
          <StatesView
            house={house}
            onOpenMP={handleOpenMP}
          />
        )}

        {activeTab === 'compare' && (
          <CompareView
            house={house}
            onOpenMP={handleOpenMP}
          />
        )}

        {activeTab === 'overview' && (
          <PortfolioOverview
            stats={stats}
            house={house}
            syncStatus={syncStatus}
            error={appError}
            onTriggerSync={handleTriggerSync}
            isSyncing={isSyncing}
            currentRole={currentRole}
            onFilterByEntity={handleFilterByEntity}
          />
        )}


      </main>

      {/* MP Transparency Profile (opens beneath the case packet) */}
      {selectedMP && (
        <MPProfileModal
          mpName={selectedMP}
            house={house}
          onClose={handleCloseMP}
          onOpenWork={handleSelectWork}
          onViewWorksInQueue={handleViewMPWorksInQueue}
        />
      )}

      {/* Case Packet Modal — renders after the MP modal so it stacks on top */}
      {selectedWorkId && (
        <CasePacketModal
          workId={selectedWorkId}
          packet={casePacket}
          isLoading={isLoadingPacket}
          onClose={() => {
            setSelectedWorkId(null);
            setCasePacket(null);
          }}
          currentRole={currentRole}
          onSubmitReview={handleSubmitReview}
          isSubmittingReview={isSubmittingReview}
        />
      )}

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-5 text-center text-xs text-slate-500">
        <p>Ministry of Statistics and Programme Implementation (MoSPI) • SIH26102 • JanNidhi</p>
        <p className="text-[11px] text-slate-600 mt-1">
          Decision Support System — Risk Scores are audit prioritization indicators, not definitive fraud verdicts.
        </p>
      </footer>

    </div>
  );
}
