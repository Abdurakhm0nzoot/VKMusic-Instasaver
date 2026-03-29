"""SQLAlchemy ORM models."""

from datetime import datetime, date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Telegram user record."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="ru", server_default="ru")
    audio_quality: Mapped[int] = mapped_column(Integer, default=320, server_default="320")
    daily_downloads: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_download_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )

    # Relationships
    playlist_items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class FileCache(Base):
    """Smart Cache — maps content hash → Telegram file_id."""

    __tablename__ = "file_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "audio" | "video"
    telegram_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    artist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seconds
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )


class PlaylistItem(Base):
    """User's personal playlist entry."""

    __tablename__ = "playlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    track_title: Mapped[str] = mapped_column(String(500), nullable=False)
    track_artist: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown")
    track_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_cache_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("file_cache.id"), nullable=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="playlist_items")
    cached_file: Mapped["FileCache | None"] = relationship()
