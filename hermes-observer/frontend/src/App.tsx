import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Bot, Eye, Globe2, LayoutDashboard, MessageSquare, Radio, Send, Settings } from 'lucide-react';
import { fetchProfiles } from './api/client';
import PresenceOverview from './pages/PresenceOverview';
import Profiles from './pages/Profiles';
import Preview from './pages/Preview';
import Traces from './pages/Traces';
import WorldSignals from './pages/WorldSignals';
import PresenceDecisions from './pages/PresenceDecisions';
import Delivery from './pages/Delivery';
import ProxyMonitor from './pages/ProxyMonitor';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [profileId, setProfileId] = useState('');
  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles, refetchInterval: 15000 });
  const profileList = profiles?.profiles || [];
  const selectedProfileId = profileId || profileList[0]?.profile_id || '';

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'profiles', label: 'Profiles', icon: Settings },
    { id: 'preview', label: 'Preview', icon: Eye },
    { id: 'traces', label: 'Traces', icon: Activity },
    { id: 'world', label: 'World Signals', icon: Globe2 },
    { id: 'decisions', label: 'Decisions', icon: MessageSquare },
    { id: 'delivery', label: 'Delivery', icon: Send },
    { id: 'proxy', label: 'Proxy', icon: Radio },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--color-dark-bg)]">
      <aside className="w-64 glass-panel border-r border-[rgba(255,255,255,0.05)] flex flex-col z-10">
        <div className="p-6 flex items-center gap-3 border-b border-[rgba(255,255,255,0.05)]">
          <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight text-white">Presence Kernel</h1>
            <p className="text-xs text-[var(--color-text-secondary)] font-medium tracking-wider uppercase">Observer Console</p>
          </div>
        </div>
        <div className="px-4 py-3 border-b border-[rgba(255,255,255,0.05)]">
          <select
            className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
            value={selectedProfileId}
            onChange={(event) => setProfileId(event.target.value)}
          >
            {profileList.map((profile: any) => (
              <option key={profile.profile_id} value={profile.profile_id}>{profile.display_name || profile.profile_id}</option>
            ))}
          </select>
        </div>
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                  isActive ? 'bg-white/10 text-white font-medium' : 'text-[var(--color-text-secondary)] hover:bg-white/5 hover:text-white'
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-blue-400' : ''}`} />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto relative">
        <div className="p-8 relative z-0 min-h-full">
          {activeTab === 'overview' && <PresenceOverview profileId={selectedProfileId} />}
          {activeTab === 'profiles' && <Profiles profileId={selectedProfileId} onProfileChange={setProfileId} />}
          {activeTab === 'preview' && <Preview profileId={selectedProfileId} />}
          {activeTab === 'traces' && <Traces profileId={selectedProfileId} />}
          {activeTab === 'world' && <WorldSignals profileId={selectedProfileId} />}
          {activeTab === 'decisions' && <PresenceDecisions profileId={selectedProfileId} />}
          {activeTab === 'delivery' && <Delivery profileId={selectedProfileId} />}
          {activeTab === 'proxy' && <ProxyMonitor />}
        </div>
      </main>
    </div>
  );
}

export default App;
