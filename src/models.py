"""SQLAlchemy schema for the event study (CLAUDE.md "Data model").

Conventions
-----------
- Yields are stored in PERCENT (FRED H.15 convention); curve-shape *deltas* in
  event_impacts are stored in BASIS POINTS.
- ``release_datetime`` is ET-naive (all release times are defined in ET).
- ``releases.source`` records provenance as "<actual source>+<consensus source>",
  e.g. "fred_first+naive_prev" or "bloomberg_csv", so naive-proxy rows and real
  consensus rows can coexist and be compared.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    freq: Mapped[str] = mapped_column(String(16))  # weekly | monthly | quarterly | 8x/yr
    fred_series: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # +1 if a positive surprise generally pushes yields up, -1 if down (CLAUDE.md).
    yield_sign: Mapped[int] = mapped_column(Integer)
    release_time: Mapped[time] = mapped_column(Time)  # ET
    transform: Mapped[str] = mapped_column(String(16))  # none | diff | pct_change
    units: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    releases: Mapped[list["Release"]] = relationship(back_populates="indicator")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Indicator {self.key}>"


class Release(Base):
    __tablename__ = "releases"
    # One row per (indicator, reference period, provenance). The same period may
    # legitimately appear under several sources (first-print vs latest vintage,
    # naive vs Bloomberg consensus); analysis filters on is_first_print/source.
    __table_args__ = (
        UniqueConstraint("indicator_id", "ref_period", "source", name="uq_release"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[int] = mapped_column(
        ForeignKey("indicators.id"), index=True
    )
    ref_period: Mapped[date] = mapped_column(Date)  # period the data describes
    release_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)  # ET-naive
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    consensus: Mapped[float | None] = mapped_column(Float, nullable=True)
    consensus_stdev: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_estimates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_first_print: Mapped[bool] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(48))

    indicator: Mapped[Indicator] = relationship(back_populates="releases")
    impacts: Mapped[list["EventImpact"]] = relationship(back_populates="release")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Release {self.indicator_id} {self.ref_period} {self.source}>"


class CurvePoint(Base):
    __tablename__ = "curve"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    tenor: Mapped[str] = mapped_column(String(8), primary_key=True)  # "2Y", "10Y", ...
    yield_pct: Mapped[float] = mapped_column("yield", Float)  # percent (H.15)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Curve {self.date} {self.tenor} {self.yield_pct}>"


class EventImpact(Base):
    __tablename__ = "event_impacts"
    # window_label names the human-chosen event window (e.g. "tm1_close_to_t_close")
    # so competing window definitions can coexist while the policy is evaluated.
    __table_args__ = (
        UniqueConstraint("release_id", "window_label", name="uq_impact_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    window_label: Mapped[str] = mapped_column(String(32))

    # Pre/post window yields, percent.
    pre_2y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_10y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_30y: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_2y: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_10y: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_30y: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Curve-shape deltas over the window, BASIS POINTS.
    delta_level_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_2s10s_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_5s30s_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_curvature_bps: Mapped[float | None] = mapped_column(Float, nullable=True)

    release: Mapped[Release] = relationship(back_populates="impacts")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EventImpact release={self.release_id} {self.window_label}>"
