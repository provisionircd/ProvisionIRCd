idx = - 1


def error():
    global idx
    idx += 1
    return idx


class Error:
    SERVER_SID_EXISTS = error(), "SID {} already exists on the network"
    SERVER_NAME_EXISTS = error(), "A server with that name ({}) already exists on the network"

    SERVER_MISSING_USERMODES = error(), "Server {} is missing user modes: {}"
    SERVER_MISSING_CHANNELMODES = error(), "Server {} is missing channel modes: {}"
    SERVER_MISSING_MEMBERMODES = error(), "Server {} is missing channel member modes: {}"
    SERVER_EXTBAN_PREFIX_MISMATCH = error(), "Extban prefixes are not the same."
    SERVER_MISSING_EXTBANS = error(), "Extbans mismatch. Missing extbans: {}"
    SERVER_PROTOCTL_PARSE_FAIL = error(), "Invalid PROTOCTL received from {}: {}"

    SERVER_LINK_NOMATCH = error(), "No matching link configuration"
    SERVER_LINK_NOMATCH_IP = error(), "Link block mask does not match"
    SERVER_LINK_NOMATCH_CERTFP = error(), "Certificate fingerprints do not match"
    SERVER_LINK_MAXCLASS = error(), "Maximum instances of link class '{}' reached"
    SERVER_LINK_NOCLASS = error(), "Remote server was unable to found a matching connection class for us"
    SERVER_LINK_NAME_COLLISION = error(), "Server name {} already in use"
    SERVER_LINK_INCORRECT_PASSWORD = error(), "Incorrect password"

    USER_UID_INVALID = error(), "[UID] Unable to parse UID from server {}"
    USER_UID_NOT_ENOUGH_PARAMS = error(), "[UID] Not enough parameters for UID from {}: {} != 13"
    USER_UID_SIGNON_NO_DIGIT = error(), "Invalid timestamp received in UID: {}. Must be a timestamp."

    @staticmethod
    def send(error_code, *args):
        error_num, error_string = error_code
        error_string = error_string.format(*args)
        # logging.error(error_string)
        return error_string
