import React from 'react';
import { X, Circle } from 'lucide-react';

interface Tab {
  id: string;
  name: string;
  path: string;
  isDirty?: boolean;
}

interface TabBarProps {
  tabs: Tab[];
  activeTabId?: string;
  onTabSelect: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
}

const TabBar: React.FC<TabBarProps> = ({ tabs, activeTabId, onTabSelect, onTabClose }) => {
  if (tabs.length === 0) return null;

  return (
    <div className="bg-gray-800 border-b border-gray-700 flex overflow-x-auto">
      {tabs.map((tab) => {
        const isActive = activeTabId === tab.id;
        
        return (
          <div
            key={tab.id}
            className={`flex items-center px-3 py-2 text-sm cursor-pointer border-r border-gray-700 min-w-0 group ${
              isActive 
                ? 'bg-gray-900 text-white' 
                : 'bg-gray-800 text-gray-300 hover:bg-gray-750 hover:text-white'
            }`}
            onClick={() => onTabSelect(tab.id)}
          >
            <div className="flex items-center space-x-2 min-w-0 flex-1">
              {tab.isDirty && (
                <Circle className="w-3 h-3 text-orange-400 fill-current flex-shrink-0" />
              )}
              <span className="truncate max-w-32">{tab.name}</span>
            </div>
            
            <button
              onClick={(e) => {
                e.stopPropagation();
                onTabClose(tab.id);
              }}
              className="ml-2 opacity-0 group-hover:opacity-100 hover:bg-gray-600 rounded p-0.5 transition-opacity"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default TabBar;
