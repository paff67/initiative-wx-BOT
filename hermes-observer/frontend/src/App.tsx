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

const navItems = [
  { id: 'overview', label: '总览', hint: '运行状态', icon: LayoutDashboard },
  { id: 'profiles', label: '配置', hint: '编辑与回滚', icon: Settings },
  { id: 'preview', label: '预览', hint: 'dry-run', icon: Eye },
  { id: 'traces', label: '链路', hint: '全流程', icon: Activity },
  { id: 'world', label: '世界信号', hint: 'MCP 与来源', icon: Globe2 },
  { id: 'decisions', label: '决策', hint: '动作裁决', icon: MessageSquare },
  { id: 'delivery', label: '投递', hint: '微信输出', icon: Send },
  { id: 'proxy', label: '代理', hint: '网关请求', icon: Radio },
];

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [profileId, setProfileId] = useState('');
  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: fetchProfiles, refetchInterval: 15000 });
  const profileList = profiles?.profiles || [];
  const selectedProfileId = profileId || profileList[0]?.profile_id || '';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">
            <Bot size={21} />
          </div>
          <div>
            <h1 className="brand-title">Presence Observer</h1>
            <p className="brand-subtitle">主动心跳控制台</p>
          </div>
        </div>

        <select
          className="profile-select"
          value={selectedProfileId}
          aria-label="选择 profile"
          onChange={(event) => setProfileId(event.target.value)}
        >
          {profileList.length === 0 && <option value="">暂无 profile</option>}
          {profileList.map((profile: any) => (
            <option key={profile.profile_id} value={profile.profile_id}>
              {profile.display_name || profile.profile_id}
            </option>
          ))}
        </select>

        <nav className="nav-list" aria-label="Observer 导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveTab(item.id)}
                className={`nav-button ${isActive ? 'is-active' : ''}`}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon size={18} />
                <span>
                  <span className="block font-semibold">{item.label}</span>
                  <span className="block text-xs opacity-75">{item.hint}</span>
                </span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="main-pane">
        <div className="content-frame">
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
