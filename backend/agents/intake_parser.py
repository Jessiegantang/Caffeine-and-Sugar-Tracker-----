from agent import parse_intake_message


def parse_intake(user_message: str) -> dict:
    return parse_intake_message(user_message)

