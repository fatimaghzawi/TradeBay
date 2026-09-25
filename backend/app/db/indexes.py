
from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel
from pymongo.errors import OperationFailure

from app.core.logging import get_logger
from app.db.collections import CollectionName

logger = get_logger(__name__)

IndexSpec = tuple[str, list[IndexModel]]

def _index_plan() -> list[IndexSpec]:
    return [
        (CollectionName.USERS, [
            IndexModel([("email", ASCENDING)], unique=True, name="uniq_users_email"),
            IndexModel([("status", ASCENDING), ("created_at", ASCENDING)], name="idx_users_status_created"),
        ]),
        (CollectionName.BUSINESS_ACCOUNTS, [
            IndexModel([("name", ASCENDING)], name="idx_business_accounts_name"),
            IndexModel(
                [("type", ASCENDING), ("status", ASCENDING), ("updated_at", ASCENDING)],
                name="idx_business_accounts_type_status_updated",
            ),
            IndexModel(
                [("email_domain", ASCENDING)],
                name="idx_business_accounts_email_domain",
            ),
                                                                                         
            IndexModel(
                [("type", ASCENDING)],
                unique=True,
                partialFilterExpression={"type": "platform"},
                name="uniq_platform_business",
            ),
        ]),
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
                IndexModel([("family_id", ASCENDING)], sparse=True, name="idx_sessions_family"),
            ],
        ),
        (
            CollectionName.AUTH_TOKENS,
            [
                IndexModel(
                    [("user_id", ASCENDING), ("purpose", ASCENDING), ("created_at", DESCENDING)],
                    name="idx_auth_tokens_user_purpose_created",
                ),
                                                                                         
                IndexModel(
                    [("expires_at", ASCENDING)],
                    expireAfterSeconds=7 * 24 * 60 * 60,
                    name="ttl_auth_tokens_expires_at",
                ),
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
            [
                IndexModel([("business_account_id", ASCENDING)], unique=True, name="uniq_supplier_profiles_business"),
                IndexModel(
                    [("verification_status", ASCENDING), ("updated_at", ASCENDING)],
                    name="idx_supplier_profiles_verification_updated",
                ),
            ],
        ),
        (
            CollectionName.CATEGORIES,
            [
                IndexModel([("slug", ASCENDING)], unique=True, name="uniq_categories_slug"),
                IndexModel([("parent_category_id", ASCENDING)], name="idx_categories_parent"),
                IndexModel(
                    [("is_active", ASCENDING), ("display_order", ASCENDING)],
                    name="idx_categories_active_order",
                ),
            ],
        ),
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
                IndexModel(
                    [("is_featured", ASCENDING), ("status", ASCENDING)],
                    name="idx_products_featured_status",
                ),
                IndexModel(
                    [("status", ASCENDING), ("category_id", ASCENDING)],
                    name="idx_products_status_category",
                ),
                IndexModel(
                    [("name", TEXT), ("description", TEXT)],
                    name="idx_products_name_description_text",
                    default_language="english",
                ),
            ],
        ),
        (
            CollectionName.PRODUCT_PRICES,
            [
                IndexModel(
                    [("product_id", ASCENDING), ("min_quantity", ASCENDING)],
                    name="idx_product_prices_product_min",
                ),
                IndexModel(
                    [("product_id", ASCENDING), ("max_quantity", ASCENDING)],
                    name="idx_product_prices_product_max",
                ),
            ],
        ),
        (CollectionName.PRODUCT_IMAGES, [IndexModel([("product_id", ASCENDING)], name="idx_product_images_product_id")]),
        (CollectionName.INVENTORIES, [IndexModel([("product_id", ASCENDING)], unique=True, name="uniq_inventories_product_id")]),
        (
            CollectionName.INVENTORY_TRANSACTIONS,
            [
                IndexModel(
                    [("inventory_id", ASCENDING), ("created_at", ASCENDING)],
                    name="idx_inventory_tx_inventory_created",
                ),
                IndexModel([("product_id", ASCENDING)], name="idx_inventory_tx_product_id"),
                IndexModel([("transaction_type", ASCENDING)], name="idx_inventory_tx_type"),
                IndexModel(
                    [("reference_type", ASCENDING), ("reference_id", ASCENDING)],
                    name="idx_inventory_tx_reference",
                ),
            ],
        ),
        (
            CollectionName.CARTS,
            [
                IndexModel(
                    [("buyer_business_id", ASCENDING)],
                    unique=True,
                    name="uniq_carts_buyer_business_id",
                ),
            ],
        ),
        (
            CollectionName.CART_ITEMS,
            [
                IndexModel(
                    [("buyer_business_id", ASCENDING), ("product_id", ASCENDING)],
                    unique=True,
                    name="uniq_cart_items_buyer_product",
                ),
                IndexModel(
                    [("cart_id", ASCENDING)],
                    name="idx_cart_items_cart_id",
                ),
            ],
        ),
        (
            CollectionName.RFQS,
            [
                IndexModel([("rfq_number", ASCENDING)], unique=True, name="uniq_rfqs_number"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_rfqs_buyer_business_id"),
                IndexModel([("status", ASCENDING)], name="idx_rfqs_status"),
                IndexModel([("rfq_type", ASCENDING)], name="idx_rfqs_type"),
                IndexModel([("product_id", ASCENDING)], name="idx_rfqs_product_id"),
                IndexModel(
                    [("supplier_business_id", ASCENDING)],
                    name="idx_rfqs_supplier_business_id",
                ),
                IndexModel(
                    [("buyer_business_id", ASCENDING), ("rfq_type", ASCENDING), ("status", ASCENDING)],
                    name="idx_rfqs_buyer_type_status",
                ),
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
                                                                                               
                IndexModel(
                    [("quotation_id", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"quotation_id": {"$type": "objectId"}},
                    name="uniq_orders_quotation_id_present",
                ),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_orders_buyer_business_id"),
                IndexModel([("supplier_business_id", ASCENDING)], name="idx_orders_supplier_business_id"),
                IndexModel([("rfq_id", ASCENDING)], name="idx_orders_rfq_id"),
                IndexModel([("status", ASCENDING)], name="idx_orders_status"),
                                                                        
                IndexModel(
                    [("checkout_id", ASCENDING), ("supplier_business_id", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"checkout_id": {"$type": "objectId"}},
                    name="uniq_orders_checkout_supplier",
                ),
            ],
        ),
        (
            CollectionName.CHECKOUTS,
            [
                IndexModel([("checkout_number", ASCENDING)], unique=True, name="uniq_checkouts_number"),
                                                                                                   
                IndexModel(
                    [("buyer_business_id", ASCENDING), ("idempotency_key", ASCENDING)],
                    unique=True,
                    name="uniq_checkouts_buyer_idempotency_key",
                ),
                IndexModel(
                    [("buyer_business_id", ASCENDING), ("created_at", DESCENDING)],
                    name="idx_checkouts_buyer_created",
                ),
                IndexModel([("status", ASCENDING)], name="idx_checkouts_status"),
            ],
        ),
        (
            CollectionName.PAYMENT_PROVIDER_EVENTS,
            [
                IndexModel(
                    [("provider", ASCENDING), ("event_id", ASCENDING)],
                    unique=True,
                    name="uniq_payment_provider_events_event",
                ),
            ],
        ),
        (
            CollectionName.SUPPLIER_LEDGER_ENTRIES,
            [
                IndexModel([("idempotency_key", ASCENDING)], unique=True, name="uniq_supplier_ledger_idempotency_key"),
                IndexModel(
                    [("supplier_business_id", ASCENDING), ("created_at", DESCENDING)],
                    name="idx_supplier_ledger_supplier_created",
                ),
                IndexModel([("order_id", ASCENDING)], name="idx_supplier_ledger_order_id"),
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
            CollectionName.SHIPMENT_ITEMS,
            [
                IndexModel([("shipment_id", ASCENDING)], name="idx_shipment_items_shipment_id"),
                IndexModel([("order_id", ASCENDING)], name="idx_shipment_items_order_id"),
                IndexModel([("order_item_id", ASCENDING)], name="idx_shipment_items_order_item_id"),
            ],
        ),
        (
            CollectionName.CUSTOMER_INVOICES,
            [
                IndexModel([("invoice_number", ASCENDING)], unique=True, name="uniq_invoices_number"),
                IndexModel([("order_id", ASCENDING)], unique=True, name="uniq_invoices_order_id"),
                IndexModel([("order_id", ASCENDING)], name="idx_invoices_order_id"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_invoices_buyer_business_id"),
                IndexModel([("supplier_business_id", ASCENDING)], name="idx_invoices_supplier_business_id"),
                IndexModel([("checkout_id", ASCENDING)], name="idx_invoices_checkout_id"),
                IndexModel([("status", ASCENDING), ("due_at", ASCENDING)], name="idx_invoices_status_due"),
            ],
        ),
        (
            CollectionName.PAYMENTS,
            [
                IndexModel([("payment_reference", ASCENDING)], unique=True, name="uniq_payments_reference"),
                IndexModel([("idempotency_key", ASCENDING)], unique=True, sparse=True, name="uniq_payments_idempotency_key"),
                IndexModel([("provider_event_id", ASCENDING)], unique=True, sparse=True, name="uniq_payments_provider_event_id"),
                                                                                                    
                IndexModel([("allocations.invoice_id", ASCENDING)], name="idx_payments_allocations_invoice_id"),
                IndexModel([("payer_business_id", ASCENDING)], name="idx_payments_payer_business_id"),
                IndexModel([("status", ASCENDING)], name="idx_payments_status"),
                IndexModel([("checkout_id", ASCENDING)], name="idx_payments_checkout_id"),
                IndexModel(
                    [("provider", ASCENDING), ("provider_payment_id", ASCENDING)],
                    unique=True,
                    partialFilterExpression={"provider_payment_id": {"$type": "string"}},
                    name="uniq_payments_provider_payment_id",
                ),
            ],
        ),
        (
            CollectionName.CREDIT_NOTES,
            [
                IndexModel([("credit_note_number", ASCENDING)], unique=True, name="uniq_credit_notes_number"),
                IndexModel([("invoice_id", ASCENDING)], name="idx_credit_notes_invoice_id"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_credit_notes_buyer"),
                IndexModel([("status", ASCENDING)], name="idx_credit_notes_status"),
            ],
        ),
        (
            CollectionName.REFUNDS,
            [
                IndexModel([("refund_number", ASCENDING)], unique=True, name="uniq_refunds_number"),
                IndexModel([("payment_id", ASCENDING)], name="idx_refunds_payment_id"),
                IndexModel([("credit_note_id", ASCENDING)], name="idx_refunds_credit_note_id"),
                IndexModel([("invoice_id", ASCENDING)], name="idx_refunds_invoice_id"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_refunds_buyer"),
                IndexModel([("status", ASCENDING)], name="idx_refunds_status"),
            ],
        ),
        (
            CollectionName.FINANCIAL_TRANSACTIONS,
            [
                IndexModel([("transaction_number", ASCENDING)], unique=True, name="uniq_financial_tx_number"),
                                                                                         
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
                IndexModel([("status", ASCENDING)], name="idx_payouts_status"),
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
                       
        (
            CollectionName.CONVERSATIONS,
            [
                                                                                      
                                                                                        
                IndexModel(
                    [("context_type", ASCENDING), ("context_id", ASCENDING)],
                    name="idx_conversations_context",
                ),
                IndexModel(
                    [("initiator_business_id", ASCENDING), ("counterparty_business_id", ASCENDING)],
                    name="idx_conversations_pair",
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
                     
        (
            CollectionName.NEGOTIATIONS,
            [
                                                                                       
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
                     
        (
            CollectionName.SOURCING_REQUESTS,
            [
                IndexModel([("buyer_user_id", ASCENDING)], name="idx_sourcing_requests_buyer"),
                IndexModel([("buyer_business_id", ASCENDING)], name="idx_sourcing_requests_business"),
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
            CollectionName.CATALOG_EMBEDDINGS,
            [
                IndexModel([("product_id", ASCENDING)], unique=True, name="uniq_catalog_embeddings_product"),
                IndexModel([("category_id", ASCENDING)], name="idx_catalog_embeddings_category"),
                IndexModel([("content_hash", ASCENDING)], name="idx_catalog_embeddings_hash"),
            ],
        ),
        (
            CollectionName.AI_USAGE,
            [
                IndexModel(
                    [("subject_id", ASCENDING), ("day", ASCENDING)],
                    unique=True,
                    name="uniq_ai_usage_subject_day",
                ),
                IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_ai_usage"),
            ],
        ),
        (
            CollectionName.SOURCING_RECOMMENDATIONS,
            [
                IndexModel([("sourcing_request_id", ASCENDING)], name="idx_sourcing_recs_request_id"),
                IndexModel([("product_id", ASCENDING)], name="idx_sourcing_recs_product_id"),
                IndexModel([("business_account_id", ASCENDING)], name="idx_sourcing_recs_business_id"),
            ],
        ),
        (
            CollectionName.BUSINESS_PROCUREMENT_PROFILES,
            [
                IndexModel(
                    [("business_account_id", ASCENDING)],
                    unique=True,
                    name="uniq_procurement_profile_business",
                ),
            ],
        ),
                          
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
        (
            CollectionName.BUSINESS_PLAN_SESSIONS,
            [
                IndexModel([("user_id", ASCENDING)], name="idx_business_plan_sessions_user_id"),
                IndexModel([("status", ASCENDING)], name="idx_business_plan_sessions_status"),
            ],
        ),
        (
            CollectionName.BUSINESS_PLAN_MESSAGES,
            [
                IndexModel(
                    [("business_plan_id", ASCENDING), ("created_at", ASCENDING)],
                    name="idx_business_plan_messages_plan_created",
                ),
            ],
        ),
    ]

_INDEXES_TO_DROP: tuple[tuple[str, str], ...] = (
                                                                                     
    (CollectionName.CONVERSATIONS, "uniq_conversations_context"),
                                                                                        
    (CollectionName.AUTH_TOKENS, "uniq_auth_tokens_token_hash"),
    (CollectionName.AUTH_TOKENS, "idx_auth_tokens_user_purpose"),
                                                                                                                
    (CollectionName.ORDERS, "uniq_orders_quotation_id"),
)

async def ensure_indexes(database: Any, *, fail_fast: bool = False) -> None:
    for collection_name, index_name in _INDEXES_TO_DROP:
        try:
            await database[str(collection_name)].drop_index(index_name)
        except OperationFailure:
            pass
    for collection_name, models in _index_plan():
        collection = database[str(collection_name)]
        try:
            await collection.create_indexes(models)
        except OperationFailure as exc:
            if fail_fast:
                logger.error(
                    "index_create_failed",
                    collection=str(collection_name),
                    reason=str(exc.details) if exc.details else str(exc),
                )
                raise
            logger.warning(
                "index_create_skipped",
                collection=str(collection_name),
                reason=str(exc.details) if exc.details else str(exc),
            )
                                                                                     
                                                                        
    existing = set(await database.list_collection_names())
    for name in _TRANSACTIONAL_COLLECTIONS:
        if str(name) not in existing:
            try:
                await database.create_collection(str(name))
            except OperationFailure:
                pass

_TRANSACTIONAL_COLLECTIONS = (
    CollectionName.DOCUMENT_COUNTERS,
    CollectionName.CHECKOUTS,
    CollectionName.ORDERS,
    CollectionName.ORDER_ITEMS,
    CollectionName.CUSTOMER_INVOICES,
    CollectionName.PAYMENTS,
    CollectionName.FINANCIAL_TRANSACTIONS,
    CollectionName.SUPPLIER_PAYOUTS,
    CollectionName.COMMISSION_RECORDS,
    CollectionName.SUPPLIER_PAYABLES,
    CollectionName.PLATFORM_TRANSACTIONS,
    CollectionName.SUPPLIER_LEDGER_ENTRIES,
    CollectionName.PAYMENT_PROVIDER_EVENTS,
    CollectionName.INVENTORIES,
    CollectionName.INVENTORY_TRANSACTIONS,
    CollectionName.CART_ITEMS,
)
