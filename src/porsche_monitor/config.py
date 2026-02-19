from __future__ import annotations

import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List


class SourceConfig(BaseModel):
    enabled: bool = False
    urls: List[str] = Field(default_factory=list)


class TelegramConfig(BaseModel):
    enabled: bool = False
    chat_id: str = ""


class NotificationsConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class AppConfig(BaseModel):
    timezone: str = "Europe/Berlin"
    report_path: str = "reports/latest.md"
    database_path: str = "data/monitor.db"
    user_agent: str = "porsche-monitor/0.1 (+contact: you@example.com)"
    request_delay_seconds: float = 4.0


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)

    @classmethod
    def from_yaml(cls, path: str | Path = "config.yaml") -> Config:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        sources = {}
        for name, src_raw in raw.get("sources", {}).items():
            sources[name] = SourceConfig(**(src_raw or {}))
        return cls(
            app=AppConfig(**raw.get("app", {})),
            sources=sources,
            notifications=NotificationsConfig(**raw.get("notifications", {})),
        )
