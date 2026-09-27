"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "image",
                "video",
                "audio",
                name="asset_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "upload",
                "generated",
                "derived",
                name="asset_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("mime", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("ai_generated", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("path", name=op.f("uq_assets_path")),
    )
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_assets_checksum_sha256"), ["checksum_sha256"], unique=False)
        batch_op.create_index(batch_op.f("ix_assets_kind"), ["kind"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("cta", sa.String(length=200), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price IS NULL OR price >= 0", name=op.f("ck_products_price_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_products_name"), ["name"], unique=False)

    op.create_table(
        "properties",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "property",
                "land",
                name="property_category",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "listing_type",
            sa.Enum(
                "sale", "rent", name="listing_type", native_enum=False, create_constraint=True, length=32
            ),
            nullable=True,
        ),
        sa.Column("property_type", sa.String(length=60), nullable=True),
        sa.Column("price", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("square_meters", sa.Float(), nullable=True),
        sa.Column("land_square_meters", sa.Float(), nullable=True),
        sa.Column("rooms", sa.String(length=20), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("floors", sa.Integer(), nullable=True),
        sa.Column("building_age", sa.Integer(), nullable=True),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("contact", sa.String(length=300), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("zoning", sa.String(length=300), nullable=True),
        sa.Column("parcel_info", sa.String(length=300), nullable=True),
        sa.Column("road_access", sa.Boolean(), nullable=True),
        sa.Column("electricity", sa.Boolean(), nullable=True),
        sa.Column("water", sa.Boolean(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("facts_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("facts_source", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name=op.f("ck_properties_coordinates_pair")
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name=op.f("ck_properties_latitude_range"),
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name=op.f("ck_properties_longitude_range"),
        ),
        sa.CheckConstraint("price IS NULL OR price >= 0", name=op.f("ck_properties_price_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_properties")),
    )
    with op.batch_alter_table("properties", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_properties_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_properties_title"), ["title"], unique=False)

    op.create_table(
        "consents",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column(
            "subject_type",
            sa.Enum(
                "face", "voice", name="consent_subject", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column("subject_name", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.String(length=200), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_asset_id", sa.String(length=40), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_asset_id"],
            ["assets.id"],
            name=op.f("fk_consents_evidence_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consents")),
    )
    op.create_table(
        "product_assets",
        sa.Column("product_id", sa.String(length=40), nullable=False),
        sa.Column("asset_id", sa.String(length=40), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "reference",
                "canonical",
                "front",
                "three_quarter",
                "full_body",
                "product_photo",
                "cutout",
                "mask",
                "photo",
                "footage",
                "drone",
                "floor_plan",
                name="asset_role",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name=op.f("fk_product_assets_asset_id_assets"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_assets_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_id", "asset_id", "role", name=op.f("pk_product_assets")),
    )
    op.create_table(
        "property_assets",
        sa.Column("property_id", sa.String(length=40), nullable=False),
        sa.Column("asset_id", sa.String(length=40), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "reference",
                "canonical",
                "front",
                "three_quarter",
                "full_body",
                "product_photo",
                "cutout",
                "mask",
                "photo",
                "footage",
                "drone",
                "floor_plan",
                name="asset_role",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name=op.f("fk_property_assets_asset_id_assets"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_property_assets_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("property_id", "asset_id", "role", name=op.f("pk_property_assets")),
    )
    op.create_table(
        "characters",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("adult_age", sa.Integer(), nullable=False),
        sa.Column("presentation", sa.String(length=60), nullable=False),
        sa.Column("face_description", sa.Text(), nullable=False),
        sa.Column("hair", sa.String(length=200), nullable=False),
        sa.Column("eye_color", sa.String(length=60), nullable=False),
        sa.Column("skin_appearance", sa.String(length=200), nullable=False),
        sa.Column("body_description", sa.Text(), nullable=False),
        sa.Column("style", sa.String(length=200), nullable=False),
        sa.Column("clothing_preferences", sa.Text(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("speaking_style", sa.Text(), nullable=False),
        sa.Column("brand_tone", sa.String(length=200), nullable=False),
        sa.Column("default_language", sa.String(length=16), nullable=False),
        sa.Column("default_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("preferred_camera_angles", sa.JSON(), nullable=False),
        sa.Column("color_palette", sa.JSON(), nullable=False),
        sa.Column("voice_profile", sa.JSON(), nullable=False),
        sa.Column("is_real_person", sa.Boolean(), nullable=False),
        sa.Column("consent_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "adult_age >= 18 AND adult_age <= 120", name=op.f("ck_characters_adult_age_range")
        ),
        sa.CheckConstraint(
            "is_real_person = 0 OR consent_id IS NOT NULL",
            name=op.f("ck_characters_real_person_requires_consent"),
        ),
        sa.ForeignKeyConstraint(
            ["consent_id"],
            ["consents.id"],
            name=op.f("fk_characters_consent_id_consents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_characters")),
    )
    with op.batch_alter_table("characters", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_characters_name"), ["name"], unique=False)

    op.create_table(
        "character_assets",
        sa.Column("character_id", sa.String(length=40), nullable=False),
        sa.Column("asset_id", sa.String(length=40), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "reference",
                "canonical",
                "front",
                "three_quarter",
                "full_body",
                "product_photo",
                "cutout",
                "mask",
                "photo",
                "footage",
                "drone",
                "floor_plan",
                name="asset_role",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name=op.f("fk_character_assets_asset_id_assets"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            name=op.f("fk_character_assets_character_id_characters"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("character_id", "asset_id", "role", name=op.f("pk_character_assets")),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "social",
                "product_ad",
                "real_estate",
                "land",
                "custom",
                name="project_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("character_id", sa.String(length=40), nullable=True),
        sa.Column("product_id", sa.String(length=40), nullable=True),
        sa.Column("property_id", sa.String(length=40), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            name=op.f("fk_projects_character_id_characters"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_projects_product_id_products"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_projects_property_id_properties"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_projects_name"), ["name"], unique=False)
        batch_op.create_index(batch_op.f("ix_projects_type"), ["type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_projects_type"))
        batch_op.drop_index(batch_op.f("ix_projects_name"))

    op.drop_table("projects")
    op.drop_table("character_assets")
    with op.batch_alter_table("characters", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_characters_name"))

    op.drop_table("characters")
    op.drop_table("property_assets")
    op.drop_table("product_assets")
    op.drop_table("consents")
    with op.batch_alter_table("properties", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_properties_title"))
        batch_op.drop_index(batch_op.f("ix_properties_category"))

    op.drop_table("properties")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_products_name"))

    op.drop_table("products")
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_assets_kind"))
        batch_op.drop_index(batch_op.f("ix_assets_checksum_sha256"))

    op.drop_table("assets")
