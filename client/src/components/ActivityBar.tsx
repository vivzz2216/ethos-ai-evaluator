import React from 'react';
import { FileText, Terminal, Settings, Search, GitBranch } from 'lucide-react';

interface ActivityBarProps {
  activeView: string;
  onViewChange: (view: string) => void;
}

const ActivityBar: React.FC<ActivityBarProps> = ({ activeView, onViewChange }) => {
  const activities = [
    { id: 'explorer', icon: FileText, label: 'Explorer' },
    { id: 'search', icon: Search, label: 'Search' },
    { id: 'source-control', icon: GitBranch, label: 'Source Control' },
    { id: 'terminal', icon: Terminal, label: 'Terminal' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="w-12 bg-gray-900 border-r border-gray-700 flex flex-col items-center py-2">
      {activities.map((activity) => {
        const Icon = activity.icon;
        const isActive = activeView === activity.id;
        
        return (
          <button
            key={activity.id}
            onClick={() => onViewChange(activity.id)}
            className={`w-10 h-10 flex items-center justify-center mb-1 rounded-md transition-all duration-200 group relative ${
              isActive 
                ? 'bg-blue-600 text-white' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
            title={activity.label}
          >
            <Icon className="w-5 h-5" />
            {isActive && (
              <div className="absolute left-0 top-2 w-0.5 h-6 bg-white rounded-r-sm"></div>
            )}
          </button>
        );
      })}
    </div>
  );
};

export default ActivityBar;
