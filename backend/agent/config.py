"""
Agent configuration and settings management.
"""
import os
import json
from typing import Optional
from dataclasses import dataclass, field, asdict

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '.agent_config.json')

@dataclass
class AgentConfig:
    api_key: str = ''
    model: str = 'gpt-4o'
    temperature: float = 0.7
    max_iterations: int = 15
    auto_approve_reads: bool = True
    auto_approve_writes: bool = False
    auto_approve_deletes: bool = False
    auto_approve_terminal: bool = False
    max_tokens: int = 4096
    workspace_root: str = ''

    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> 'AgentConfig':
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        # Check environment variable for API key
        cfg = cls()
        cfg.api_key = os.environ.get('OPENAI_API_KEY', '')
        return cfg

config = AgentConfig.load()
