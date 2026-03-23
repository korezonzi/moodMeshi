"""SQLAlchemy ORM models for MoodMeshi."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    allergy_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    preference_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    slack_channel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    mood_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    target_categories: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    closing_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    meals: Mapped[list["ProposedMealRecord"]] = relationship(
        "ProposedMealRecord", back_populates="session", cascade="all, delete-orphan"
    )


class ProposedMealRecord(Base):
    __tablename__ = "proposed_meals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_title: Mapped[str] = mapped_column(Text, nullable=False)
    recipe_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    food_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_indication: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_cost: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_recommended: Mapped[str | None] = mapped_column(Text, nullable=True)
    nutrition_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    seasonal_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    arrange_tip: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favorited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    session: Mapped["SearchSession"] = relationship("SearchSession", back_populates="meals")
