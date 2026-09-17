"""Idempotent MongoDB indexes. Created once at startup, never per request."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, IndexModel
from pymongo.errors import OperationFailure

from app.core.logging import get_logger
from app.db.collections import CollectionName

logger = get_logger(__name__)

IndexSpec = tuple[str, list[IndexModel]]


def _index_plan() -> list[IndexSpec]:
    return [
        (CollectionName.USERS, [IndexModel([("email", ASCENDING)], unique=True, name="uniq_users_email")]),
        (CollectionName.BUSINESS_ACCOUNTS, [IndexModel([("name", ASCENDING)], name="idx_business_accounts_name")]),
        (
            CollectionName.BUSINESS_MEMBERSHIPS,
            [
                IndexModel([("user_id", ASCENDING), ("business_account_id", ASCENDING)], unique=True, name="uniq_membership_user_business"),
                IndexModel([("user_id", ASCENDING)], name="idx_memberships_user_id"),
                IndexModel([("business_account_id", ASCENDING)], name="idx_memberships_business_account_id"),
            ],
        ),
        (
            CollectionName.ROLES,
            [
                IndexModel([("business_account_id", ASCENDING), ("name", ASCENDING)], unique=True, name="uniq_roles_business_name"),
                IndexModel([("business_account_id", ASCENDING)], name="idx_roles_business_account_id"),
            ],
        ),
        (
            CollectionName.PERMISSIONS,
            [IndexModel([("resource", ASCENDING), ("action", ASCENDING)], unique=True, name="uniq_permissions_resource_action")],
        ),
        (
            CollectionName.ROLE_PERMISSIONS,
            [
                IndexModel([("role_id", ASCENDING), ("permission_id", ASCENDING)], unique=True, name="uniq_role_permissions"),
                IndexModel([("role_id", ASCENDING)], name="idx_role_permissions_role_id"),
            ],
        ),
        (
            CollectionName.INVITATIONS,
            [
                IndexModel([("token_hash", ASCENDING)], unique=True, name="uniq_invitations_token_hash"),
                IndexModel(
                    [("business_account_id", ASCENDING), ("invited_email", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"status": "pending"},
                    name="uniq_invitations_pending_business_email",
                ),
            ],
        ),
        (
            CollectionName.SESSIONS,
            [
                IndexModel([("refresh_token_hash", ASCENDING)], unique=True, name="uniq_sessions_refresh_token_hash"),
                IndexModel([("user_id", ASCENDING)], name="idx_sessions_user_id"),
                IndexModel([("active_business_account_id", ASCENDING)], name="idx_sessions_active_business"),
            ],
        ),
        (
            CollectionName.AUTH_TOKENS,
            [
                IndexModel([("token_hash", ASCENDING)], unique=True, name="uniq_auth_tokens_token_hash"),
                IndexModel([("user_id", ASCENDING), ("purpose", ASCENDING)], name="idx_auth_tokens_user_purpose"),
            ],
        ),
        (
            CollectionName.AUDIT_LOGS,
            [
                IndexModel([("resource_type", ASCENDING), ("resource_id", ASCENDING)], name="idx_audit_resource"),
                IndexModel([("business_account_id", ASCENDING), ("created_at", ASCENDING)], name="idx_audit_business_created"),
            ],
        ),
        (
            CollectionName.SUPPLIER_PROFILES,
            [IndexModel([("business_account_id", ASCENDING)], unique=True, name="uniq_supplier_profiles_business")],
        ),
        (CollectionName.CATEGORIES, [IndexModel([("slug", ASCENDING)], unique=True, name="uniq_categories_slug")]),
        (
            CollectionName.PRODUCTS,
            [
                IndexModel([("supplier_id", ASCENDING), ("sku", ASCENDING)], unique=True, name="uniq_products_supplier_sku"),
                IndexModel([("supplier_id", ASCENDING)], name="idx_products_supplier_id"),
                IndexModel([("business_account_id", ASCENDING)], name="idx_products_business_account_id"),
                IndexModel([("category_id", ASCENDING)], name="idx_products_category_id"),
                IndexModel([("sku", ASCENDING)], name="idx_products_sku"),
                IndexModel([("slug", ASCENDING)], name="idx_products_slug"),
                IndexModel([("status", ASCENDING)], name="idx_products_status"),
            ],
        ),
        (CollectionName.PRODUCT_PRICES, [IndexModel([("product_id", ASCENDING)], name="idx_product_prices_product_id")]),
        (CollectionName.PRODUCT_IMAGES, [IndexModel([("product_id", ASCENDING)], name="idx_product_images_product_id")]),
        (CollectionName.INVENTORIES, [IndexModel([("product_id", ASCENDING)], unique=True, name="uniq_inventories_product_id")]),
        (
            CollectionName.INVENTORY_TRANSACTIONS,
            [
                IndexModel([("inventory_id", ASCENDING)], name="idx_inventory_tx_inventory_id"),
                IndexModel([("product_id", ASCENDING)], name="idx_inventory_tx_product_id"),
                IndexModel([("reference_type", ASCENDING), ("reference_id", ASCENDING)], name="idx_inventory_tx_reference"),
            ],
        ),
        (
            CollectionName.RFQS,
            [
                IndexModel([("rfq_number", ASCENDING)], unique=True, name="uniq_rfqs_number"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_rfqs_buyer_business_id"),
                IndexModel([("status", ASCENDING)], name="idx_rfqs_status"),
            ],
        ),
        (CollectionName.RFQ_ITEMS, [IndexModel([("rfq_id", ASCENDING)], name="idx_rfq_items_rfq_id")]),
        (
            CollectionName.QUOTATIONS,
            [
                IndexModel([("quotation_number", ASCENDING)], unique=True, name="uniq_quotations_number"),
                IndexModel(
                    [("rfq_id", ASCENDING), ("supplier_id", ASCENDING)],
                    unique=True,
                    name="uniq_quotations_rfq_supplier",
                ),
                IndexModel(
                    [("rfq_id", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"status": "accepted"},
                    name="uniq_quotations_accepted_per_rfq",
                ),
                IndexModel([("rfq_id", ASCENDING)], name="idx_quotations_rfq_id"),
                IndexModel([("supplier_id", ASCENDING)], name="idx_quotations_supplier_id"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_quotations_buyer_business_id"),
            ],
        ),
        (
            CollectionName.QUOTATION_ITEMS,
            [
                IndexModel(
                    [("quotation_id", ASCENDING), ("rfq_item_id", ASCENDING), ("version", ASCENDING)],
                    unique=True,
                    name="uniq_quotation_items_quote_rfq_item_version",
                ),
                IndexModel([("quotation_id", ASCENDING)], name="idx_quotation_items_quotation_id"),
            ],
        ),
        (
            CollectionName.ORDERS,
            [
                IndexModel([("order_number", ASCENDING)], unique=True, name="uniq_orders_number"),
                IndexModel([("quotation_id", ASCENDING)], unique=True, name="uniq_orders_quotation_id"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_orders_buyer_business_id"),
                IndexModel([("supplier_business_id", ASCENDING)], name="idx_orders_supplier_business_id"),
                IndexModel([("rfq_id", ASCENDING)], name="idx_orders_rfq_id"),
                IndexModel([("status", ASCENDING)], name="idx_orders_status"),
            ],
        ),
        (CollectionName.ORDER_ITEMS, [IndexModel([("order_id", ASCENDING)], name="idx_order_items_order_id")]),
        (
            CollectionName.SHIPMENTS,
            [
                IndexModel([("shipment_number", ASCENDING)], unique=True, name="uniq_shipments_number"),
                IndexModel([("order_id", ASCENDING)], name="idx_shipments_order_id"),
                IndexModel([("tracking_number", ASCENDING)], name="idx_shipments_tracking_number"),
            ],
        ),
        (
            CollectionName.CUSTOMER_INVOICES,
            [
                IndexModel([("invoice_number", ASCENDING)], unique=True, name="uniq_invoices_number"),
                IndexModel([("order_id", ASCENDING)], unique=True, name="uniq_invoices_order_id"),
                IndexModel([("order_id", ASCENDING)], name="idx_invoices_order_id"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_invoices_buyer_business_id"),
                IndexModel([("status", ASCENDING), ("due_at", ASCENDING)], name="idx_invoices_status_due"),
            ],
        ),
        (
            CollectionName.PAYMENTS,
            [
                IndexModel([("payment_reference", ASCENDING)], unique=True, name="uniq_payments_reference"),
                IndexModel([("idempotency_key", ASCENDING)], unique=True, sparse=True, name="uniq_payments_idempotency_key"),
                IndexModel([("provider_event_id", ASCENDING)], unique=True, sparse=True, name="uniq_payments_provider_event_id"),
                # A payment may settle several invoices, so the link lives on the allocations array.
                IndexModel([("allocations.invoice_id", ASCENDING)], name="idx_payments_allocations_invoice_id"),
                IndexModel([("payer_business_id", ASCENDING)], name="idx_payments_payer_business_id"),
            ],
        ),
        (
            CollectionName.CREDIT_NOTES,
            [
                IndexModel([("credit_note_number", ASCENDING)], unique=True, name="uniq_credit_notes_number"),
                IndexModel([("invoice_id", ASCENDING)], name="idx_credit_notes_invoice_id"),
            ],
        ),
        (
            CollectionName.REFUNDS,
            [
                IndexModel([("refund_number", ASCENDING)], unique=True, name="uniq_refunds_number"),
                IndexModel([("payment_id", ASCENDING)], name="idx_refunds_payment_id"),
                IndexModel([("invoice_id", ASCENDING)], name="idx_refunds_invoice_id"),
            ],
        ),
        (
            CollectionName.FINANCIAL_TRANSACTIONS,
            [
                IndexModel([("transaction_number", ASCENDING)], unique=True, name="uniq_financial_tx_number"),
                # Buyer statement, outstanding and aging are all computed off this index.
                IndexModel([("business_account_id", ASCENDING), ("posted_at", ASCENDING)], name="idx_financial_tx_business_posted"),
                IndexModel([("source_type", ASCENDING), ("source_id", ASCENDING)], name="idx_financial_tx_source"),
                IndexModel([("invoice_id", ASCENDING)], name="idx_financial_tx_invoice_id"),
                IndexModel([("order_id", ASCENDING)], name="idx_financial_tx_order_id"),
            ],
        ),
        (
            CollectionName.COMMISSION_RECORDS,
            [
                IndexModel([("order_id", ASCENDING)], unique=True, name="uniq_commission_records_order_id"),
                IndexModel([("supplier_business_id", ASCENDING)], name="idx_commission_records_supplier_id"),
                IndexModel([("status", ASCENDING)], name="idx_commission_records_status"),
            ],
        ),
        (
            CollectionName.SUPPLIER_PAYABLES,
            [
                IndexModel([("payable_number", ASCENDING)], unique=True, name="uniq_payables_number"),
                IndexModel([("order_id", ASCENDING)], name="idx_payables_order_id"),
                IndexModel([("supplier_business_id", ASCENDING), ("status", ASCENDING)], name="idx_payables_supplier_status"),
            ],
        ),
        (
            CollectionName.SUPPLIER_PAYOUTS,
            [
                IndexModel([("payout_number", ASCENDING)], unique=True, name="uniq_payouts_number"),
                IndexModel([("provider_event_id", ASCENDING)], unique=True, sparse=True, name="uniq_payouts_provider_event_id"),
                IndexModel([("idempotency_key", ASCENDING)], unique=True, sparse=True, name="uniq_payouts_idempotency_key"),
                IndexModel([("supplier_business_id", ASCENDING)], name="idx_payouts_supplier_business_id"),
                IndexModel([("supplier_payable_id", ASCENDING)], name="idx_payouts_payable_id"),
                IndexModel([("settlement_batch_id", ASCENDING)], name="idx_payouts_settlement_batch_id"),
            ],
        ),
        (
            CollectionName.SETTLEMENT_BATCHES,
            [
                IndexModel([("batch_number", ASCENDING)], unique=True, name="uniq_settlements_number"),
                IndexModel([("status", ASCENDING)], name="idx_settlements_status"),
            ],
        ),
        (
            CollectionName.PLATFORM_TRANSACTIONS,
            [
                IndexModel([("transaction_number", ASCENDING)], unique=True, name="uniq_platform_tx_number"),
                # {source}:{event_id}:{type} — one provider event may post several row types.
                IndexModel([("idempotency_key", ASCENDING)], unique=True, sparse=True, name="uniq_platform_tx_idempotency_key"),
                IndexModel([("type", ASCENDING), ("posted_at", ASCENDING)], name="idx_platform_tx_type_posted"),
                IndexModel([("reference_type", ASCENDING), ("reference_id", ASCENDING)], name="idx_platform_tx_reference"),
                IndexModel([("order_id", ASCENDING)], name="idx_platform_tx_order_id"),
                IndexModel([("supplier_business_id", ASCENDING)], name="idx_platform_tx_supplier_business_id"),
            ],
        ),
        (CollectionName.REVIEWS, [IndexModel([("order_id", ASCENDING)], unique=True, name="uniq_reviews_order_id")]),
        (
            CollectionName.DISPUTES,
            [
                IndexModel([("dispute_number", ASCENDING)], unique=True, name="uniq_disputes_number"),
                IndexModel([("order_id", ASCENDING)], name="idx_disputes_order_id"),
                IndexModel([("status", ASCENDING)], name="idx_disputes_status"),
            ],
        ),
        (
            CollectionName.NOTIFICATIONS,
            [
                IndexModel([("recipient_user_id", ASCENDING), ("created_at", ASCENDING)], name="idx_notifications_recipient_created"),
                IndexModel([("recipient_user_id", ASCENDING), ("is_read", ASCENDING)], name="idx_notifications_recipient_is_read"),
            ],
        ),
        # System settings — singletons keyed on "default"
        (CollectionName.PLATFORM_SETTINGS, [IndexModel([("key", ASCENDING)], unique=True, name="uniq_platform_settings_key")]),
        (CollectionName.BUSINESS_SETTINGS, [IndexModel([("key", ASCENDING)], unique=True, name="uniq_business_settings_key")]),
        (
            CollectionName.TAX_SETTINGS,
            [
                IndexModel(
                    [("is_active", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"is_active": True},
                    name="uniq_tax_settings_one_active",
                ),
                IndexModel([("is_active", ASCENDING), ("effective_from", ASCENDING)], name="idx_tax_settings_active_effective"),
            ],
        ),
        # Communication
        (
            CollectionName.CONVERSATIONS,
            [
                # One thread per business context; DIRECT and SUPPORT have no context and are exempt.
                IndexModel(
                    [("context_type", ASCENDING), ("context_id", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"context_type": {"$type": "string"}},
                    name="uniq_conversations_context",
                ),
                IndexModel([("initiator_business_id", ASCENDING), ("last_message_at", ASCENDING)], name="idx_conversations_initiator_last_message"),
                IndexModel([("counterparty_business_id", ASCENDING), ("last_message_at", ASCENDING)], name="idx_conversations_counterparty_last_message"),
                IndexModel([("type", ASCENDING), ("status", ASCENDING)], name="idx_conversations_type_status"),
            ],
        ),
        (
            CollectionName.CONVERSATION_PARTICIPANTS,
            [
                IndexModel([("conversation_id", ASCENDING), ("user_id", ASCENDING)], unique=True, name="uniq_participants_conversation_user"),
                IndexModel([("user_id", ASCENDING), ("last_read_at", ASCENDING)], name="idx_participants_user_last_read"),
                IndexModel([("business_account_id", ASCENDING)], name="idx_participants_business_account_id"),
            ],
        ),
        (
            CollectionName.MESSAGES,
            [
                IndexModel([("conversation_id", ASCENDING), ("created_at", ASCENDING)], name="idx_messages_conversation_created"),
                IndexModel([("sender_user_id", ASCENDING)], name="idx_messages_sender_user_id"),
                IndexModel([("reference_type", ASCENDING), ("reference_id", ASCENDING)], name="idx_messages_reference"),
                IndexModel([("reply_to_message_id", ASCENDING)], name="idx_messages_reply_to_message_id"),
            ],
        ),
        # Negotiation
        (
            CollectionName.NEGOTIATIONS,
            [
                # Sparse but NOT unique: a conversation is optional in both directions.
                IndexModel([("conversation_id", ASCENDING)], sparse=True, name="idx_negotiations_conversation_id"),
                IndexModel([("rfq_id", ASCENDING)], name="idx_negotiations_rfq_id"),
                IndexModel([("quotation_id", ASCENDING)], name="idx_negotiations_quotation_id"),
                IndexModel([("status", ASCENDING)], name="idx_negotiations_status"),
            ],
        ),
        (
            CollectionName.NEGOTIATION_OFFERS,
            [
                IndexModel([("negotiation_id", ASCENDING), ("created_at", ASCENDING)], name="idx_offers_negotiation_created"),
                IndexModel([("parent_offer_id", ASCENDING)], name="idx_offers_parent_offer_id"),
                IndexModel([("status", ASCENDING)], name="idx_offers_status"),
            ],
        ),
        (
            CollectionName.NEGOTIATION_OFFER_ITEMS,
            [
                IndexModel(
                    [("offer_id", ASCENDING), ("rfq_item_id", ASCENDING)],
                    unique=True,
                    name="uniq_offer_items_offer_rfq_item",
                ),
                IndexModel([("negotiation_id", ASCENDING)], name="idx_offer_items_negotiation_id"),
            ],
        ),
        # AI Sourcing
        (
            CollectionName.SOURCING_REQUESTS,
            [
                IndexModel([("buyer_user_id", ASCENDING)], name="idx_sourcing_requests_buyer"),
                IndexModel([("status", ASCENDING)], name="idx_sourcing_requests_status"),
                IndexModel([("rfq_id", ASCENDING)], name="idx_sourcing_requests_rfq_id"),
                IndexModel([("business_plan_id", ASCENDING)], name="idx_sourcing_requests_business_plan_id"),
            ],
        ),
        (
            CollectionName.SOURCING_REQUEST_ITEMS,
            [IndexModel([("sourcing_request_id", ASCENDING)], name="idx_sourcing_items_request_id")],
        ),
        (
            CollectionName.SOURCING_RECOMMENDATIONS,
            [
                IndexModel([("sourcing_request_id", ASCENDING)], name="idx_sourcing_recs_request_id"),
                IndexModel([("product_id", ASCENDING)], name="idx_sourcing_recs_product_id"),
                IndexModel([("business_account_id", ASCENDING)], name="idx_sourcing_recs_business_id"),
            ],
        ),
        # Business Planner
        (
            CollectionName.BUSINESS_PLANS,
            [
                IndexModel([("user_id", ASCENDING)], name="idx_business_plans_user_id"),
                IndexModel([("status", ASCENDING)], name="idx_business_plans_status"),
            ],
        ),
        (
            CollectionName.BUSINESS_PLAN_ITEMS,
            [IndexModel([("business_plan_id", ASCENDING)], name="idx_business_plan_items_plan_id")],
        ),
        (
            CollectionName.PRICE_ESTIMATES,
            [IndexModel([("business_plan_item_id", ASCENDING)], name="idx_price_estimates_item_id")],
        ),
    ]


async def ensure_indexes(database: Any) -> None:
    for collection_name, models in _index_plan():
        collection = database[str(collection_name)]
        try:
            await collection.create_indexes(models)
        except OperationFailure as exc:
            logger.warning(
                "index_create_skipped",
                collection=str(collection_name),
                reason=str(exc.details) if exc.details else str(exc),
            )
