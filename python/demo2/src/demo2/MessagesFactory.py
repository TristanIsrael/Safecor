class MessagesFactory:
    @staticmethod
    def create_message_request(message: str) -> dict:
        return {"message": message}
