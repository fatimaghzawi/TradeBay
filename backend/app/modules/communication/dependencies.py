from app.modules.communication.service import ConversationService, MessageService


def get_conversation_service() -> ConversationService:
    return ConversationService()


def get_message_service() -> MessageService:
    return MessageService()
