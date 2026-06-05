from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text, Index, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    manufacturer = Column(String)
    type = Column(String)

    games = relationship("Game", back_populates="platform")

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Which collection (shared workspace) this item belongs to. Backfilled to the
    # default collection #1 by migration k7l8m9n0o1p2; enforced per-request in routes.
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    title = Column(String, nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"))
    barcode = Column(String)
    igdb_id = Column(Integer)
    comicvine_id = Column(String)
    hobbydb_id = Column(String)
    mfc_id = Column(String)
    release_date = Column(String)
    publisher = Column(String)
    developer = Column(String)
    genre = Column(String)
    description = Column(Text)
    cover_url = Column(String)
    region = Column(String)
    # Catalog-sourced disc/cart identity (Redump/No-Intro/GameDB lookup)
    serial = Column(String)
    disc_revision = Column(String)
    languages = Column(String)
    edition = Column(String)
    catalog_source = Column(String)
    condition = Column(String)
    completeness = Column(String)
    location = Column(String)
    quantity = Column(Integer, server_default="1", nullable=False)
    purchase_date = Column(String)
    purchase_price = Column(Float)
    current_value = Column(Float)
    notes = Column(Text)
    is_wishlist = Column(Integer, server_default="0")
    wishlist_max_price = Column(Float)
    item_type = Column(String, server_default="game")
    character_name = Column(String)
    series_name = Column(String)
    scale = Column(String)
    funko_number = Column(String)
    vinyl_format = Column(String)
    created_at = Column(String, server_default=func.current_timestamp())
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    platform = relationship("Platform", back_populates="games")
    price_history = relationship("PriceHistory", back_populates="game", cascade="all, delete-orphan")
    images = relationship("ItemImage", back_populates="game", cascade="all, delete-orphan")
    copies = relationship("GameCopy", back_populates="game", cascade="all, delete-orphan", order_by="GameCopy.id")

class GameCopy(Base):
    __tablename__ = "game_copies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    condition = Column(String)
    completeness = Column(String)
    region = Column(String)
    barcode = Column(String)
    purchase_price = Column(Float)
    purchase_date = Column(String)
    location = Column(String)
    current_value = Column(Float)
    notes = Column(Text)
    created_at = Column(String, server_default=func.current_timestamp())
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    game = relationship("Game", back_populates="copies")


class ItemImage(Base):
    __tablename__ = "item_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String, nullable=False)
    is_primary = Column(Integer, server_default="0", nullable=False)
    sort_order = Column(Integer, server_default="0", nullable=False)
    created_at = Column(String, server_default=func.current_timestamp())

    game = relationship("Game", back_populates="images")

class ValueHistory(Base):
    __tablename__ = "value_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    recorded_at = Column(String, nullable=False)
    total_value = Column(Float, nullable=False)
    game_value = Column(Float, nullable=False)
    hardware_value = Column(Float, nullable=False)

class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    source = Column(String, server_default="pricecharting")
    loose_price = Column(Float)
    complete_price = Column(Float)
    new_price = Column(Float)
    graded_price = Column(Float)
    box_only_price = Column(Float)
    manual_only_price = Column(Float)
    eur_rate = Column(Float)
    pricecharting_id = Column(String)
    fetched_at = Column(String, server_default=func.current_timestamp())

    game = relationship("Game", back_populates="price_history")

class PriceCatalog(Base):
    __tablename__ = "price_catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pricecharting_id = Column(String)
    title = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    loose_usd = Column(Float)
    cib_usd = Column(Float)
    new_usd = Column(Float)
    loose_eur = Column(Float)
    cib_eur = Column(Float)
    new_eur = Column(Float)
    page_url = Column(String)
    scraped_at = Column(String, server_default=func.current_timestamp())
    changed_at = Column(String)

    __table_args__ = (
        Index('idx_price_catalog_title', title, sqlite_where=None),
        Index('idx_price_catalog_platform', platform),
        Index('idx_price_catalog_platform_title', platform, title, sqlite_where=None),
        Index('idx_price_catalog_platform_pcid', platform, pricecharting_id),
    )

class AppMeta(Base):
    __tablename__ = "app_meta"

    key = Column(String, primary_key=True)
    value = Column(String)
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    name = Column(String, nullable=False)
    purchase_date = Column(String)
    seller = Column(String)
    purchase_price_gross = Column(Float, server_default="0", nullable=False)
    shipping_in = Column(Float, server_default="0", nullable=False)
    fees_in = Column(Float, server_default="0", nullable=False)
    other_costs = Column(Float, server_default="0", nullable=False)
    notes = Column(Text)
    created_at = Column(String, server_default=func.current_timestamp())
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    items = relationship("LotItem", back_populates="lot", cascade="all, delete-orphan")


class LotItem(Base):
    __tablename__ = "lot_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="SET NULL"))
    title_snapshot = Column(String, nullable=False)
    platform_snapshot = Column(String)
    item_type_snapshot = Column(String, server_default="game")
    quantity = Column(Integer, server_default="1", nullable=False)
    estimated_value = Column(Float)
    cost_basis_override = Column(Float)
    allocated_cost_basis = Column(Float, server_default="0", nullable=False)
    allocation_method = Column(String, server_default="estimated", nullable=False)
    status = Column(String, server_default="inventory", nullable=False)
    notes = Column(Text)
    created_at = Column(String, server_default=func.current_timestamp())
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    lot = relationship("Lot", back_populates="items")
    sale = relationship("LotSale", back_populates="item", cascade="all, delete-orphan", uselist=False)

    __table_args__ = (
        Index("idx_lot_items_lot_id", lot_id),
        Index("idx_lot_items_game_id", game_id),
    )


class LotSale(Base):
    __tablename__ = "lot_sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_item_id = Column(Integer, ForeignKey("lot_items.id", ondelete="CASCADE"), nullable=False)
    sold_at = Column(String)
    channel = Column(String)
    sale_price_gross = Column(Float, server_default="0", nullable=False)
    platform_fees = Column(Float, server_default="0", nullable=False)
    shipping_out = Column(Float, server_default="0", nullable=False)
    other_costs = Column(Float, server_default="0", nullable=False)
    net_proceeds = Column(Float, server_default="0", nullable=False)
    realized_profit = Column(Float, server_default="0", nullable=False)
    notes = Column(Text)
    created_at = Column(String, server_default=func.current_timestamp())
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    item = relationship("LotItem", back_populates="sale")

    __table_args__ = (
        UniqueConstraint("lot_item_id", name="uq_lot_sales_lot_item_id"),
        Index("idx_lot_sales_lot_item_id", lot_item_id),
    )


# ---------------------------------------------------------------------------
# Multi-user / auth / sharing
# ---------------------------------------------------------------------------

class User(Base):
    """An account that logs in with email + password (+ optional TOTP MFA)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    display_name = Column(String)
    password_hash = Column(String, nullable=False)
    # Global role pyramid: super_admin (you) can manage users/global settings/all
    # collections; everyone else is a regular user scoped to their memberships.
    is_super_admin = Column(Boolean, server_default="0", nullable=False)
    is_active = Column(Boolean, server_default="1", nullable=False)
    # TOTP multi-factor. Secret is base32; only "enabled" once the user has proven
    # they can generate a valid code (confirmed setup).
    mfa_enabled = Column(Boolean, server_default="0", nullable=False)
    mfa_secret = Column(String)
    mfa_recovery_codes = Column(Text)  # JSON list of bcrypt-hashed one-time codes
    # Bumped on password change / forced logout to invalidate outstanding tokens.
    token_version = Column(Integer, server_default="0", nullable=False)
    last_login_at = Column(String)
    created_at = Column(String, server_default=func.current_timestamp())
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    memberships = relationship("CollectionMember", back_populates="user", cascade="all, delete-orphan")


class Collection(Base):
    """A shared workspace holding games/lots. Users join via CollectionMember."""
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    # Convenience pointer to the owning user; authoritative roles live in members.
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    is_personal = Column(Boolean, server_default="0", nullable=False)
    created_at = Column(String, server_default=func.current_timestamp())
    updated_at = Column(String, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    members = relationship("CollectionMember", back_populates="collection", cascade="all, delete-orphan")


class CollectionMember(Base):
    """A user's membership in a collection, with a per-collection role."""
    __tablename__ = "collection_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # owner > editor > viewer. owner can manage members/delete; editor can write
    # items; viewer is read-only.
    role = Column(String, server_default="viewer", nullable=False)
    created_at = Column(String, server_default=func.current_timestamp())

    collection = relationship("Collection", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("collection_id", "user_id", name="uq_collection_member"),
        Index("idx_collection_members_user", user_id),
    )


class Invitation(Base):
    """Pending invite for someone to join a collection at a given role."""
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, server_default="editor", nullable=False)
    token = Column(String, nullable=False, unique=True)
    invited_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    accepted_at = Column(String)
    created_at = Column(String, server_default=func.current_timestamp())

    __table_args__ = (
        Index("idx_invitations_email", email),
    )
