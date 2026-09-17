from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    collection_name = CollectionName.CONVERSATIONS


class ConversationParticipantRepository(BaseRepository):
    collection_name = CollectionName.CONVERSATION_PARTICIPANTS


class MessageRepository(BaseRepository):
    collection_name = CollectionName.MESSAGES
