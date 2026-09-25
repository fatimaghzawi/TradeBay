
from enum import StrEnum


class CollectionName(StrEnum):
              
    USERS = "users"
    BUSINESS_ACCOUNTS = "business_accounts"
    BUSINESS_MEMBERSHIPS = "business_memberships"
    ROLES = "roles"
    PERMISSIONS = "permissions"
    ROLE_PERMISSIONS = "role_permissions"
    INVITATIONS = "invitations"
    SESSIONS = "sessions"
    AUTH_TOKENS = "auth_tokens"
    AUDIT_LOGS = "audit_logs"
    SUPPLIER_PROFILES = "supplier_profiles"

                                                                 
    CATEGORIES = "categories"
    PRODUCTS = "products"
    PRODUCT_PRICES = "product_prices"
    PRODUCT_IMAGES = "product_images"
    INVENTORIES = "inventories"
    INVENTORY_TRANSACTIONS = "inventory_transactions"
    CARTS = "carts"
    CART_ITEMS = "cart_items"

                 
    RFQS = "rfqs"
    RFQ_ITEMS = "rfq_items"
    QUOTATIONS = "quotations"
    QUOTATION_ITEMS = "quotation_items"
    ORDERS = "orders"
    ORDER_ITEMS = "order_items"
    SHIPMENTS = "shipments"
    SHIPMENT_ITEMS = "shipment_items"

                   
    CONVERSATIONS = "conversations"
    CONVERSATION_PARTICIPANTS = "conversation_participants"
    MESSAGES = "messages"

                                                                  
    NEGOTIATIONS = "negotiations"
    NEGOTIATION_OFFERS = "negotiation_offers"
    NEGOTIATION_OFFER_ITEMS = "negotiation_offer_items"

                 
    SOURCING_REQUESTS = "sourcing_requests"
    SOURCING_REQUEST_ITEMS = "sourcing_request_items"
    SOURCING_RECOMMENDATIONS = "sourcing_recommendations"
                                                                                    
    CATALOG_EMBEDDINGS = "catalog_embeddings"
                                                                                 
    AI_USAGE = "ai_usage"
    BUSINESS_PROCUREMENT_PROFILES = "business_procurement_profiles"

                                                     
    BUSINESS_PLANS = "business_plans"
    BUSINESS_PLAN_ITEMS = "business_plan_items"
    PRICE_ESTIMATES = "price_estimates"
    BUSINESS_PLAN_SESSIONS = "business_plan_sessions"
    BUSINESS_PLAN_MESSAGES = "business_plan_messages"

                                                                               
    CHECKOUTS = "checkouts"

                                                                     
    CUSTOMER_INVOICES = "customer_invoices"
    PAYMENTS = "payments"
                                                                              
    PAYMENT_PROVIDER_EVENTS = "payment_provider_events"
    CREDIT_NOTES = "credit_notes"
    REFUNDS = "refunds"
    FINANCIAL_TRANSACTIONS = "financial_transactions"

                    
    COMMISSION_RECORDS = "commission_records"
    SUPPLIER_PAYABLES = "supplier_payables"
    SUPPLIER_PAYOUTS = "supplier_payouts"
    SETTLEMENT_BATCHES = "settlement_batches"
    PLATFORM_TRANSACTIONS = "platform_transactions"
                                                                       
    SUPPLIER_LEDGER_ENTRIES = "supplier_ledger_entries"

           
    REVIEWS = "reviews"
    DISPUTES = "disputes"
    NOTIFICATIONS = "notifications"

                                                               
    PLATFORM_SETTINGS = "platform_settings"
    TAX_SETTINGS = "tax_settings"
    BUSINESS_SETTINGS = "business_settings"
    DOCUMENT_COUNTERS = "document_counters"
