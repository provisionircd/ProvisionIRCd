class OperData:
    clients = {}

    @staticmethod
    def save_host(client):
        if client not in OperData.clients:
            OperData.clients[client] = {}
        OperData.clients[client]["host"] = client.user.cloakhost

    @staticmethod
    def save_original_class(client):
        if client not in OperData.clients:
            OperData.clients[client] = {}
        OperData.clients[client]["class"] = client.class_

    @staticmethod
    def get_host(client):
        if client not in OperData.clients or "host" not in OperData.clients[client]:
            return None
        return OperData.clients[client]["host"]

    @staticmethod
    def get_original_class(client):
        if client not in OperData.clients or "class" not in OperData.clients[client]:
            return None
        return OperData.clients[client]["class"]
